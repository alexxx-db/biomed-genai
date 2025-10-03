# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # Chunk Articles with `unstructured`
# MAGIC
# MAGIC **Objective:** Chunk article bodies for vector search using the `unstructured` library.
# MAGIC
# MAGIC **Setup:** `%run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true`
# MAGIC
# MAGIC - Uses config/objects from `pubmed_wf`
# MAGIC - See [partition-xml](https://docs.unstructured.io/open-source/core-functionality/partitioning#partition-xml) for chunking options

# COMMAND ----------

# DBTITLE 1, Initialize pubmed_wf Application Class
# MAGIC %run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true

# COMMAND ----------

# The `processed_articles_content` table gets its DDL from the config/sql path
sql_path = pubmed_wf.processed_articles_content.sql_path
with open(sql_path, 'r') as file:
    sql = file.read()
    print(sql)

# COMMAND ----------

# Chunking UDF for article bodies using unstructured
from unstructured.partition.xml import partition_xml
from pyspark.sql.types import ArrayType, StringType
import xml.etree.ElementTree as ET
import html2text

chunking_strategy_params = {
    'chunking_strategy': 'by_title',
    'combine_text_under_n_chars': 500,
    'new_after_n_chars': 3850,
    'max_characters': 4000
}

def chunk_xml_body(body: str, attrs: dict, **kwargs):
    """
    Chunk XML article body text with specified strategy.
    Returns: list of text chunks for vector search.
    """
    text_maker = html2text.HTML2Text()
    root = ET.Element('root', attrib=attrs)
    root.text = body
    body_elements = partition_xml(
        text=str(ET.tostring(root, encoding='utf-8'), 'UTF-8'),
        xml_keep_tags=False,
        encoding='utf-8',
        include_metadata=False,
        languages=['eng'],
        date_from_file_object=None,
        chunking_strategy=kwargs.get('chunking_strategy', 'by_title'),
        multipage_sections=True,
        combine_text_under_n_chars=kwargs.get('combine_text_under_n_chars', 500),
        new_after_n_chars=kwargs.get('new_after_n_chars', 3850),
        max_characters=kwargs.get('max_characters', 4000)
    )
    body_chunks = [text_maker.handle(str(be.text)) for be in body_elements if len(be.text) >= 110]
    return body_chunks

chunk_xml_body_udf = udf(chunk_xml_body, ArrayType(StringType()))

# COMMAND ----------

# Ingest new (not-yet-chunked) articles into processed_articles_content
from pyspark.sql.functions import col, lit, concat, xpath_string, posexplode

pubmed_wf.curated_articles_xml.df.alias("a") \
    .join(
        pubmed_wf.processed_articles_content.df.select(col("pmid")).distinct().alias("b"),
        col("a.AccessionID") == col("b.pmid"),
        "left_anti"
    ) \
    .withColumn('contents', chunk_xml_body_udf('body', 'attrs')) \
    .select(
        col('AccessionID').alias('pmid'),
        xpath_string(col('front'), lit('front/article-meta/title-group/article-title')).alias('title'),
        xpath_string(col('front'), lit('front/journal-meta/journal-title-group/journal-title')).alias('journal'),
        lit('NEED DESIRED CITATION FORMAT').alias('citation'),
        xpath_string(col('front'), lit('front/article-meta/pub-date/year')).alias('year'),
        posexplode('contents').alias('content_pos', 'content')
    ) \
    .withColumn('id', concat(col('pmid'), lit('-'), col('content_pos'))) \
    .drop('content_pos') \
    .write.mode('append').saveAsTable(pubmed_wf.processed_articles_content.name)

# COMMAND ----------

INSPECT_CURATED_ARTICLES = True
if INSPECT_CURATED_ARTICLES:
    display(pubmed_wf.curated_articles_xml.df)

# COMMAND ----------

INSPECT_PROCESSED_ARTICLES = True
if INSPECT_PROCESSED_ARTICLES:
    display(pubmed_wf.processed_articles_content.df)