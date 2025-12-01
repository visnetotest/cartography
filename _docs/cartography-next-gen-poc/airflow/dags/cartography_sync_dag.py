from __future__  import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="cartography_sync_dag",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["cartography"],
) as dag:
    # Task to trigger the AWS EC2 intel microservice
    trigger_aws_ec2_intel = BashOperator(
        task_id="trigger_aws_ec2_intel",
        bash_command="echo 'Triggering AWS EC2 Intel Microservice...'",
    )

    # Task to trigger the GCP Storage intel microservice
    trigger_gcp_storage_intel = BashOperator(
        task_id="trigger_gcp_storage_intel",
        bash_command="echo 'Triggering GCP Storage Intel Microservice...'",
    )

    # Task for the graph ingestion service
    # This task would typically be triggered by a message on the NATS stream
    # For this PoC, we'll simulate it as a downstream task
    graph_ingestion = BashOperator(
        task_id="graph_ingestion",
        bash_command="echo 'Running Graph Ingestion Service...'",
    )

    # Define task dependencies
    [trigger_aws_ec2_intel, trigger_gcp_storage_intel] >> graph_ingestion
