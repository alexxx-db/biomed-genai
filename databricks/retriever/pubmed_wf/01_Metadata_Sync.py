# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # PMC MetaData Sync
# MAGIC
# MAGIC **Objective**: Synchronize PubMed Central metadata (from S3) into the biomed_genai catalog as a managed Delta table.
# MAGIC
# MAGIC **Setup**: Run `%run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true`
# MAGIC

# COMMAND ----------

# DBTITLE 1, Initialize pubmed_wf application class
# MAGIC %run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true

# Set parameters
PMC_SOURCE_METADATA_BUCKET = "s3://pmc-oa-opendata/oa_comm/xml/metadata/csv/"
TARGET_TABLE = pubmed_wf.raw_metadata_xml.uc_name

# COMMAND ----------

from pyspark.sql import SparkSession, DataFrame, functions as F
from delta.tables import DeltaTable

readStream_options = {
    "cloudFiles.format": "csv",
    "cloudFiles.allowOverwrites": "true",
    "cloudFiles.schemaLocation": pubmed_wf.raw_metadata_xml.cp.path,
    "header": "true"
}

readStream_columns = [
    F.col("Key"),
    F.col("ETag"),
    F.col("Article Citation").alias("ArticleCitation"),
    F.col("AccessionID"),
    F.col("Last Updated UTC (YYYY-MM-DD HH:MM:SS)").cast("timestamp").alias("LastUpdated"),
    F.col("PMID"),
    F.col("License"),
    F.col("Retracted"),
    F.col("_metadata.file_path").alias("_file_path"),
    F.col("_metadata.file_modification_time").alias("_file_modification_time"),
    F.col("_metadata.file_size").alias("_file_size"),
    F.current_timestamp().alias("_ingestion_timestamp"),
    F.lit("PENDING").alias("status"),
    F.lit(None).alias('volume_path')
]

def upsert_metadata(microBatchOutputDF: DataFrame, batchId: int):
    """Upsert new metadata into the target Delta table."""
    tgt_df = pubmed_wf.raw_metadata_xml.dt.alias("tgt")
    tgt_df.merge(source=microBatchOutputDF.alias("src"),
                 condition="src.AccessionID = tgt.AccessionID") \
        .whenMatchedUpdateAll(condition="src.LastUpdated > tgt.LastUpdated") \
        .whenNotMatchedInsertAll() \
        .execute()

# COMMAND ----------

# Allow anonymous reads from S3
spark.conf.set("fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider")

spark.readStream.format("cloudFiles") \
    .options(**readStream_options) \
    .load(PMC_SOURCE_METADATA_BUCKET) \
    .select(*readStream_columns) \
    .writeStream.foreachBatch(upsert_metadata) \
    .trigger(availableNow=True) \
    .option("checkpointLocation", pubmed_wf.raw_metadata_xml.cp.path) \
    .queryName(f"query_{pubmed_wf.raw_metadata_xml.name}".replace('`', '').replace('-', '_')) \
    .start() \
    .awaitTermination()

# COMMAND ----------

# Inspect metadata history (optional)
INSPECT_METADATA_HIST = False
if INSPECT_METADATA_HIST:
    hist = spark.sql(f"DESCRIBE HISTORY {TARGET_TABLE}")
    display(hist)

# COMMAND ----------

INSPECT_METADATA = False
if INSPECT_METADATA:
    display(pubmed_wf.raw_metadata_xml.df)