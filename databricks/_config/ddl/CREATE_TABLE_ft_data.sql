SET catalog_name = 'biomed_genai_alex_barreto';
SET schema_name  = 'syn_data_gen';
SET table_name   = 'data';

CREATE TABLE IF NOT EXISTS biomed_genai_alex_barreto.syn_data_gen.data (
    id        STRING NOT NULL,
    pmid      STRING,
    journal   STRING,
    title     STRING,
    year      STRING,
    citation  STRING,
    content   STRING,
    question  STRING,
    answer    STRING,
    CONSTRAINT pk_ft_seed_id PRIMARY KEY (id)
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