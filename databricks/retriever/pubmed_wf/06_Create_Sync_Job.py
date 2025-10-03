# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # Create Sync Job [OPTIONAL]
# MAGIC
# MAGIC **Objective:** Schedule and automate the full retriever workflow as a multi-task Databricks job.
# MAGIC
# MAGIC **Setup:** `%run ./_setup/setup_pubmed_wf $SHOW_TABLE=false $SHOW_WORKFLOW=true`
# MAGIC
# MAGIC - Demonstrates job cluster/task config for Azure (extend for AWS/GCP as needed)
# MAGIC - Defines dependencies and schedule for end-to-end workflow

# COMMAND ----------

# [OPTIONAL] Define Job Cluster (currently only Azure, add AWS/GCP as needed)
from databricks.sdk.service.jobs import JobCluster
from databricks.sdk.service.compute import ClusterSpec, AzureAttributes, AzureAvailability, DataSecurityMode, RuntimeEngine

def get_job_cluster():
    cloud = spark.conf.get("spark.databricks.cloudProvider")
    if cloud == "Azure":
        return JobCluster(
            job_cluster_key="BioMed_VS_Sync",
            new_cluster=ClusterSpec(
                azure_attributes=AzureAttributes(
                    first_on_demand=1,
                    availability=AzureAvailability(value="ON_DEMAND_AZURE"),
                    spot_bid_max_price=-1
                ),
                cluster_name="",
                data_security_mode=DataSecurityMode(value="SINGLE_USER"),
                node_type_id="Standard_D4ds_v5",
                num_workers=0,
                runtime_engine=RuntimeEngine(value="PHOTON"),
                spark_conf={'spark.master': 'local[*, 4]'},
                spark_version='14.3.x-scala2.12'
            )
        )
    elif cloud == "AWS":
        pass  # TODO: Add AWS cluster config
    elif cloud == "GCP":
        pass  # TODO: Add GCP cluster config

# COMMAND ----------

# Define Workflow Tasks and Dependencies
from databricks.sdk.service.jobs import Task, NotebookTask, TaskDependency
from databricks.sdk.service.compute import Library, PythonPyPiLibrary
import os

workflow_dir = os.path.dirname(dbutils.entry_point.getDbutils().notebook().getContext().notebookPath().getOrElse(None))

tasks = [
    Task(
        task_key='01_Metadata_Sync',
        job_cluster_key="BioMed_VS_Sync",
        libraries=[
            Library(pypi=PythonPyPiLibrary(package='pyyaml==6.0')),
            Library(pypi=PythonPyPiLibrary(package='mlflow==2.15.1')),
            Library(pypi=PythonPyPiLibrary(package='databricks_vectorsearch==0.39'))
        ],
        notebook_task=NotebookTask(notebook_path=os.path.join(workflow_dir, "01_Metadata_Sync"))
    ),
    Task(
        task_key='02_Articles_Ingest',
        job_cluster_key="BioMed_VS_Sync",
        libraries=[
            Library(pypi=PythonPyPiLibrary(package='pyyaml==6.0')),
            Library(pypi=PythonPyPiLibrary(package='mlflow==2.15.1')),
            Library(pypi=PythonPyPiLibrary(package='databricks_vectorsearch==0.39'))
        ],
        notebook_task=NotebookTask(notebook_path=os.path.join(workflow_dir, "02_Articles_Ingest")),
        depends_on=[TaskDependency(task_key='01_Metadata_Sync')]
    ),
    Task(
        task_key='03_Curate_Articles',
        job_cluster_key="BioMed_VS_Sync",
        libraries=[
            Library(pypi=PythonPyPiLibrary(package='pyyaml==6.0')),
            Library(pypi=PythonPyPiLibrary(package='mlflow==2.15.1')),
            Library(pypi=PythonPyPiLibrary(package='databricks_vectorsearch==0.39'))
        ],
        notebook_task=NotebookTask(notebook_path=os.path.join(workflow_dir, "03_Curate_Articles")),
        depends_on=[TaskDependency(task_key='02_Articles_Ingest')]
    ),
    Task(
        task_key='04_Chunk_Articles_Content',
        job_cluster_key="BioMed_VS_Sync",
        libraries=[
            Library(pypi=PythonPyPiLibrary(package='pyyaml==6.0')),
            Library(pypi=PythonPyPiLibrary(package='mlflow==2.15.1')),
            Library(pypi=PythonPyPiLibrary(package='databricks_vectorsearch==0.39')),
            Library(pypi=PythonPyPiLibrary(package='unstructured==0.15.1')),
            Library(pypi=PythonPyPiLibrary(package='html2text==2024.2.26')),
            Library(pypi=PythonPyPiLibrary(package='nltk==3.7'))
        ],
        notebook_task=NotebookTask(notebook_path=os.path.join(workflow_dir, "04_Chunk_Articles_Content")),
        depends_on=[TaskDependency(task_key='03_Curate_Articles')]
    ),
    Task(
        task_key='05_Sync_VectorSearch_Index',
        job_cluster_key="BioMed_VS_Sync",
        libraries=[
            Library(pypi=PythonPyPiLibrary(package='pyyaml==6.0')),
            Library(pypi=PythonPyPiLibrary(package='mlflow==2.15.1')),
            Library(pypi=PythonPyPiLibrary(package='databricks_vectorsearch==0.39')),
            Library(pypi=PythonPyPiLibrary(package='langchain_community==0.2.7'))
        ],
        notebook_task=NotebookTask(notebook_path=os.path.join(workflow_dir, "05_Sync_VectorSearch_Index")),
        depends_on=[TaskDependency(task_key='04_Chunk_Articles_Content')]
    )
]

# COMMAND ----------

# Create Scheduled Job
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import Job, Format, CronSchedule, PauseStatus, JobEditMode, JobRunAs, QueueSettings

def get_or_create_job(job_name: str) -> Job:
    client = WorkspaceClient()
    user = dbutils.notebook.entry_point.getDbutils().notebook().getContext().tags().apply('user')
    try:
        job: Job = next(client.jobs.list(expand_tasks=True, name=job_name))
        displayHTML(f'<a href=jobs/{job.job_id}>{job_name}</a> already exists.')
    except StopIteration:
        job_response = client.jobs.create(
            name=job_name,
            description="BioMed GenAI Workflow Synchronization",
            job_clusters=[get_job_cluster()],
            format=Format(value="MULTI_TASK"),
            tasks=tasks,
            schedule=CronSchedule(
                quartz_cron_expression='1 0 5 ? * Sun',
                timezone_id='America/New_York',
                pause_status=PauseStatus("UNPAUSED")
            ),
            edit_mode=JobEditMode(value="EDITABLE"),
            run_as=JobRunAs(user_name=user),
            queue=QueueSettings(enabled=True),
            max_concurrent_runs=1,
            timeout_seconds=0
        )
        job: Job = client.jobs.get(job_response.job_id)
        displayHTML(f'<a href=jobs/{job.job_id}>{job_name}</a> has been created.')
    return job

job: Job = get_or_create_job(job_name="BioMed_VS_Sync")