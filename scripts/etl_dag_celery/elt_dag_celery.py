from __future__ import annotations

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pendulum
from airflow import models
from airflow.contrib.operators import kubernetes_pod_operator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.operators.python import PythonOperator
from airflow import DAG
from datetime import datetime, timedelta
from airflow.contrib.operators import kubernetes_pod_operator
from kubernetes.client import models as k8s

default_args = {
    'owner': 'Damavis',
    'start_date': datetime(2020, 5, 5),
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}



vol1 = k8s.V1VolumeMount(name='test-volume', mount_path='/opt/airflow/dags')
volume = k8s.V1Volume(
            name='test-volume',
            persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name='airflow-dags'),
    )
with DAG('etl_dag',
         default_args=default_args,
         schedule_interval=None) as dag:
             
    r_base = kubernetes_pod_operator.KubernetesPodOperator(
        namespace='airflow',
        image="harbor-atx.us.int.sonichealthcare/airflow/r-base:latest",
        volumes=[volume],
        volume_mounts=[vol1],
        #cmds=["sleep"],
        #arguments=["240"],
        cmds=["Rscript /opt/airflow/dags/repo/scripts/adcsf-main/ADCSF.R"],
        #arguments=["/opt/airflow/dags/repo/scripts/adcsf-main/ADCSF.R"],
        labels={"r-base": "r-base"},
        name="r-base",
        task_id="extract-tranform",
        get_logs=True,
        env_vars={"TZ":"America/Chicago"},
    )
