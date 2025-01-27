
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pendulum
from airflow import models
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.operators.python import PythonOperator
from docker.types import Mount 

load_dotenv()
ENV_ID = os.environ.get("SYSTEM_TESTS_ENV_ID")
DAG_ID = "IA_Wellness_Midland_weekly_report"

local_tz = pendulum.timezone("America/Chicago") #sets timezone to CST
current_time = datetime.now() # Get current time and date
formatted_datetime = current_time.strftime('%Y%m%d_%H%M')

print(formatted_datetime)

reportID = os.getenv(f"{DAG_ID}ri") 

emaillist = os.getenv(f"{DAG_ID}el") 


formatted_date = current_time.strftime("%Y%m%d")

file_path = f"/opt/airflow/dags/Scripts/258670_ia_wellness_midland/{formatted_date}.out.xls"

def report_failure(context):
    send_email = EmailOperator(task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to= os.getenv('Callbackelist'), #list of email recipients separated by comma then space
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
    tags=["docker","Production","Weekly","Maddie"],
) as dag:
    # [START howto_operator_docker]
    run_script = DockerOperator(
        docker_url=os.getenv("docker_url"),  # Set your docker URL
        command="Rscript /opt/airflow/dags/Scripts/258670_ia_wellness_midland/go.R",
        image="sonic/r-base",
        working_dir="/opt/airflow/dags/Scripts/258670_ia_wellness_midland",
        network_mode="bridge",
        task_id="script_task",
        environment={"TZ":"America/Chicago"},
        retries=3,
        retry_delay=timedelta(minutes=5),
        mount_tmp_dir=False,
        mounts=[Mount(source='/root/zdir/docker/airflow/dags', target='/opt/airflow/dags', type='bind')],
        dag=dag,
    )

    send_email = EmailOperator(
         task_id="Send_Results",
         from_email="airflow@sonichealthcareusa.com",
         to=emaillist,
         subject=f"{reportID}",
         html_content=f"Attached is the {reportID}. Please contact the Data Science Department at cpldatascience@cpllabs.com if there are any issues. Have a good day!",
         files=[file_path]
         )
    def delete_file(file_path):
        try:
            os.remove(file_path)
            print(f"Sucessfully deleted file: {file_path}")
        except OSError as e:
            print(f"Error: {file_path} : {e.strerror}")
    delete_file_task = PythonOperator(
        task_id="delete_files_task", 
        python_callable=delete_file,
        provide_context=True,
        op_args=[file_path],
        dag=dag
    )
    (
        # TEST BODY
        run_script >> send_email >> delete_file_task
    )
