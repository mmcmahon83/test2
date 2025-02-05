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

    r_base = kubernetes_pod_operator.KubernetesPodOperator(
        namespace='airflow',
        image="harbor-atx.us.int.sonichealthcare/airflow/r-base:latest",
        cmds=["sleep"],
        arguments=["240"],
        labels={"r-base": "r-base"},
        name="r-base",
        task_id="extract-tranform",
        get_logs=True,
        env_vars={"TZ":"America/Chicago"},
        cmds={"Rscript /opt/airflow/dags/repo/scripts/adcsf-main/ADCSF.R"}
    )

    r_base
