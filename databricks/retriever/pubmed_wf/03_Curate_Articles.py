# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # Curate Articles
# MAGIC
# MAGIC **Objective**: Parse downloaded raw articles and save structured content into a Delta table for downstream processing.
# MAGIC
# MAGIC **Setup**: `%run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true`
# MAGIC
# MAGIC - Uses UDFs for XML parsing
# MAGIC - Appends new articles to `curated_articles_xml` table, avoids duplicates

# COMMAND ----------

# DBTITLE 1, Initialize pubmed_wf Application Class
# MAGIC %run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true

# COMMAND ----------

# The `curated_articles_xml` table gets its DDL from the config/sql path
sql_path = pubmed_wf.curated_articles_xml.sql_path
with open(sql_path, 'r') as file:
    sql = file.read()
    print(sql)

# COMMAND ----------

from pyspark.sql.functions import udf
from pyspark.sql.types import StringType, IntegerType, DoubleType, MapType, StructType, StructField

def article_parse_xml(accession_id: str, volume_path: str) -> tuple:
    """
    Parse XML article file given accession_id and volume_path.
    Returns tuple with structured fields for DB ingest.
    """
    from bs4 import BeautifulSoup
    with open(volume_path, 'r') as file:
        article = BeautifulSoup(file.read(), 'xml').find('article')
    return (
        accession_id, volume_path,
        {str(k):str(v) for k,v in article.attrs.items()},
        str(article.find('front')),
        str(article.find('body')),
        str(article.find('floats-group')),
        str(article.find('back')),
        str(article.find('processing-meta'))
    )

article_parse_xml_udf = udf(
    article_parse_xml,
    returnType=StructType([
        StructField("AccessionID",         StringType(), nullable=False),
        StructField("volume_path",         StringType(), nullable=False),
        StructField("attrs",               MapType(StringType(), StringType()), nullable=False),
        StructField("front",               StringType(), nullable=False),
        StructField("body",                StringType(), nullable=False),
        StructField("floats_group",        StringType(), nullable=False),
        StructField("back",                StringType(), nullable=False),
        StructField("processing_metadata", StringType(), nullable=False)
    ])
)

# COMMAND ----------

parsed_articles = pubmed_wf.raw_metadata_xml.df.filter('status="DOWNLOADED"') \
    .join(pubmed_wf.curated_articles_xml.df, 'AccessionID', 'leftanti') \
    .withColumn('parsed_struct', article_parse_xml_udf("AccessionID", "volume_path")) \
    .select('parsed_struct.AccessionID',
            'ETag',
            'LastUpdated',
            'PMID',
            'parsed_struct.attrs',
            'parsed_struct.front',
            'parsed_struct.body',
            'parsed_struct.floats_group',
            'parsed_struct.back',
            'parsed_struct.processing_metadata',
            '_ingestion_timestamp',
            'volume_path')

# COMMAND ----------

pubmed_wf.curated_articles_xml.dt.alias('tgt') \
    .merge(parsed_articles.alias('src'), "src.AccessionID = tgt.AccessionID") \
    .whenMatchedUpdateAll() \
    .whenNotMatchedInsertAll() \
    .execute()