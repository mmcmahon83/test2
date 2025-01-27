from __future__ import annotations

import os
from dotenv import load_dotenv
import pendulum
from datetime import datetime, timedelta

from airflow import models
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.operators.python import PythonOperator
from docker.types import Mount 

load_dotenv()
ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
DAG_ID = "stxcl_critical_potassiums"
reportID = os.getenv(f"{DAG_ID}ri") 
emaillist = os.getenv(f"{DAG_ID}el")   

local_tz = pendulum.timezone("America/Chicago")
def report_failure(context):
    send_email = EmailOperator(task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to= os.getenv('Callbackelist'), 
         subject=f"{reportID}{os.getenv('Callbacksubject')}",
         html_content="Report Failed",)
    send_email.execute(context)

with models.DAG(
    DAG_ID,
    # schedule='@once',
    schedule= os.getenv(f"{DAG_ID}sc"), 
    default_args = {
        "on_failure_callback": report_failure },
    start_date=datetime(2021, 1, 1, tzinfo=local_tz),
    catchup=False,
    tags=["docker","Production","Monthly","Maddie"]
) as dag:
    # [START howto_operator_docker]
    run_script = DockerOperator(
        docker_url=os.getenv("docker_url"),  # Set your docker URL
        command="Rscript /opt/airflow/dags/Scripts/14928_stxcl_criticalpotassiums/highpotassiumsscript.R",
        image="sonic/r-base",
        working_dir="/opt/airflow/dags/Scripts/14928_stxcl_criticalpotassiums",
        network_mode="bridge",
        task_id="stxcl_critical_potassiums_task",
        environment={"TZ":"America/Chicago"},
        retries=3,
        retry_delay=timedelta(minutes=5),
        mount_tmp_dir=False,
        mounts=[Mount(source='/root/zdir/docker/airflow/dags', target='/opt/airflow/dags', type='bind')],
        dag=dag,
    )
    # [END howto_operator_docker]
    jin = PythonOperator(
        task_id="render_output",
        python_callable=lambda **c: c['task'].render_template(content=c['ti'].xcom_pull(task_ids=run_script.task_id),context=c),
        provide_context=True,
        dag=dag
    )

    send_email = EmailOperator(
         task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to= emaillist,
         subject=f"CONFIDENTIAL - {reportID}",
         html_content=f"See attached {reportID} for SOUTH TEXAS CLINICAL LABS. Please contact the Data Science Department at cpldatascience@cpllabs.com if there are any issues.",
         files=['{{ ti.xcom_pull(task_ids="render_output",key="filename") }}']
         )
    def delete_files(**kwargs):
        ti = kwargs['ti']
        filename=ti.xcom_pull(task_ids="render_output",key="filename")
        os.remove(filename) #created file to remove
    delete_file_task = PythonOperator(
        task_id="delete_files_task", 
        python_callable=delete_files,
        provide_context=True,
        dag=dag
    )
    (
        # TEST BODY
        run_script >> jin >> send_email >> delete_file_task
    )

# client problem notes dags 
