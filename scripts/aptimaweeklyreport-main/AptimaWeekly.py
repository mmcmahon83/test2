#all dependencies and imports
from __future__ import annotations

import os
import pathlib
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pendulum
from airflow import models
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.operators.python import PythonOperator
from airflow.providers.samba.hooks.samba import SambaHook

load_dotenv()
#mount information and DAGID
from docker.types import Mount 

ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
DAG_ID = "AptimaWeekly" #update this, this will be the DAG name in Airflow

#variable assignment
local_tz = pendulum.timezone("America/Chicago") #sets timezone to CST
reportID = os.getenv(f"{DAG_ID}ri") 
emaillist = os.getenv(f"{DAG_ID}el")   

pathlib.Path('/opt/airflow/dags/tempfiles/').mkdir(exist_ok=True) 

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
    tags=["docker","Nielsa","Production","Weekly"],
) as dag:

    #function to import static file from outside server and write to current server
    def download_samba_file():
        samba = SambaHook(samba_conn_id='datascience', share = 'Data_Science') #this is the server connection name, there are three shares Data_Science, Gov_Reportables, Misys_archive
        with samba.open_file('/ScriptFiles/AptimaWeeklyCount.xlsx', mode = 'rb') as input: #this is the file we want to import
            with open('/opt/airflow/dags/tempfiles/AptimaWeeklyCount.xlsx', 'wb') as output: #this is the place we want to write to
                output.write(input.read())
       
    #task to execute file import from outside server
    pullfiles = PythonOperator(
        task_id='samba_download_task',
        python_callable=download_samba_file,
        dag=dag
    )
    # docker operator that runs script, returns jinja that can be read to get dynamic file names
    script = DockerOperator(
        docker_url=os.getenv("docker_url"),
        command="Rscript /opt/airflow/dags/Scripts/aptimaweeklyreport/AptimaWeekly.R",
        image="sonic/r-base",
        working_dir="/opt/airflow/dags/Scripts/aptimaweeklyreport",
        network_mode="bridge",
        task_id="script_task",
        environment={"TZ":"America/Chicago"},
        retries=3,
        retry_delay=timedelta(minutes=5),
        mount_tmp_dir=False,
        mounts=[Mount(source='/root/zdir/docker/airflow/dags', target='/opt/airflow/dags', type='bind')],
        dag=dag,
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
         to=emaillist,
         subject=f"{reportID}",
         html_content=f"Attached is the {reportID}. Please contact the Data Science Department at cpldatascience@cpllabs.com if there are any issues. Have a good day!",
         files=['{{ ti.xcom_pull(task_ids="render_output",key="filename") }}'] #key  that identifies file
         )

#function to write files to an outside server
    def samba_write_files(**kwargs):
        ti = kwargs['ti']
        filename=ti.xcom_pull(task_ids="render_output",key="filename")
        filewrite=os.path.basename(filename)
        local = '/opt/airflow/dags/tempfiles/'
        local_path = os.path.join(local, filewrite)
        remote = '/ScriptFiles/'
        remote_path = os.path.join(remote, filewrite)
        samba = SambaHook(samba_conn_id='datascience', share = 'Data_Science')
        samba.push_from_local(remote_path, local_path) 

    #task to write to outside server
    wfiles = PythonOperator(
        task_id='samba_write_task',
        python_callable=samba_write_files,
        provide_context=True,
        dag=dag
    )

#function to delete file that was imported from outside server
    def delete_files(**kwargs):
        ti = kwargs['ti']
        filename=ti.xcom_pull(task_ids="render_output",key="filename")
        os.remove('/opt/airflow/dags/Scripts/aptimaweeklyreport/graph1.png') #imported file to delete
        os.remove('/opt/airflow/dags/Scripts/aptimaweeklyreport/graph2.png')
        os.remove('/opt/airflow/dags/Scripts/aptimaweeklyreport/AptimaWeeklyCount.xlsx') #created file to remove
    #task to delete file imported from outside server
    dfiles = PythonOperator(
        task_id='delete_files_task',
        python_callable=delete_files,
        provide_context=True,
        dag=dag
        )
    
    (
        # TEST BODY
        pullfiles >> script >> jin >> email >> wfiles >> dfiles
    )

