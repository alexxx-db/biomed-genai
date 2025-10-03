SET catalog_name = 'biomed_genai_alex_barreto';
SET schema_name  = 'raw';
SET table_name   = 'search_hist';

CREATE TABLE IF NOT EXISTS biomed_genai_alex_barreto.raw.search_hist (
  keyword STRING,
  min_dte STRING,
  max_dte STRING)
USING delta
TBLPROPERTIES (
  'delta.minReaderVersion' = '1',
  'delta.minWriterVersion' = '2')