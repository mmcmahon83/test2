asst<-"OK"
library('RJDBC')
drv<-JDBC("com.kbs.jdbc.KBSDriver","/opt/airflow/dags/repo/scripts/kbsjdbc18.jar","'")
asst<-tryCatch({
   conn<-dbConnect(drv, "jdbc:kbsjdbc://200.10.10.10:8600", "DBA", "SHARK")} , 
   warning=function(w) {return("WARN")}, error=function(e) {return("ERR")}, finally={})
