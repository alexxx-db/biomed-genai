# Databricks notebook source
"""
Configuration parameters for biomed_genai model training pipeline.

This module provides:
- Databricks authentication and connection settings
- MLflow configuration for model registry
- Environment setup for both notebook and IDE execution
"""

import os
import json
import pandas as pd
from databricks.sdk.runtime import dbutils
import mlflow

# Configure MLflow to use Unity Catalog for model registry
mlflow.set_registry_uri("databricks-uc")

# Databricks authentication - uses environment variables or secrets
DATABRICKS_TOKEN: str = os.environ.get('DATABRICKS_TOKEN', dbutils.secrets.get("biomed_genai", "token"))
DATABRICKS_HOST: str = os.environ.get('DATABRICKS_HOST', f"https://{json.loads(dbutils.notebook.entry_point.getDbutils().notebook().getContext().toJson())['tags']['browserHostName']}")
BASE_URL: str = f"{DATABRICKS_HOST}serving-endpoints"


# if not in Databricks notebook but in IDE
if not os.environ.get('DATABRICKS_RUNTIME_VERSION'):
   spark = DatabricksSession.builder.remote(
      host       = DATABRICKS_HOST,
      token      = DATABRICKS_TOKEN,
      cluster_id = json.loads(dbutils.notebook.entry_point.getDbutils().notebook().getContext().safeToJson())['attributes']['clusterId']
   ).getOrCreate()