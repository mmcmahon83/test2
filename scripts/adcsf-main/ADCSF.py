#all dependencies and imports
from __future__ import annotations

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pendulum
from airflow import models
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.operators.python import PythonOperator
from airflow.contrib.operators import kubernetes_pod_operator
from kubernetes.client import models as k8s
from pathlib import Path

# mvm mount information and DAGID
# mvm load_dotenv()
# mvm from docker.types import Mount 
# mvm ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
# mvm DAG_ID = "ADCSF" #update this, this will be the DAG name in Airflow


#mount information and DAGID
dotenv_path = Path('/opt/airflow/dags/repo/script/.env')
load_dotenv(dotenv_path=dotenv_path)
from docker.types import Mount 
ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
DAG_ID = "ADCSF" #update this, this will be the DAG name in Airflow

#variable assignment
local_tz = pendulum.timezone("America/Chicago") #sets timezone to CST
reportID = os.getenv(f"{DAG_ID}ri") 
emaillist = os.getenv(f"{DAG_ID}el") 

def report_failure(context):
    send_email = EmailOperator(task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to= os.getenv('Callbackelist'), 
         subject=f"{reportID}{os.getenv('Callbacksubject')}",
         html_content="Report Failed",)
    send_email.execute(context)

with models.DAG(
    DAG_ID,
    schedule= os.getenv(f"{DAG_ID}sc"),
    start_date=datetime(2021, 1, 1, tzinfo=local_tz),
    default_args = {
        "on_failure_callback": report_failure },
    catchup=False,
    tags=["docker","daily","Nielsa","Production"],
) as dag:

# Mount volume for kubernetes_pod_operator  
    vol1 = k8s.V1VolumeMount(name='test-volume', mount_path='/opt/airflow/dags')
    volume = k8s.V1Volume(
            name='test-volume',
            persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name='airflow-dags'),
    )
 # kubernetes_pod_operator that runs script, returns jinja that can be read to get dynamic file name           
    script = kubernetes_pod_operator.KubernetesPodOperator(
        namespace='airflow',
        image="harbor-atx.us.int.sonichealthcare/airflow/r-base:latest",
        volumes=[volume],
        volume_mounts=[vol1],
        arguments=['Rscript', '/opt/airflow/dags/repo/scripts/adcsf-main/ADCSF.R'],
        labels={"r-base": "r-base"},
        name="adcsf",
        task_id="script_task",
        get_logs=True,
        env_vars={"TZ":"America/Chicago"},
        do_xcom_push=True,
    )
        
    #operator that will convert jinga into key value pair for dynamic file produced in t2
    jin = PythonOperator(
        task_id="render_output",
        python_callable=lambda **c: c['task'].render_template(content=c['ti'].xcom_pull(task_ids=script.task_id),context=c),
        provide_context=True,
        dag=dag
    )

    #email file 
    email = EmailOperator(
         task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to="mmcmahon@sonichealthcareusa.com",
         subject=f"{reportID}",
         html_content=f"Attached is the {reportID}. Please contact the Data Science Department at cpldatascience@cpllabs.com if there are any issues. Have a good day!",
         files=['{{ ti.xcom_pull(task_ids="render_output",key="filename") }}'] #key  that identifies file
         )


    #Function to delete file that was imported from outside server
    def delete_files(**kwargs):
        ti = kwargs['ti']
        filename=ti.xcom_pull(task_ids="render_output",key="filename")
        os.remove(filename) #created file to remove
    #task to delete file imported from outside server
    dfiles = PythonOperator(
        task_id='delete_files_task',
        python_callable=delete_files,
        provide_context=True,
        dag=dag
        )
    (
        # TEST BODY
        script >> jin >> email >> dfiles
    )
