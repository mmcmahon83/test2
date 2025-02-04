from airflow import DAG
from datetime import datetime, timedelta
from airflow.contrib.operators import kubernetes_pod_operator

default_args = {
    'owner': 'Damavis',
    'start_date': datetime(2020, 5, 5),
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}

with DAG('etl_dag',
         default_args=default_args,
         schedule_interval=None) as dag:

    test-work = kubernetes_pod_operator.KubernetesPodOperator(
        namespace='airflow',
        # image="python:3.7-slim",
        image="harbor-atx.us.int.sonichealthcare/airflow/r-base:latest",
        #image="python:3.8-slim-buster",
        # image_pull_secrets=regcred-atx,
        #image_pull_secrets=('secret'),
        #image_pull_secrets=[k8s.V1LocalObjectReference('regcred-atx')],
        # namespace="airflow",
        # force_pull=True,
        cmds=["sleep"],
        arguments=["200"],
        labels={"foo": "bar"},
        name="extract-tranform",
        task_id="extract-tranform",
        get_logs=True
    )

    test-work
