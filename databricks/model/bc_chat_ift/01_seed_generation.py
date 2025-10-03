# Databricks notebook source
# MAGIC %md
# MAGIC This notebook is first in a series that **generates synthetic seed data** for subsequent chat completion Fine Tuning (FT).
# MAGIC
# MAGIC What this notebook does:
# MAGIC 1. Sample document chunks. Using each chunk as context, generate a question that could be posed.
# MAGIC 2. Generate an answer to the question using only the chunk as a source.
# MAGIC 3. Steps 1-2 are done by Few Shot Prompting
# MAGIC 4. Periodically save the context, question, answer and source in a jsonl and finally a spark table
# MAGIC
# MAGIC
# MAGIC **NOTE**: Need to look at reference code at [synthetic-simulator](https://github.com/epec254/synthetic-simulator) and where if possible use databricks synthetic genration approach.

# COMMAND ----------

# MAGIC %pip install langchain==0.3.7 langchain-community==0.3.5 langchain_core==0.3.15 langchain_databricks>=0.1.1
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %pip freeze

# COMMAND ----------

import re, os, json
import pandas as pd
from pandas.errors import EmptyDataError
from langchain_databricks import ChatDatabricks
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_core.runnables.base import RunnableSequence
from typing import Optional, List
#from pydantic import BaseModel, Field
from typing import Type
from typing_extensions import Annotated, TypedDict
from pyspark.sql.functions import col, size, split
from _setup.params import *
from _setup.utils import write_jsonl_by_line

# COMMAND ----------

min_chunk_len: int = 50
chunk_table: str = "biomed_genai.processed.articles_content"
model_seed: str = 'databricks-meta-llama-3.1-405b-instruct'
temperature: float = 0.7
max_retries: int = 2
max_concurrency: int = 4

seed_table_name: str = "yen.syn_data_gen.seed"
outfile = "data/seed.jsonl"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Sample document chunks

# COMMAND ----------

df = spark.table(chunk_table)
display(df)

# COMMAND ----------

chunk_sample =df.where(size(split(col('content'), '\W'))>=min_chunk_len) \
    .withColumnRenamed('content', 'context') \
    .select(['id','context']) \
    .sample(0.02, seed=0)
inputs = chunk_sample.toPandas().to_dict(orient='records')
len(inputs)

# COMMAND ----------

display(chunk_sample)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Few Shot Prompting (FSP)
# MAGIC #### Curate a list of examples for FSP

# COMMAND ----------

examples_gen = [   
{"context": "1 Introduction\n\nBreast cancer (BRCA) is one of the most common malignant tumors in women\nworldwide and a major cause of cancer-related deaths among women globally\n(Sung et al., 20[...]",
"question": "What cancer antigen is used for detection of breast cancer?",
"answer": "CA 15-3. It is usually significantly elevated in the serum of late-stage breast cancer patients."},
{"context": "study, reconstruction timing did not show a significant association with\nbreast complications, and the ESTRO-ACROP target volume delineation method did\nnot affect complications in e[...]",
"question": "What are the advantages of the new ESTRO-ACROP guideline?",
"answer": "ESTRO-ACROP has dosimentric benefits, minimizing radiotherapy-induced adverse events such as radiation pneumonitis and radiation fibrosis and unnecessary radiation exposure to cardiopul[..."}
]

# COMMAND ----------

examples_judge = {"context": "1 Introduction\n\nBreast cancer (BRCA) is one of the most common malignant tumors in women\nworldwide and a major cause of cancer-related deaths among women globally[...]",
"question": "What cancer antigen is used for detection of breast cancer?",
"answer": "CA 15-3. It is usually significantly elevated in the serum of late-stage breast cancer patients.",
"domain_specificity": True,
"validity": True,
"relevance": True,
"correctness": True},
{"context": "1 Introduction\n\nBreast cancer (BRCA) is one of the most common malignant tumors in women\nworldwide and a major cause of cancer-related deaths among women globally\n(Sung et al., 20[...]",
"question": "What cancer antigen is used for detection of breast cancer?",
"answer": "CA 123. It is usually significantly elevated in the serum of late-stage breast cancer patients.",
"domain_specificity": True,
"validity": True,
"relevance": True,
"correctness": False},
{"context": "1 Introduction\n\nBreast cancer (BRCA) is one of the most common malignant tumors in women\nworldwide and a major cause of cancer-related deaths among women globally\n(Sung et al., 2[...]",
"question": "What cancer antigen is used for detection of skin cancer?",
"answer": "CA 15-3. It is usually significantly elevated in the serum of late-stage breast cancer patients.",
"domain_specificity": False,
"validity": True,
"relevance": False,
"correctness": False},
{"context": 'ref-type="bibr" rid="CIT0290">2017)  \nYes| ↓ systolic and diastolic blood pressure, ↔ arterial stiffness| Men with\nprediabetes, RT, n = 16| TRF (early)| (Sutton et al. 2018)  [...]',
"question": "How many men have prediabetes?",
"answer": "16",
"domain_specificity": False,
"validity": False,
"relevance": True,
"correctness": True}

