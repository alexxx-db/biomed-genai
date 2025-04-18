# Databricks notebook source
# MAGIC %md
# MAGIC This notebook is fourth in a series that **takes in synthetic data for Fine Tuning (FT)**.
# MAGIC
# MAGIC What this notebook does:
# MAGIC 1. Perform fine tuning using a chat model on the synthetic data generated and prepared in NBs 1-3
# MAGIC 2. Serve the model on an endpoint
# MAGIC 3. Perform inference using the endpoint

# COMMAND ----------

# MAGIC %pip install databricks-genai databricks-sdk mlflow
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %pip freeze

# COMMAND ----------

import os, json
from random import sample, seed
import mlflow
from mlflow import deployments
from pyspark.sql.types import StringType
from pyspark.sql.functions import pandas_udf, expr
from databricks.model_training import foundation_model as fm
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ServedEntityInput, EndpointCoreConfigInput, AutoCaptureConfigInput
from langchain_core.prompts import PromptTemplate
#from langchain_databricks import ChatDatabricks
from _setup.params import *
from _setup.utils import get_latest_model_version, get_current_cluster_id

# COMMAND ----------

# MAGIC %md
# MAGIC #### Set parameters and names

# COMMAND ----------

catalog = "yen"
db = "syn_data_gen"

train_table_name = f"{catalog}.{db}.train"
test_table_name = f"{catalog}.{db}.test"

base_model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
ft_model_name = f"{catalog}.{db}.pubmed_rag_model"

base_endpoint_name = "databricks-meta-llama-3-1-70b-instruct"
model_endpoint_name = "pubmed_rag_model"
inference_table_name = model_endpoint_name

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Fine tune using Model Training API with prehosted models

# COMMAND ----------

#https://docs.databricks.com/en/large-language-models/foundation-model-training/create-fine-tune-run.html
run = fm.create(
  model=base_model_name,
  experiment_path="/Users/yen.low@databricks.com/Experiments/biomed_genai",
  train_data_path=train_table_name,
  eval_data_path=test_table_name,
  data_prep_cluster_id = get_current_cluster_id(),
  register_to=ft_model_name,
  task_type="CHAT_COMPLETION",
  training_duration='3ep',
  context_length=8192,
)
print(run)

# COMMAND ----------

run.get_events()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Serve finetuned model
# MAGIC Set up the endpoint config

# COMMAND ----------

endpoint_config = EndpointCoreConfigInput(
    name=model_endpoint_name,
    served_entities=[
        ServedEntityInput(
            entity_name=ft_model_name,
            entity_version=get_latest_model_version(ft_model_name),
            min_provisioned_throughput=0, # The minimum tokens per second that the endpoint can scale down to.
            max_provisioned_throughput=3000,# The maximum tokens per second that the endpoint can scale up to.
            scale_to_zero_enabled=True
        )
    ],
    auto_capture_config = AutoCaptureConfigInput(catalog_name=catalog, schema_name=db, enabled=True,table_name_prefix=inference_table_name)
)

#Set this to True to release a newer version (the demo won't update the endpoint to a newer model version by default)
force_update = True

# COMMAND ----------

w = WorkspaceClient()

existing_endpoint = next(
    (e for e in w.serving_endpoints.list() if e.name == model_endpoint_name), None
)

if not existing_endpoint:
    print(f"Creating the endpoint {model_endpoint_name}, this will take a few minutes to package and deploy the endpoint...")
    w.serving_endpoints.create_and_wait(name=model_endpoint_name, config=endpoint_config)
