
#Enter strings for the dates.
STARTDATE= Sys.Date() -30
ENDDATE= Sys.Date() -1


startDateAsDate = STARTDATE 
endDateAsDate = ENDDATE

#Set variable to start date.
currentDateAsDate = startDateAsDate

#Define dataframe to append information into and set to null
results <- NULL
messages <- NULL

options(warning.length = 2000L)

#Connection to the MISYS database
source('/opt/airflow/dags/g.R')  # This establishes jdbc connection to tkbs and grabs a subscription

#Loop to iterate through each date of the date range
while(currentDateAsDate <= endDateAsDate) {
  currentDateAsString = format(currentDateAsDate, format='%m/%d/%Y')
  # print(currentDateAsString)
  
  # This snippet is only used during development. The thing is that when one is runnin a large for loop that contains querying and for some reason you need to stop it is very hard to stop it until the loop is done.  Here you can stop it without a problem during the pause time
  # print("Pausing query for 2 seconds.  You can stop the script at this time if you need to by pressing control C")
  # Sys.sleep(2)
  # print("Query resumed")
  
  # Here is the actual query
  potresults <- dbGetQuery(conn, paste0("SELECT coalesce(ACCESSION, 'NA') as ACN
        , COALESCE(DEMOGRAPHICS_POINTER@REQ_NUMBER, 'NA') as REQNUMBER
        , COALESCE(DEMOGRAPHICS_POINTER@PATIENT_NAME, 'NA') as PATIENTNM
        , COALESCE(DEMOGRAPHICS_POINTER@DOB, 'NA') as DOB
        , COALESCE(TEST_CODE, 'NA') as TCODE
        , COALESCE(MINI_LOG_DATE, 'NA') as MLD
        , COALESCE(RESULT, 'NA') as RESULTS
        , COALESCE(WORKLIST, 'NA') as WKLIST
        , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_MNEMONIC, 'NA') as CLIENTMN
        , COALESCE(HIGH_LOW_FLAG, 'NA') AS HIGHLOWFLAG
        FROM LABORATORY_III.ACCESSION_RESULTS
        WHERE 
        CLIENTMN = 'SOUTHTCL'
        AND WKLIST = 'COBAS7S'
        AND TCODE = '2228'
	AND MINI_LOG_DATE = '",currentDateAsString,"'"))
  results <- rbind(results, potresults)
  currentDateAsDate = currentDateAsDate + 1
}


colnames(results) <- c("ACCESSION", "REQNUMBER", "PATIENT_NAME", "DOB", "TCODE", "DATE_OF_SERVICE", "RESULTS", "WKLIST", "CLIENTMN", "HIGH_LOW_FLAG")
results <- subset(results, select = -WKLIST)


filteredresults <- results[grepl("H|L", results$HIGH_LOW_FLAG), ]

#write completed dataframe to CSV file.
# write.csv(filteredresults, "CPL_14928_SOUTHTEX_POTASSIUM_HIGHS_LOWS.csv", row.names=FALSE)

current_date <- format(Sys.Date(),"%Y-%m-%d")
output=file.path(getwd(), 'CPL_14928_SOUTHTEX_POTASSIUM_HIGHS_LOWS.csv') 
if (nrow(filteredresults) == 0) {
    # DataFrame is empty, write custom message
    message <- sprintf("No new high/low potassium results for: %s", Sys.Date())
    write(message, file = output)
} else {
    # DataFrame is not empty, write it to CSV
    write.csv(filteredresults, output, row.names = FALSE)
}

# write.csv(filteredresults, output, row.names=FALSE)

result=sprintf('{{ ti.xcom_push(key="filename",value="%s") }}',output)
cat(result)
