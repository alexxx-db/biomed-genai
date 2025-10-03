# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # Sync VectorSearch Index
# MAGIC
# MAGIC **Objective:** Sync the processed articles content Delta table to a VectorSearch index for semantic search.
# MAGIC
# MAGIC **Setup:** `%run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true`
# MAGIC
# MAGIC - Uses config/objects from `pubmed_wf`
# MAGIC - Demonstrates both Databricks SDK and LangChain integration.

# COMMAND ----------

# DBTITLE 1, Initialize pubmed_wf Application Class
# MAGIC %run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true

# COMMAND ----------

# Inspect Endpoint (optional)
endpoint = pubmed_wf.vector_search.biomed.endpoint
print("VectorSearch endpoint info:", endpoint)

# COMMAND ----------

# Sync Index: triggers a DLT job, does not await completion.
pubmed_wf.vector_search.biomed.processed_articles_content_vs_index.index.sync()

# COMMAND ----------

# [OPTIONAL] Inspect VectorSearch Index via similarity_search
INSPECT_VS_INDEX = False
if INSPECT_VS_INDEX:
    query_text = "What are some proteins associated with breast cancer and what methods are available to detect these?"
    vs_index = pubmed_wf.vector_search.biomed.processed_articles_content_vs_index.index
    rslt = vs_index.similarity_search(
        query_text=query_text,
        columns=["id", "content"],
        num_results=5
    )
    display(rslt)

# COMMAND ----------

# [OPTIONAL] Inspect VectorSearch Index as a LangChain Retriever
INSPECT_LC_INDEX = False
if INSPECT_LC_INDEX:
    from langchain_community.vectorstores import DatabricksVectorSearch
    query_text = "What are some proteins associated with breast cancer and what methods are available to detect these?"

    retriever_config = {
        "chunk_template": "Passage: {chunk_text}\n",
        "data_pipeline_tag": "biomed_workflow",
        "parameters": {"k": 5, "query_type": "ann"},
        "schema": {"chunk_text": "content", "document_uri": "url", "primary_key": "id"},
        "vector_search_index": pubmed_wf.vector_search.biomed.processed_articles_content_vs_index.index.name
    }
    # Turn the Vector Search index into a LangChain retriever
    lc_retriever = DatabricksVectorSearch(
        index=pubmed_wf.vector_search.biomed.processed_articles_content_vs_index.index,
        text_column="content",
        columns=["id", "content"]
    ).as_retriever(**retriever_config)
    rslt = lc_retriever.invoke(query_text)
    print(rslt)