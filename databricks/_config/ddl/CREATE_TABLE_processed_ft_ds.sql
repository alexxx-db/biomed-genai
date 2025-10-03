SET catalog_name = 'biomed_genai_alex_barreto';
SET schema_name  = 'processed';
SET table_name   = 'ift_ds';

CREATE TABLE biomed_genai_alex_barreto.processed.ift_ds (
  messages ARRAY<STRUCT<role: STRING, content: STRING>>)
USING delta
TBLPROPERTIES (
  'delta.minReaderVersion' = '1',
  'delta.minWriterVersion' = '2')