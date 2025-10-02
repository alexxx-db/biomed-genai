# biomed_genai

**Medallion Architecture & Models for Biomedical Articles in GenAI Applications**

---

## Overview

`biomed_genai` is a modular Python package designed to power advanced GenAI applications in the biomedical domain. It leverages state-of-the-art technologies for retrieval-augmented generation (RAG), question-answering, and model deployment, with a focus on biomedical literature such as PubMed and PMC articles.

The project follows a layered ("medallion") architecture, integrating model training, deployment, governance, and information retrieval in a highly extensible structure. It is built to run seamlessly on Databricks environments but is general enough for broader research and production use.

---

## Directory Structure

```
biomed_genai/
├── agent/
│   ├── bc_qa_chat/
│   │   └── agent_bc_qa_chat.py
│   ├── eval.py
│   ├── viz_agent_deploy.py
│   └── viz_governance.py
├── config.py
├── model/
│   └── bc_chat_ift/
│       └── model_bc_chat_ift.py
└── retriever/
    └── pubmed_wf/
        ├── pmc.py
        ├── vector_search.py
        ├── viz_table.py
        ├── viz_workflow.py
        └── workflow_pubmed_wf.py
requirements.txt
setup.py
```

- **agent/**: Components for agent orchestration, evaluation, and visualization.
- **model/**: Model definitions, especially for instruction fine-tuning and chat-based models.
- **retriever/**: Biomedical literature workflows, including vector search and workflow visualization.
- **config.py**: Centralized configuration utilities.

---

## Key Features

- **Biomedical RAG Pipelines**: End-to-end workflows for retrieval and generation using large language models (LLMs) and vector search.
- **Evaluation & Visualization**: Tools to visualize agent deployments, governance, and workflow progress.
- **Extensible Agent Framework**: Modular agents for biomedical Q&A, chat, and custom workflows.
- **Modeling Utilities**: Instruction tuning, chat model integration, and model deployment support.
- **Rich Integration**: Built to leverage Databricks, MLflow, and Databricks Vector Search.

---

## Installation

### Requirements

- Python 3.10+
- Databricks environment recommended (for full feature support)

### Dependencies

All dependencies are listed in `requirements.txt` and will be installed automatically.

To install locally for development:

```bash
cd python
pip install -e .
```

---

## Usage

### 1. Importing the Package

```python
from biomed_genai.agent.bc_qa_chat.agent_bc_qa_chat import BiomedicalQAAgent
from biomed_genai.model.bc_chat_ift.model_bc_chat_ift import ChatIFTModel
from biomed_genai.retriever.pubmed_wf.vector_search import PubMedVectorSearch
```

### 2. Running a Biomedical Q&A Agent

```python
agent = BiomedicalQAAgent(config_path="path/to/config.yaml")
response = agent.answer_question("What are the latest findings on CRISPR in cancer therapy?")
print(response)
```

### 3. Vector Search on PubMed

```python
retriever = PubMedVectorSearch(index_path="data/pubmed_index")
results = retriever.search("genome editing in rare diseases")
for doc in results:
    print(doc['title'], doc['snippet'])
```

### 4. Model Training (Instruction Fine-Tuning)

```python
from biomed_genai.model.bc_chat_ift.model_bc_chat_ift import ChatIFTModel

model = ChatIFTModel(base_model="databricks/dolly-v2-12b")
model.train(train_data_path="data/biomedical_qa.jsonl", output_dir="models/biomed_ift/")
```

---

## Submodule Deep Dive

### agent/

- **bc_qa_chat/agent_bc_qa_chat.py**: Main entry point for biomedical QA agents. Implements prompt engineering, dialogue management, and tool-calling for LLM-based Q&A.
- **eval.py**: Evaluation routines for agent performance, including metrics like accuracy, BLEU, and domain-specific criteria.
- **viz_agent_deploy.py**: Visualization tools for deployment status and agent lifecycles.
- **viz_governance.py**: Visualizes governance and compliance aspects of GenAI agents.

### model/

- **bc_chat_ift/model_bc_chat_ift.py**: Abstractions for chat-based instruction fine-tuning of LLMs. Supports custom datasets and various backbone models.

### retriever/pubmed_wf/

- **pmc.py**: Utilities for parsing and processing PMC (PubMed Central) articles.
- **vector_search.py**: Implements vector-based information retrieval using Databricks Vector Search.
- **viz_table.py**: Visualizes tabular results from PubMed workflows.
- **viz_workflow.py**: Interactive visualization of retrieval workflows.
- **workflow_pubmed_wf.py**: End-to-end workflow definitions for PubMed-based RAG pipelines.

### config.py

Centralizes all configuration (paths, credentials, runtime options) for reproducibility and ease of deployment.

---

## Development

### Editable Install

```bash
pip install -e .
```

### Testing

> *(Add your testing framework instructions here, e.g., pytest, unittest, or Databricks notebook testing.)*

```bash
pytest tests/
```

### Linting & Code Quality

```bash
flake8 biomed_genai/
mypy biomed_genai/
```

---

## Contributing

1. Fork the repo and create your feature branch (`git checkout -b feature/fooBar`)
2. Commit your changes (`git commit -am 'Add some fooBar'`)
3. Push to the branch (`git push origin feature/fooBar`)
4. Open a pull request

---

## License

DATABRICKS (see setup.py for details)

---

## Authors

- Alexandre Barreto (`alex.barreto@entrada.ai`)

---

## Acknowledgments

- Built leveraging Databricks/GenAI infrastructure
- Biomedical datasets courtesy of PubMed and PMC

---

## Related Projects

- [Databricks GenAI Inference](https://github.com/databricks/databricks-genai-inference)
- [MLflow](https://mlflow.org/)

---

*For more information, see the docstrings in each module and the official Databricks documentation.*