# COMMAND ----------

# MAGIC %md
# MAGIC #### Set up a class for langchain structured output
# MAGIC Note that ChatDatabricks so far (v0.1.1) supports TypedDict, JSON but not pydantic schemas

# COMMAND ----------

# https://python.langchain.com/docs/integrations/chat/databricks/
class QA_context(TypedDict):
    context: Annotated[str, ..., "Chunks of articles most similar to a topic queried from Vector Store"]
    question: Annotated[str, ..., "Question generated"]
    answer: Annotated[str, ..., "Generated answer to the question"]

# COMMAND ----------

class QA_quality(TypedDict):
    domain_specificity: Annotated[bool, ..., "context is about breast cancer in human patients"]
    validity: Annotated[bool, ..., "context is not about numbers, a table, a figure caption, equation or code, or acknowledging authors' contributionsfor framing a question"]
    relevance: Annotated[bool, ..., "question is relevant to the context"]
    correctness: Annotated[bool, ..., "answer reasonably answers the question and relies only on the context and not contain links or extra information"]

# COMMAND ----------

# MAGIC %md
# MAGIC Set up the appropriate prompts for both the prompt to generate Q&A and then to judge it

# COMMAND ----------

prefix_gen = """Given the context below, generate a question that can be answered following these rules:
Rules:
1. The context should be 1-3 paragraphs of text from a medical journal. Otherwise, ignore and return None.
2. If the context is mostly about numbers, a recipe listing reagents, a table, a figure caption, equation or code, ignore and return None. 
3. If the context is mostly about acknowledging authors' contributions, ignore and return None.
4. The question should be fully answered from the given context.
5. The question should be reasonably understood and answerable by a trained scientist.
6. Do not ask highly contextual questions that require referencing to a specific study, for example "What are the main findings of the study" or "how many patients are enrolled in the study".  
7. Do not use phrases like 'provided context', etc. in the question.
8. Avoid framing questions using the word "and" that can be decomposed into more than one question.
9. The question should not be longer than 15 words.
10. The answer should be about 10-80 words long.
11. The question should be about breast cancer and not broadly about medical research, such as "what is a cell" or "what is an observational study".
12. The answer to the question should be based on the given context, not contain any links or extra information.
13. Be as precise as possible with answering the question.

Some examples are provided below.
Examples:
"""

suffix_gen = """To generate the question, first identify the most important or relevant part of the context. Then frame a question around that part that satisfies all the rules above and return t[...]
Context:
{context}
"""

example_prompt_gen = PromptTemplate.from_template(
"""Context: {context}
Question: {question}
Answer: {answer}""")

# COMMAND ----------

prefix_judge = """Given the context, question and corresponding answer, critique in terms of:
1. Domain-specificity: that the context is about medical science.
2. Validity: that the context is not about numbers, a table, a figure caption, equation or code, or acknowledging authors' contributions.
3. Relevance: that the question is relevant to the context
4. Correctness: the answer reasonably answers the question and relies only on the context and not contain links or extra information.

Return only True/False to the above 4 fields
"""

suffix_judge = """To generate the question, first identify the most important or relevant part of the context and return that in the "source" field. Then frame a question around that part that sa[...]
Context:
{context}

Question:
{question}

Answer:
{answer}
"""

example_prompt_judge = PromptTemplate.from_template(
    """Context: {context}
    Question: {question}
    Answer: {answer}""")

# COMMAND ----------

# MAGIC %md
# MAGIC Set up the LLM and chain

# COMMAND ----------

def create_chain(llm, prefix, suffix,
                 examples, example_prompt,
                 input_var, structured_class):
    prompt = FewShotPromptTemplate(
        examples=examples,
        example_prompt=example_prompt,
        input_variables=input_var,
        prefix=prefix,
        suffix=suffix)
    structured_llm = llm.with_structured_output(structured_class)
    chain = prompt | structured_llm
    return chain, prompt

# COMMAND ----------

llm = ChatDatabricks(endpoint=model_seed, temperature=temperature)

# COMMAND ----------

# Chain to generate Q&A from context
chain_gen, prompt_gen = create_chain(llm, prefix_gen, suffix_gen,
                 examples_gen, example_prompt_gen,
                 input_var=["context"],
                 structured_class=QA_context)
