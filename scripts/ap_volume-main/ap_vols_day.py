from __future__ import annotations

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pendulum
import fnmatch
import glob 
import pandas as pd
import logging
# import openpyxl

from airflow import models
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.operators.python import PythonOperator
from airflow.providers.samba.hooks.samba import SambaHook
from docker.types import Mount 

load_dotenv()
ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
DAG_ID = "ap_volumes"

local_tz = pendulum.timezone("America/Chicago") #sets timezone to CST
current_time = datetime.now() # Get current time and date
formatted_datetime = current_time.strftime('%Y%m%d_%H%M')

print(formatted_datetime)

reportID = os.getenv(f"{DAG_ID}ri") 
emaillist = os.getenv(f"{DAG_ID}el")   

now = datetime.now()
last_month = now -timedelta(days=now.day)
myyr = last_month.strftime('%Y')

last_month_date = now - relativedelta(months=1)
lastmonth_year = last_month_date.strftime('%B %Y')



## 1. DOWNLOAD THE FILE FROM T drive
def download_most_recent_file():
    downloaded_files = []
    samba = SambaHook(samba_conn_id='TDrive', share='client')
    file_pattern = f"Dept UC Statistics Report for {myyr}.xls"
    remote_dir = f"/OPERATIONS/Reporting/Management Reports/{myyr} Management Reports/"
    local_dir = "/opt/airflow/dags/Scripts/ap_volume/"
    

    try:
        # List all files in the remote directory
        all_files = samba.listdir(remote_dir)
        # Try to Filter files based on the pattern
        matched_files = fnmatch.filter(all_files, file_pattern)
        
        for file_name in matched_files:
            remote_path = os.path.join(remote_dir, file_name)
            local_path = os.path.join(local_dir, file_name)
            
            with samba.open_file(remote_path, mode='rb') as input_file:
                with open(local_path, 'wb') as output_file:
                    output_file.write(input_file.read())
                downloaded_files.append(local_path)
                print(f"Successfully downloaded {file_name}")
    except Exception as e:
        print(f"Failed to list or download files: {e}")

    return downloaded_files

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
    default_args = {
        "on_failure_callback": report_failure },
    start_date=datetime(2021, 1, 1, tzinfo=local_tz),
    catchup=False,
    tags=["docker","Production","Monthly","Maddie"],
) as dag:
    # [START howto_operator_docker]
    download_files = PythonOperator(
        task_id="list_samba_folders",
        python_callable=download_most_recent_file,
        dag=dag,
     )
    ## 2. Convert xls file downloaded
    run_script1 = DockerOperator(
        docker_url=os.getenv("docker_url"),  # Set your docker URL
        command="python3 /opt/airflow/dags/Scripts/ap_volume/xls2csv2stdout.py",
        image="sonic/r-base",
        working_dir="/opt/airflow/dags/Scripts/ap_volume",
        network_mode="bridge",
        task_id="script_task1",
        environment={"TZ":"America/Chicago"},
        retries=3,
        retry_delay=timedelta(minutes=5),
        mount_tmp_dir=False,
        mounts=[Mount(source='/root/zdir/docker/airflow/dags', target='/opt/airflow/dags', type='bind')],
        dag=dag,
         )
    ## 3. Data analysis on imported files
    run_script2 = DockerOperator(
        docker_url=os.getenv("docker_url"),  # Set your docker URL
        command="python3 /opt/airflow/dags/Scripts/ap_volume/read_tjcodes.py",
        image="sonic/r-base",
        working_dir="/opt/airflow/dags/Scripts/ap_volume",
        network_mode="bridge",
        task_id="script_task2",
        environment={"TZ":"America/Chicago"},
        retries=3,
        retry_delay=timedelta(minutes=5),
        mount_tmp_dir=False,
        mounts=[Mount(source='/root/zdir/docker/airflow/dags', target='/opt/airflow/dags', type='bind')],
        dag=dag,
    )
    ## 4. OG sh script pushes a value to email so just copied that.
    def read_and_push_value(**kwargs):
        file_path = '/opt/airflow/dags/Scripts/ap_volume/data_to_cat_email.txt'
        
        # Read the content of the file
        with open(file_path, 'r') as file:
            file_content = file.read().strip()  
        
        # Push the value to XCom
        kwargs['ti'].xcom_push(key='file_content', value=file_content)
    
    read_txt_output = PythonOperator(
        task_id='read_file',
        python_callable=read_and_push_value,
        provide_context=True,
        dag=dag,
    )
    ## 5. send email to those on emaillist
    send_email = EmailOperator(
         task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to=emaillist,
         subject=f"CPL Molecular monthly count for {lastmonth_year}",
         html_content="""
        <html>
            <body>
                <p>{{ task_instance.xcom_pull(task_ids='read_file', key='file_content') }}</p>
                <p> Please contact the Data Science Department at cpldatascience@cpllabs.com if there are any issues. Have a good day!</p>
            </body>
        </html>
        """,
        
         )
    ##  6. write files to spec. location
    def samba_write_files(**kwargs):
        
        samba = SambaHook(samba_conn_id='TDrive', share = 'client')
        samba.push_from_local('/SHARED/Files from AP/AP Daily Volume/AP volume/Molecular_AP_Volume_Monthly.txt', '/opt/airflow/dags/Scripts/ap_volume/Molecular_AP_Volume_Monthly.txt') #first file is destination file on external server, second is location of file on linux server
        
    #task to write to outside server
    write_files = PythonOperator(
        task_id='samba_write_task',
        python_callable=samba_write_files,
        provide_context=True,
        dag=dag
    )
    ## 7. Delete files
    def delete_files(**kwargs):
        os.remove('/opt/airflow/dags/Scripts/ap_volume/Molecular_AP_Volume_Monthly.txt') 
        os.remove('/opt/airflow/dags/Scripts/ap_volume/data_to_cat_email.txt')
        os.remove(f'/opt/airflow/dags/Scripts/ap_volume/deptuc_{myyr}.txt')
        os.remove(f'/opt/airflow/dags/Scripts/ap_volume/Dept UC Statistics Report for {myyr}.xls')
    dfiles = PythonOperator(
        task_id='delete_files_task',
        python_callable=delete_files,
        provide_context=True,
        dag=dag
        )

    (
        # TEST BODY
       # run_script >> 
    download_files >> run_script1 >> run_script2 >> read_txt_output >> send_email >> write_files >> dfiles
    )
