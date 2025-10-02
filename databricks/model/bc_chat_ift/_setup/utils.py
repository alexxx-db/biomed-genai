"""
Utility functions for biomed_genai model training pipeline.

This module provides helper functions for:
- Cluster and MLflow operations
- Data processing and formatting
- File I/O operations for synthetic data generation
"""

import json
import pandas as pd
from typing import List, Dict
from databricks.sdk.runtime import dbutils


def get_current_cluster_id() -> str:
    """
    Return the current cluster id to use for fine-tuning operations.
    
    Returns:
        str: Current Databricks cluster ID
        
    See: https://docs.databricks.com/en/large-language-models/foundation-model-training/create-fine-tune-run.html#cluster-id
    """
  return json.loads(dbutils.notebook.entry_point.getDbutils().notebook().getContext().safeToJson())['attributes']['clusterId']


def get_latest_model_version(model_name: str) -> int:
    """
    Get the latest version number of a registered model.
    
    Args:
        model_name (str): Name of the model in Unity Catalog format
        
    Returns:
        int: Latest version number of the model
    """
    from mlflow.tracking import MlflowClient
    mlflow_client = MlflowClient(registry_uri="databricks-uc")
    latest_version = 1
    for mv in mlflow_client.search_model_versions(f"name='{model_name}'"):
        version_int = int(mv.version)
        if version_int > latest_version:
            latest_version = version_int
    return latest_version


def write_jsonl_by_line(responses: List, outfile: str, no_none: bool = True) -> None:
    """
    Write responses to a JSONL file, appending line by line.
    
    Args:
        responses (List): List of response dictionaries to write
        outfile (str): Output file path
        no_none (bool): If True, filter out responses containing None values
    """
    # Write to jsonl line by line
    with open(outfile, 'a+') as out:
        for r in responses:
            if r:
                if no_none:
                    if len(set(r.values()).intersection({None,'None','null'}))==0:
                        jout = json.dumps(r) + '\n'
                else:
                    jout = json.dumps(r) + '\n'
                out.write(jout)


def make_completion_prompt(context: str, question: str, system_prompt: str) -> str:
    """
    Create a formatted prompt for completion-based models.
    
    Args:
        context (str): Background context for the question
        question (str): Question to be answered
        system_prompt (str): System instruction (overridden with default)
        
    Returns:
        str: Formatted prompt string
    """
    system_prompt = "You are a medical expert answering questions about biomedical research. Please answer the question below based on only the provided context. If you do not know, return nothing."
    return f"""{system_prompt}
### Question: {question}
### Context: {context}
### Answer:
"""


def make_chat_prompt(context: str, question: str, answer: str, mistral: bool = False) -> List[Dict[str, str]]:
    """
    Create a chat messages array for chat-based models.
    
    Args:
        context (str): Background context for the question
        question (str): Question to be answered
        answer (str): Expected answer
        mistral (bool): Whether to format for Mistral model (no system role)
        
    Returns:
        List[Dict[str, str]]: Chat messages array with roles and content
    """
    system_prompt = f"""You are a medical expert answering questions about biomedical research. Please answer the question below based on only the provided context. If you do not know, return nothing."""
    user_input = f"""{question}. Answer this question using only this context: 
{context}."""
    if mistral:
        #Mistral doesn't support system prompt
        return [
            {"role": "user", "content": f"{system_prompt} \n{user_input}"},
            {"role": "assistant", "content": answer}]
    else:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": answer}]


@pandas_udf("array<struct<role:string, content:string>>")
def make_chat_udf(content: pd.Series, question: pd.Series, answer: pd.Series) -> pd.Series:
    """
    Pandas UDF to create chat message arrays for multiple rows.
    
    Args:
        content (pd.Series): Series of context strings
        question (pd.Series): Series of questions
        answer (pd.Series): Series of answers
        
    Returns:
        pd.Series: Series of chat message arrays
    """
    return pd.Series([make_chat_prompt(c, q, a) for c, q, a in zip(content, question, answer)])


