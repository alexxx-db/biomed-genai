SET catalog_name = 'biomed_genai_alex_barreto';
SET schema_name  = 'curated';
SET table_name   = 'articles_xml';

CREATE TABLE IF NOT EXISTS biomed_genai_alex_barreto.curated.articles_xml (
  AccessionID          STRING,
  ETag                 STRING,
  LastUpdated          TIMESTAMP,
  PMID                 STRING,
  attrs                MAP<STRING, STRING>,
  front                STRING,
  body                 STRING,
  floats_group         STRING,
  back                 STRING,
  processing_metadata  STRING,
  _ingestion_timestamp TIMESTAMP,
  volume_path STRING)
USING DELTA
CLUSTER BY (AccessionID)
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true'
)