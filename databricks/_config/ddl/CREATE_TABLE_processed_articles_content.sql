SET catalog_name = 'biomed_genai_alex_barreto';
SET schema_name  = 'processed';
SET table_name   = 'articles_content';

CREATE TABLE IF NOT EXISTS biomed_genai_alex_barreto.processed.articles_content (
    id        STRING NOT NULL,
    pmid      STRING,
    journal   STRING,
    title     STRING,
    year      STRING,
    citation  STRING,
    content   STRING,
    CONSTRAINT pk_id PRIMARY KEY (id)
)
USING DELTA
TBLPROPERTIES (
  delta.checkpointPolicy = 'v2',
  delta.enableDeletionVectors = true,
  delta.enableRowTracking = true,
  delta.feature.deletionVectors = 'supported',
  delta.feature.rowTracking = 'supported',
  delta.feature.v2Checkpoint = 'supported',
  delta.enableChangeDataFeed = true
);