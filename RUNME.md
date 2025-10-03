# How to Run the `biomed_genai` Pipeline End-to-End

This pipeline consists of two major components:
- **Retriever Workflow**: Ingests, curates, chunks, and indexes biomedical literature (e.g., PubMed Central) for vector search.
- **Agent Workflow**: Develops, evaluates, registers, and deploys generative agents that use the indexed biomedical data.

---

## 1. Initial Setup

1. **Clone or Access the Repository**  
   Ensure you have access to the Databricks workspace and have cloned or attached the `biomed_genai` repo.

2. **Configure and Review Environment**  
   - Review and, if needed, update `databricks/_config/config_biomed_genai.yaml` to reflect your environment and resource paths.
   - Ensure you have configured cloud storage and Unity Catalog access for all referenced data assets.

3. **Install Required Libraries**  
   - The setup notebooks (e.g., `retriever/pubmed_wf/_setup/setup_pubmed_wf.py`) will install PyPI dependencies, but ensure your cluster/job runtime supports:
     - `mlflow`
     - `databricks_vectorsearch`
     - `langchain`
     - `unstructured`
     - `html2text`
     - `bs4`
     - `pyyaml`
     - and others as needed per notebook.

---

## 2. Retriever Workflow: Literature Ingestion and Indexing

The retriever workflow is modularized; each notebook represents a pipeline stage.

**You can run these notebooks individually or as an automated multi-task job (recommended for production).**

### Manual Run (for development/testing)

Run in this order:

1. **00_pubmed_wf_config.py**  
   - (Optional) Review configuration and entity/table setup.

2. **01_Metadata_Sync.py**  
   - Synchronizes PubMed article metadata from S3 to a Delta table.

3. **02_Articles_Ingest.py**  
   - Searches for and downloads new PMC articles (XML) by keyword and time window.

4. **03_Curate_Articles.py**  
   - Parses XML files and curates their content/metadata into a structured Delta table.

5. **04_Chunk_Articles_Content.py**  
   - Uses the `unstructured` library to chunk article content for vector search, creating a processed content table.

6. **05_Sync_VectorSearch_Index.py**  
   - Syncs the processed articles Delta table with the Databricks Vector Search index.

7. **06_Create_Sync_Job.py** (Optional for automation)  
   - Creates a Databricks Job to orchestrate steps 1–6 on a schedule.

**Tip:** You can use `scratch.py` for ad hoc inspection and development.

### Automated Run (recommended for production)

- Launch the job defined in `06_Create_Sync_Job.py` (or via the Databricks UI after creating it once).
- This job will run all workflow steps in the correct dependency order.

---

## 3. Agent Workflow: Model Development, Evaluation, and Deployment

This workflow is organized as Databricks notebooks (or .py files) under `databricks/agent/bc_qa_chat/`.

### Steps:

1. **05_RELEASE_biomed_genai.py**  
   - (Governance/Release checkpoint – optional but recommended for documenting release state.)

2. **agent_model/02_01_Candidate_Runs.py**  
   - Validates candidate models are up-to-date with config.

3. **agent_model/02_02_Score_Register.py**  
   - Scores candidate models using evaluation metrics.
   - Registers the best model to the Unity Catalog model registry.
   - Deploys the model as an agent endpoint for review.

4. **agent_model/02_03_Review_App_Feedback.py**  
   - Analyzes human feedback collected from the deployed review app.

5. **agent_model/02_04_Designate_Champion.py**  
   - Compares candidate and production models, promotes champion, and version-controls agent releases.

6. **agent_model/models/.../dbrx_lc_rag.py** or **llama3_lc_rag.py**  
   - Use these for developing/testing specific RAG-based LLM agents for biomedical Q&A, using the indexed literature as retrieval context.

---

## 4. Model Inference and Feedback

- Once an agent is deployed, use the provided review app and endpoint URL for human-in-the-loop evaluation and feedback.
- Update pipeline and evaluation criteria as new insights are gathered.

---

## 5. Maintenance

- Regularly review and update dependencies, configurations, and pipeline logic as new data or requirements arise.
- Use the Databricks Jobs scheduler to automate retriever index refreshes and agent evaluation as needed.

---

## 6. (Optional) Customization and Extension

- Add or modify chunking, parsing, or model logic for your specific biomedical application.
- Extend the workflow with additional data sources or downstream analytics.

---

## References

- [Databricks Vector Search Docs](https://docs.databricks.com/en/generative-ai/vector-search.html)
- [LangChain Docs](https://python.langchain.com/)
- [Databricks MLflow Docs](https://mlflow.org/docs/latest/index.html)