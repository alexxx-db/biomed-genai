# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC This notebook is second in a series that **generates synthetic data by data augmentation of seed data** for subsequent chat completion Fine Tuning (FT).
# MAGIC
# MAGIC What this notebook does:
# MAGIC 1. Read in the seed data generated in the previous NB
# MAGIC 2. Create prompt variants by [Evolve-Instruct](https://arxiv.org/abs/2304.12244). Each prompt variant creates a variant of the seed datum
# MAGIC by increasing in depth, complexity etc.
# MAGIC 3. Set up appropriate prompt templates with the prompt variants, seed data and examples in langchain for Few Shot Prompting
# MAGIC 4. Run Few Shot Prompting to evolve the seed data according to the prompt variants

# COMMAND ----------

# MAGIC %pip install langchain_databricks>=0.1.1 langchain-experimental==0.3.3 langchain==0.3.7 langchain-community==0.3.5 langchain-core==0.3.15
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %pip freeze

# COMMAND ----------

import re, os, json
import pyspark.sql
from langchain_databricks import ChatDatabricks
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
import pandas as pd
from typing import List, Type
from typing_extensions import Annotated, TypedDict
from pyspark.sql.functions import col
from pprint import pprint
from _setup.params import *
from _setup.utils import write_jsonl_by_line

# COMMAND ----------

seed_table_name: str = "yen.syn_data_gen.seed"
evolved_table_name: str = "yen.syn_data_gen.evolved"

# TODO: set up volume for these files
outfile: str = 'data/evolved.jsonl'

model_evolve: str = 'databricks-meta-llama-3.1-405b-instruct'
temperature: float = 0.7
max_retries: int = 2
max_concurrency: int = 4

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Read in seed data

# COMMAND ----------

seed_df = spark.table(seed_table_name)
display(seed_df)

# COMMAND ----------

# MAGIC %md
# MAGIC #### Set up class object to collect structured output

# COMMAND ----------

