# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # Workflow_pubmed_wf Config Class Instantiation
# MAGIC
# MAGIC This notebook demonstrates configuration for the BioMed GenAI retriever workflow using the Workflow_pubmed_wf dataclass.
# MAGIC
# MAGIC ## Usage
# MAGIC - Setup via `%run ./_setup/setup_pubmed_wf`
# MAGIC - Inspect workflow entities in the config object and metadata tables.
# MAGIC - Not strictly required for workflow execution, but useful for debugging and documentation.
# MAGIC
# MAGIC ## Related files
# MAGIC - [config.py](../../../python/biomed_genai/config.py)
# MAGIC - [workflow_pubmed_wf.py](../../../python/biomed_genai/retriever/pubmed_wf/workflow_pubmed_wf.py)
# MAGIC - [viz_workflow.py](../../../python/biomed_genai/retriever/pubmed_wf/viz_workflow.py)

# COMMAND ----------

# MAGIC %run ./_setup/setup_pubmed_wf $SHOW_TABLE=true $SHOW_WORKFLOW=false

# COMMAND ----------

# As a convenience, Delta Table (dt) and Spark DataFrame (df) instances for UC assets are included as cached properties
print(pubmed_wf.raw_metadata_xml.df.__class__)
pubmed_wf.raw_metadata_xml.df.printSchema()

# COMMAND ----------

pubmed_wf.raw_articles_xml.path

# COMMAND ----------

# MAGIC %run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true

# COMMAND ----------

# For more details on workflow entities and execution order, see the main README or documentation.