print(prompt_gen.format_prompt(context="<context>").text)

# COMMAND ----------

# Chain to judge Q&A from context
chain_judge, prompt_judge = create_chain(llm, prefix_judge, suffix_judge,
                 examples=examples_judge,
                 example_prompt=example_prompt_judge,
                 input_var=["context", "question", "answer"],
                 structured_class=QA_quality)
print(prompt_judge.format_prompt(context="<context>",
                                 question="<question>",
                                 answer="<answer>").text)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Invocation
# MAGIC Test invocation with 1-3 inputs

# COMMAND ----------

# Invoke with single input
# response = chain_gen.invoke(inputs[0])

# View output
# response.dict() #pydantic
# response #TypedDict

# Batch invocation with multiple inputs
responses = chain_gen.with_retry(stop_after_attempt=max_retries) \
    .batch(inputs[0:10], config={"max_concurrency": max_concurrency})
responses

# COMMAND ----------

responses_wo_none = [r for r in responses if r and len(set(r.values()).intersection({None,'None','null'})) == 0]
critiques = chain_judge.with_retry(stop_after_attempt=max_retries) \
    .batch(responses_wo_none, config={"max_concurrency": max_concurrency})
critiques

# COMMAND ----------

# MAGIC %md
# MAGIC #### Concurrent batch invocation

# COMMAND ----------

# Checkpoint every few inputs
def generate_seed_data(inputs: List[dict], ans: List[dict],
                       chain_gen: Type[RunnableSequence], chain_judge: Type[RunnableSequence],
                       outfile: str = 'data/seed.jsonl', 
                       save_every: int = 10, 
                       concurrency: int = 2, retries: int = 2,
                       debug_inputs: str = None):
  for i in range(0, len(inputs), save_every):
    try:
      end = i + save_every
      subset = inputs[i:end]
      print(f"Generating Q & A for {i}th context")
      # For debugging
      write_jsonl_by_line(subset, debug_inputs, no_none=False)
      responses = chain_gen.with_retry(stop_after_attempt=retries) \
        .batch(subset, config={"max_concurrency": concurrency})

      # Ensure the full context is used but not unneccessarily sent to and fro into llm
      responses_wo_none = []
      for s, r in zip(subset, responses):
        if isinstance(r, dict) \
        and isinstance(s, dict) \
        and len(set(r.values()).intersection({None,'None','null'}))==0:
          response_dict = {'id': s.get('id'),
                        'context': s.get('context'),
                        'question': r.get('question'),
                        'answer': r.get('answer')}
          responses_wo_none.append(response_dict)
      # Ensure all None are removed
      responses_wo_none = [r for r in responses_wo_none if r \
        and len(set(r.values()).intersection({None,'None','null'}))==0]
      valid_responses = responses_wo_none.copy()

      if chain_judge and responses_wo_none:
        critiques = chain_judge.with_retry(stop_after_attempt=retries) \
          .batch(responses_wo_none, config={"max_concurrency": concurrency})
        critique_mask = [all(c.values()) for c in critiques if c]
        valid_responses = [r for r, c in zip(responses_wo_none, critique_mask) if c]
        #print(valid_responses)

    except Exception as e:
      print(f"Exception of type {type(e)}.\n{e}")

    # Write to jsonl after every x inputs
    write_jsonl_by_line(valid_responses, outfile, no_none=True)
    ans.extend(valid_responses)

# COMMAND ----------

# TODO: Save to UC volume
ans = []
generate_seed_data(inputs, ans,
                   chain_gen, chain_judge,
                   outfile='data/seed.jsonl',
                   save_every=5, concurrency=max_concurrency, retries=max_retries,
                   debug_inputs="data/inputs_to_seed.jsonl")

# COMMAND ----------

len(ans)

# COMMAND ----------

# Option 1 to save seed data: Read from ans in memory
seed_df = spark.createDataFrame(pd.DataFrame.from_records(ans))

# Option 2 to save seed data: Read in from jsonl (if cluster stopped)
#seed_df = spark.createDataFrame(pd.read_json(outfile, lines=True))
display(seed_df.select(["id","context"]).orderBy("context"))

# COMMAND ----------

seed_df.na.drop(how='any', subset=["context", "question", "answer"]) \
    .dropDuplicates() \
    .write.mode("overwrite") \
    .saveAsTable(seed_table_name)
display(spark.table(seed_table_name))

# COMMAND ----------

input_df = spark.createDataFrame(pd.read_json("data/inputs_to_seed.jsonl", lines=True))
display(input_df.orderBy("context"))