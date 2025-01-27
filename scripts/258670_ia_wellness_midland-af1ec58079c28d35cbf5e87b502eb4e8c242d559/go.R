source('/opt/airflow/dags/g.R')
ares<-dbGetQuery(conn, "SELECT A.ACCESSION, A.DEMOGRAPHICS_POINTER@PATIENT_NAME, A.DEMOGRAPHICS_POINTER@MINI_LOG_DATE, A.RELEASE_DATE, A.DEMOGRAPHICS_POINTER@DOB AS PTDOB, A.DEMOGRAPHICS_POINTER@PATIENT_ID AS PATID, B.TEST_CODE, C.TEST_REPORT_NAME, B.RESULT, coalesce(B.RESULT_DATA, 'na') as RDAT FROM LABORATORY_III.RELEASED_RESULTS_INDEX A, LABORATORY_III.ACCESSION_RESULTS B, LABORATORY_III.TEST_CODE C WHERE A.CLIENT_MNEMONIC='IAWM' AND A.RELEASE_DATE>'01/20/2020' AND B.WORKLIST=A.WORKLIST AND B.ACCESSION=A.ACCESSION AND C.TEST_CODE=B.TEST_CODE AND RESULT IS NOT NULL")
dbDisconnect(conn)
dim(ares)
# head(ares)
ares[ares$TEST_REPORT_NAME=="COMMENTS",]
awrite<-ares[!(grepl("DNR",ares$RDAT)|grepl("DNR", ares$RESULT)),]
dim(ares)
dim(awrite)

library(xlsx) 
# Check if the dataframe is empty
if (nrow(awrite) == 0) {
    # Create an Excel file with a message
    output_file <- paste(format(Sys.Date(), "%Y%m%d"), ".out.xls", sep="")
    wb <- createWorkbook(type="xls")
    sheet <- createSheet(wb, sheetName = "Sheet1")
    rows <- createRow(sheet, rowIndex=1)
    cell <- createCell(rows, colIndex=1)[[1]]
    setCellValue(cell, "No data to report")
    saveWorkbook(wb, output_file)
} else {
    # Normal file creation process with data
    colnames(awrite) <- c("Accession", "Patient Name", "Order Date", "Release Date", "Patient DOB", "Patient ID", "Test Code", "Result Name", "Numeric Result", "Textual Result")
    output_file <- paste(format(Sys.Date(), "%Y%m%d"), ".out.xls", sep="")
    wb <- createWorkbook(type="xls")
    sheet <- createSheet(wb, sheetName = "Sheet1")
    
    # Add column headers
    colHeaderRow <- createRow(sheet, rowIndex=1)
    for (i in 1:ncol(awrite)) {
        cell <- createCell(colHeaderRow, colIndex=i)[[1]]
        setCellValue(cell, colnames(awrite)[i])
    }

    # Add data
    addDataFrame(awrite, sheet, startRow=2, col.names=FALSE, row.names=FALSE)

    saveWorkbook(wb, output_file)
}
quit()