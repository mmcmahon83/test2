library(lubridate)
require(openxlsx)
library(tidyverse)
library(data.table)
library(scales)

#code for automated dat run
TODAY_DATE = Sys.Date()   # all dates below are dependent only on this line
firstDayThisMonth = lubridate::floor_date(TODAY_DATE, unit = "month")
lastDayLastMonth = (lubridate::floor_date(TODAY_DATE, unit = "month")) - 1
firstDayLastMonth = lubridate::floor_date(lastDayLastMonth, unit = "month")

startingDateToQuery = format(firstDayLastMonth, format='%m/%d/%Y')
endingDateToQuery = format(lastDayLastMonth, format='%m/%d/%Y')

#Define dataframe to append information into and set to null
adcsf <- NULL

#Connection to the MISYS database
source('/opt/airflow/dags/g.R')  # This establishes jdbc connection to tkbs and grabs a subscription

currentDayDateFormat = firstDayLastMonth
while(currentDayDateFormat <= lastDayLastMonth) {
  currentDayStringFormat = format(currentDayDateFormat, format="%m/%d/%Y")
  print(currentDayStringFormat)

  # Here is the actual query
  temp <- dbGetQuery(conn, paste0("SELECT ACCESSION 
		, MINI_LOG_DATE
		, UNIT_CODE 
		FROM LABORATORY_III.ACCESSION_ORDER_UNIT_CODE A, LABORATORY_III.ACCESSION_BY_MINI_LOG_DATE B
		WHERE 
		B.MINI_LOG_DATE = '",currentDayStringFormat,"'
		AND A.UNIT_CODE IN ('3015')
		AND A.ACCESSION = B.ACCESSION"))
  adcsf <- rbind(adcsf, temp)
  currentDayDateFormat = as.Date(strptime(currentDayStringFormat, format="%m/%d/%Y")) + 1
}
dbDisconnect(conn) # Always a good idea to do this to release the tkbs subscription.  Although closing out of the R terminal might do so (almost sure it does) this is still a good idea in case you leave the terminal open or in case there is some sort of error that crashes things and the subscription maybe stays held (no graceful exit)


TESTCODES <- c('30151','30156','30153','30154','30155')
testsForQuery <- paste0("(", paste(TESTCODES,collapse=","),")")

accessions = sort(unique(adcsf$ACCESSION))
adcsfall = NULL
temp <- NULL
count = 0
source('/opt/airflow/dags/g.R')
for(accession in accessions) {

  temp <- dbGetQuery(conn, paste0("SELECT ACCESSION  
    , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_POINTER@CLIENT_NUMBER, 'NA') AS CNUMBER
    , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_POINTER@CLIENT_NAME, 'NA') AS CNAME
    , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_POINTER@ACCOUNT_DESCRIPTION, 'NA') AS REGION
    , COALESCE(SALESPERSON_POINTER@SALESPERSON_ID, 'NA') AS SALEID
    , COALESCE(RESULT, 'NA') AS RES
    FROM LABORATORY_III.ACCESSION_RESULTS A, AR3_CLIENT B
    WHERE 
    B.CLIENT_NUMBER = A.DEMOGRAPHICS_POINTER@CLIENT_POINTER@CLIENT_NUMBER
    AND A.TEST_CODE IN ",testsForQuery,"
    AND A.accession = '",accession,"'"))
 
  adcsfall <- rbind(adcsfall, temp)
}
dbDisconnect(conn)

adcsfall <- subset(adcsfall, !(startsWith(ACCESSION, "T")))

adcsfall2 <- adcsfall %>% 
  group_by(ACCESSION, CNUMBER, CNAME, REGION, SALEID) %>%
  summarise(RES = str_c(RES, collapse="; "))


adcsfstats <- adcsfall2 %>% group_by(CNAME,CNUMBER,REGION, SALEID) %>% summarise(Total.Count = n(), 
                                                          TNP = sum(str_detect(RES, pattern = "TNP")),
                                                          Percent.TNP = percent((TNP/Total.Count), accuracy = 0.1))

#Workbook style
header_style <- createStyle(textDecoration = "Bold", fontColour = "#FFFFFF",
                            halign = "left", valign = "top", fgFill = "#233954", border = "LeftRight",
                            borderColour = "#FFFFFF", borderStyle = "thin", wrapText = FALSE)
title_style <- createStyle(textDecoration = c("bold","italic"), fontColour = "#1c3d84",fontSize = "16",halign = "left", valign = "top",wrapText = FALSE)

#Create and write summary data to workbook
wb <- createWorkbook()
addWorksheet(wb, sheetName="Summary")
writeData(wb, "Summary", adcsfstats, startCol = 1, startRow = 3, rowNames = FALSE)
writeData(wb, "Summary", paste("Monthly AD CSF TNP Report"), startCol = 1, startRow = 1)
addStyle(wb, sheet="Summary", header_style, rows = 3, cols = 1:7, gridExpand = TRUE)
addStyle(wb, sheet="Summary", title_style, rows = 1, cols = 1, gridExpand = FALSE)
setColWidths(wb, sheet="Summary", cols = 1, widths = 20)

addWorksheet(wb, sheetName="Data")
writeData(wb, "Data", adcsfall2, startCol = 1, startRow = 3, rowNames = FALSE)
writeData(wb, "Data", paste("Accession Data"), startCol = 1, startRow = 1)
addStyle(wb, sheet="Data", header_style, rows = 3, cols = 1:6, gridExpand = FALSE)
addStyle(wb, sheet="Data", title_style, rows = 1, cols = 1, gridExpand = FALSE)

outputFile=paste0("MonthlyADCAFTNPReport.xlsx")
saveWorkbook(wb,outputFile,overwrite = TRUE)

output=file.path(getwd(), outputFile) 
result=sprintf('{{ ti.xcom_push(key="filename",value="%s") }}',output)
cat(result)

