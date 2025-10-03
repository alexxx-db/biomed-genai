SET catalog_name = 'biomed_genai_alex_barreto';
SET schema_name  = 'agents';
SET table_name = 'bc_eval_ds';

CREATE TABLE IF NOT EXISTS biomed_genai_alex_barreto.agents.bc_eval_ds (
  request_id                  STRING NOT NULL,
  request                     STRING NOT NULL,
  expected_retrieved_context  STRING,
  expected_response           STRING NOT NULL,
  response                    STRING,
  retrieved_context           STRING,
  trace                       STRING,
  CONSTRAINT pk_request_id PRIMARY KEY (request_id)
)
USING delta
TBLPROPERTIES (
  'delta.minReaderVersion' = '1',
  'delta.minWriterVersion' = '2')