# https://python.langchain.com/docs/integrations/chat/databricks/
class QA_augmented(TypedDict):
#    context: Annotated[str, ..., "Chunks of articles most similar to a topic queried from Vector Store"]
#    question: Annotated[str, ..., "Question provided"]
#    answer: Annotated[str, ..., "Answer to the provided question"]
#    prompt_variant: Annotated[str, ..., "Prompt to re-write question"]
    question_new: Annotated[str, ..., "New re-written question"]
    answer_new: Annotated[str, ..., "New answer to the re-written question"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Prompt Variants
# MAGIC Set up prompt variants inspired by [Evolve-Instruct](https://arxiv.org/abs/2304.12244) to evolve the question and answer with the same context

# COMMAND ----------

prompt_variants = {
    "depth": "Re-write the question to ask in greater depth. The answer should correspondingly explain in greater detail or demonstrate step-by-step reasoning.",
    "complexity": "Re-write the question to be more complex such that the corresponding answers require the use of precise and specific technical terms and defining them as needed.",
    "conditional": "Re-write the question such that its answer is not general and appropriately states exceptions and conditions to demonstrate a deep and nuanced understanding of the question.",
    "diversity": "Draw inspiration from the provided context, question and answer to create a diverse range of questions and answers that are still in the same domain and based on the same context.",
    "paraphrase": "You can paraphrase the question and answer."
}

# COMMAND ----------

# MAGIC %md
# MAGIC #### Cross the seeds with prompt variants such that every seed is paired with every prompt variant

# COMMAND ----------

prompts_df = spark.createDataFrame(
    pd.DataFrame.from_dict(prompt_variants, orient="index", 
                           columns=['prompt']).reset_index())
prompts_df = prompts_df.withColumnRenamed('index','variant')
display(prompts_df)

# COMMAND ----------

seed_promptvariant = seed_df.crossJoin(prompts_df)
display(seed_promptvariant)

# COMMAND ----------

selected_fields = ["id", "context", "question", "answer", "prompt"]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Set up prompt template and chain

# COMMAND ----------

prefix = """You are an experienced linguistics expert for building datasets for large language models. Rewrite and paraphrase the question and answer provided following these rules:
1. The re-written question and answer must still be grounded in the provided context without extra information added.
2. {prompt}

Examples are provided below delimited by ### to show how new questions and answers are re-written.
Examples:
###"""

suffix = """###
Return the re-written question and answer in the fields 'question_new' and 'answer_new' respectively.

Context:
{context}
Question:
{question}
Answer:
{answer}
"""

example_prompt = PromptTemplate.from_template("""Context: {context}
Question: {question}
Answer: {answer}
Question_new: {question_new}
Answer_new: {answer_new}""")

# COMMAND ----------

# MAGIC %md
# MAGIC #### Set up examples for Few Shot Prompting and have them evolve by the prompt variant

# COMMAND ----------

examples = dict()
examples['depth'] = [{"context": "study, reconstruction timing did not show a significant association with\nbreast complications, and the ESTRO-ACROP target volume delineation method did\nnot aff[...]",
"question": "What are the advantages of the new ESTRO-ACROP guideline?",
"answer": "ESTRO-ACROP has dosimentric benefits, minimizing radiotherapy-induced adverse events such as radiation pneumonitis and radiation fibrosis and unnecessary radiation exposure to cardiopul[...]
"prompt_variant": "Re-write the question to ask in greater depth. The answer should correspondingly explain in greater detail or demonstrate step-by-step reasoning.",
"question_new": "Explain the advantages of the new ESTRO-ACROP guideline",
"answer_new": "Because ESTRO-ACROP uses modern volume-based planning techniques, it has dosimentric advantages, minimizing radiation exposure to cardiopulmonary organs, such as the heart, left ve[...]
},
# ... (other examples for each variant as in the code)
]

# ... (examples for 'complexity', 'conditional', 'diversity', 'paraphrase' not shown for brevity)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Evolve the seed data by Few Shot Prompting
# MAGIC Evolve the Q&A by one prompt variant at a time. Checkpoint augmented data every x inputs to .jsonl

# COMMAND ----------

def batch_structured_llm_with_checkpoints(df: pyspark.sql.DataFrame, selected_fields: List[str],
                                          structured_class: Type[QA_augmented],
                                          prompt_variants: dict, split_col: str,
                                          llm: Type[BaseChatModel],
                                          outfile: str, ans: List,
                                          save_every: int = 5, concurrency: int = 5, retries: int = 2,
                                          verbose: bool = False, debug_inputs: str = None) -> List:
    for k,v in prompt_variants.items():
        # Set up chain for batch inference
        prompt = FewShotPromptTemplate(
                examples=examples.get(k),
                example_prompt=example_prompt,
                input_variables=selected_fields,
                prefix=prefix,
                suffix=suffix)
        print(f'Evolving Q&A by {k} prompt...')
        if verbose:
            print(prompt.format_prompt(prompt_variant=v, context='<context>',
                                       question='<question>', answer='<answer>').text)
        structured_llm = llm.with_structured_output(structured_class)
        chain = prompt | structured_llm
        inputs = df.where(col(split_col)==k) \
                .select(*selected_fields) \
                .dropDuplicates() \
                .toPandas().to_dict("records")

        # batch run every x inputs
        for i in range(0, len(inputs), save_every):
            end = i + save_every
            subbatch = inputs[i:end]
            print(f"Evolving {i}th Q&A")
            # For debugging dupes
            if debug_inputs:
                write_jsonl_by_line(subbatch, debug_inputs)
            if verbose:
                print(f"Original question {subbatch[0].get('question')}")
            try:
                responses = chain.with_retry(stop_after_attempt=retries) \
                    .batch(subbatch, config={"max_concurrency": concurrency})

                # Store the context, original question and answer in the response dictionary (but not passed into the LLM unnecessarily)
                for i, r in zip(inputs, responses):
                    if r:
                        for k,v in i.items():
                            r[k] = v
                        if verbose:
                            pprint(r)

                responses = [r for r in responses if r and len(set(r.values()).intersection({None,'None','null'}))==0]
                # Write to jsonl after every x inputs
                write_jsonl_by_line(responses, outfile)
                ans.extend(responses)

            except Exception as e:
                print(f"Exception of type {type(e)}.\n{e}")

# COMMAND ----------

llm = ChatDatabricks(endpoint=model_evolve, temperature=temperature)

batches = []
batch_structured_llm_with_checkpoints(
    df=seed_promptvariant, selected_fields=selected_fields,
    structured_class=QA_augmented,
    prompt_variants=prompt_variants, split_col="variant",
    llm=llm, outfile=outfile, ans=batches,
    save_every=5, concurrency=max_concurrency, retries=max_retries, 
    verbose=False, debug_inputs="data/inputs.jsonl"
)

# COMMAND ----------

len(batches)

# COMMAND ----------

# Option 1 to save evolved data: Read from batches in memory
evolved_df = spark.createDataFrame(pd.DataFrame.from_records(batches))

# Option 2 to save evolved data: Read in from jsonl (if cluster stopped)
#evolved_df = spark.createDataFrame(pd.read_json("data/evolved.jsonl", lines=True))
display(evolved_df)

# COMMAND ----------

evolved_df.na.drop(how='any', subset=["context", "question", "answer", "question_new", "answer_new"]) \
    .dropDuplicates() \
    .write.mode("overwrite") \
    .saveAsTable(evolved_table_name)
display(spark.table(evolved_table_name))

# COMMAND ----------

evolved_df.count()

# COMMAND ----------

# For debugging
inputs_df = spark.createDataFrame(pd.read_json("data/inputs.jsonl", lines=True))
display(inputs_df)