else:
  print(f"endpoint {model_endpoint_name} already exist...")
  if force_update:
    print(f"Updating endpoint {model_endpoint_name}...")
    w.serving_endpoints.update_config_and_wait(served_entities=endpoint_config.served_entities, 
                                               name=model_endpoint_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Inferencing
# MAGIC Evaluate with our `test` dataset

# COMMAND ----------

test = spark.table(test_table_name)
display(test)

# COMMAND ----------

# MAGIC %md
# MAGIC #### Option 1: Using `curl` to call the REST API

# COMMAND ----------

# Get dict/json input for a curl call
inputs = test.toPandas().to_dict(orient="records")
seed(2)
input = sample(inputs, 1)[0]['messages'].tolist()[0:2]
print(input)

# COMMAND ----------

input_dict = {"messages": input,
              "temperature":0,
              "max_tokens":500}
input_json = json.dumps(input_dict)

# COMMAND ----------

# Set input as an env var to pass it to shell
os.environ['input_json'] = input_json
os.environ['DATABRICKS_TOKEN'] = DATABRICKS_TOKEN
os.environ['endpoint'] = model_endpoint_name

# COMMAND ----------

# MAGIC %sh
# MAGIC echo $input_json
# MAGIC curl \
# MAGIC -u token:"$DATABRICKS_TOKEN" \
# MAGIC -X POST \
# MAGIC -H "Content-Type: application/json" \
# MAGIC -d "$input_json" \
# MAGIC "https://adb-830292400663869.9.azuredatabricks.net/serving-endpoints/$endpoint/invocations"

# COMMAND ----------

# MAGIC %md
# MAGIC #### Option 2: Using `mlflow` client

# COMMAND ----------

client = mlflow.deployments.get_deploy_client("databricks")
response = client.predict(endpoint=model_endpoint_name, inputs=input_dict)
print(response['choices'][0]['message']['content'])

# COMMAND ----------

# MAGIC %md
# MAGIC #### Option 3 (RECOMMENDED): Bulk/multiple inference with `ai_query` 

# COMMAND ----------

pred_ft = test \
    .withColumn("question", test.messages.getItem(1)['content']) \
    .withColumn("answer", test.messages.getItem(2)['content']) \
    .withColumn("prediction", expr(f"""ai_query('{model_endpoint_name}', 
                                   CONCAT('{{"messages": [{{"role": "user", "content": "', question, '}}]}}'))"""))
display(pred_ft)

# COMMAND ----------

# MAGIC %md
# MAGIC #### TODO: Option 4: batch invocation with `langchain`
# MAGIC finetuned model is a completion type model and requires a different prompt template
# MAGIC This is also less performant than using `ai_query`

# COMMAND ----------

# TODO Not working
# full_prompt = PromptTemplate.from_template("{prompt}")
# default_temperature = 0.1

# llm = ChatDatabricks(endpoint=model_endpoint_name, temperature=default_temperature)
# llm_base = ChatDatabricks(endpoint='databricks-meta-llama-3-1-70b-instruct',
#                   temperature=default_temperature)
# llm_judge = 'databricks-meta-llama-3.1-405b-instruct'

# chain = full_prompt | llm_base
# pred_lc = chain.with_retry(stop_after_attempt=2) \
#     .batch(inputs[0:5], config={"max_concurrency": 4})

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Evaluate model answering quality (no retrieval) - `mlflow.evaluate`
# MAGIC Use LLM judges with ground truth answers to compare responses from a finetuned model vs those from a base model without finetuning.
# MAGIC
# MAGIC #### Generate prediction dataframes using the base model and the finetuned model

# COMMAND ----------

pred_base = test \
    .withColumn("question", test.messages.getItem(1)['content']) \
    .withColumn("answer", test.messages.getItem(2)['content']) \
    .withColumn("prediction", expr(f"""ai_query('{base_endpoint_name}',
                                   CONCAT('{{"messages": [{{"role": "user", "content": "', question, '}}]}}'))"""))
display(pred_base)

# COMMAND ----------

# Responses from base model without finetuning
with mlflow.start_run(run_name=f"eval_{base_endpoint_name}") as run:
    results = mlflow.evaluate(
        data=pred_base,
        targets="answer",
        predictions="prediction",
        model_type="question-answering",
        # extra_metrics=[
        #     mlflow.metrics.genai.answer_similarity(model=f"endpoints:/{llm_judge}"),
        #     mlflow.metrics.genai.answer_correctness(model=f"endpoints:/{llm_judge}")
        # ],
        evaluators="default"
    )

# COMMAND ----------

# Responses from finetuned model
with mlflow.start_run(run_name=f"eval_{model_endpoint_name}") as run:
    results = mlflow.evaluate(
        data=pred_ft,
        targets="answer",
        predictions="prediction",
        model_type="question-answering",
        extra_metrics=[
            mlflow.metrics.genai.answer_similarity(model=f"endpoints:/{llm_judge}"),
            mlflow.metrics.genai.answer_correctness(model=f"endpoints:/{llm_judge}")
        ],
        evaluators="default",
        evaluator_config={'col_mapping': {'inputs': 'question'}}
        )


# COMMAND ----------


