library(lubridate)
require(openxlsx)
library(tidyverse)
library(data.table)
library(scales)
library(reshape2)
library(ggplot2)

TODAY_DATE = Sys.Date()
TESTCODES <- c(39111,39101,44451,44452,53981,53961,37551,37552,37553,37554,37702,37703,37704,37712,37713,37722,37723)
testsForQuery <- paste0("(", paste(TESTCODES,collapse=","),")")

STARTDATE= Sys.Date() - 7
ENDDATE= Sys.Date() - 1

#Transform date strings into date datatypes in roder to iterate over date range in loop containing query
startDateAsDate = STARTDATE 
endDateAsDate = ENDDATE

#Set variable to start date.
currentDateAsDate = startDateAsDate

#Define dataframe to append information into and set to null
alldf1 <- NULL

#Connection to the MISYS database
source('/opt/airflow/dags/g.R')  # This establishes jdbc connection to tkbs and grabs a subscription

#Loop to iterate through each date of the date range
while(currentDateAsDate <= endDateAsDate) {
  currentDateAsString = format(currentDateAsDate, format='%m/%d/%Y')
  print(currentDateAsString)
  
  # This snippet is only used during development. The thing is that when one is runnin a large for loop that contains querying and for some reason you need to stop it is very hard to stop it until the loop is done.  Here you can stop it without a problem during the pause time
  print("Pausing query for 2 seconds.  You can stop the script at this time if you need to by pressing control C")
  Sys.sleep(2)
  print("Query resumed")
  temp <- dbGetQuery(conn,paste0("SELECT ACCESSION as ACCNUM  
        , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_POINTER@CLIENT_NUMBER, 'NA') AS CNUMBER
        , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_POINTER@CLIENT_NAME, 'NA') AS CNAME
        , COALESCE(ORDERED_UNIT_TITLE_POINTER@ORDERED_UNIT_CODE, 'NA') AS OUC
        , COALESCE(ORDERED_UNIT_TITLE_POINTER@ORDERED_UNIT_TITLE , 'NA') AS TESTNAME
        , COALESCE(SALESPERSON_POINTER@SALESPERSON_ID, 'NA') AS SALEID
        , COALESCE(SALESPERSON_POINTER@SALESPERSON_NAME, 'NA') AS SALENAME
        , COALESCE(DEMOGRAPHICS_POINTER@CLIENT_POINTER@ACCOUNT_DESCRIPTION, 'NA') AS REGION
		    FROM LABORATORY_III.ACCESSION_BY_MINI_LOG_DATE A  
        , LABORATORY_III.ACCESSION_RESULTS B, AR3_CLIENT C, LABORATORY_III.ACCESSION_RESULTS_MESSAGES D,LABORATORY_III.ACCESSION_ORDER_UC_DETAIL E
        WHERE  A.ACCESSION = B.ACCESSION 
        AND A.ACCESSION = D.ACCESSION
        AND A.ACCESSION = E.ACCESSION
        AND C.CLIENT_NUMBER = B.DEMOGRAPHICS_POINTER@CLIENT_POINTER@CLIENT_NUMBER
        AND D.MESSAGE IN ('V1744','V1727')
        AND A.MINI_LOG_DATE = '",currentDateAsString,"'
        AND TEST_CODE IN ",testsForQuery,""))
  
  alldf1 <- rbind(alldf1, temp)
  currentDateAsDate = currentDateAsDate + 1
}
dbDisconnect(conn) # Always a good idea to do this to release the tkbs subscription.  Although closing out of the R terminal might do so (almost sure it does) this is still a good idea in case you leave the terminal open or in case there is some sort of error that crashes things and the subscription maybe stays held (no graceful exit)

#Data cleaning and analysis
alldf <- alldf1 %>% distinct()
alldf <- subset(alldf,subset = OUC %in% c(3911,3910,4445,5249,5398,5396,3755,3770,3771,3772))
alldf <- aggregate(.~ACCNUM+CNUMBER+CNAME+REGION, data = alldf, paste, collapse = ",")
alldf$SALENAME <- sapply(strsplit(alldf$SALENAME, ","), function(x) paste(unique(x), collapse = ","))
alldf$SALEID <- sapply(strsplit(alldf$SALEID, ","), function(x) paste(unique(x), collapse = ","))
regional <- alldf %>% count(REGION) 
client <- aggregate(ACCNUM~CNUMBER+CNAME+REGION, alldf, length)
regional <- alldf %>% count(REGION) 
alldf <- alldf %>% rename("Accession" = "ACCNUM", "Client Number" = "CNUMBER","Client Name" = "CNAME","Order Code" = "OUC","Test Name" = "TESTNAME","Sales ID" = "SALEID","Salesperson" = "SALENAME")
fulldata <- split(subset(alldf, select = -REGION), alldf$REGION)
total <- nrow(alldf)
regional$Percentage <- with(regional, percent(regional$n/total,accuracy=1))
summary <- subset(regional,select = c(REGION,n))

#Column renames
client <- client %>% rename("Client Number" = "CNUMBER","Client Name" = "CNAME","Region" = "REGION", !!quo_name(STARTDATE):= "ACCNUM")
regional <- regional %>% rename("Region" = "REGION", !!quo_name(STARTDATE):= n)
summary <- summary %>% rename("Region" = "REGION", !!quo_name(STARTDATE):= n)
print(summary)
#Read in first sheet from previous xlsx file
summaryo <- read.xlsx("/opt/airflow/dags/Scripts/aptimaweeklyreport/AptimaWeeklyCount.xlsx", sheet = 1,startRow = 3)
summaryo <- summaryo[ -c(2) ]
print(summaryo)
summary <- merge(summaryo, summary, by="Region", all = T)
summary[is.na(summary)] <- 0

#Create df for graph with trendline
summary2 <- summary %>% summarize_if(is.numeric, sum, na.rm=TRUE)
summary2 <- t(summary2)
summary2 <- as.data.frame(summary2)

#Workbook formatting styles
header_style <- createStyle(textDecoration = "Bold", fontColour = "#FFFFFF",
                            halign = "left", valign = "top", fgFill = "#233954", border = "LeftRight",
                            borderColour = "#FFFFFF", borderStyle = "thin", wrapText = FALSE)
title_style <- createStyle(textDecoration = c("bold","italic"), fontColour = "#1c3d84",fontSize = "16",halign = "left", valign = "top",wrapText = FALSE)

#Create and write summary data to workbook
wb <- createWorkbook()
addWorksheet(wb, sheetName="Summary")
writeData(wb, "Summary", summary, startCol = 1, startRow = 3, rowNames = FALSE)
writeData(wb, "Summary", paste("Twelve Week Summary (by week starting date)"), startCol = 1, startRow = 1)
addStyle(wb, sheet="Summary", header_style, rows = 3, cols = 1:13, gridExpand = FALSE)
addStyle(wb, sheet="Summary", title_style, rows = 1, cols = 1, gridExpand = FALSE)

#Bar graph creation
graph1 <- melt(summary, id = c("Region"))

graph1 <- ggplot(graph1, aes(fill=variable, y=value, x=Region)) + 
  geom_bar(position="dodge", stat="identity")+
  ggtitle("Number of Aptima Tests Grouped by Region (12 week period by week)")+
  ylab("Accessions")+
  labs(fill = "Week (by start date)")+
  theme(plot.title=element_text(size=16, colour ="#1c3d84", face ="bold"))+
  theme(axis.title.x= element_text(colour="#1e1444",
                                   size=10))+ 
  theme(axis.title.y= element_text(colour="#1e1444",
                                   size=10))+ 
  theme(axis.text.x= element_text(colour="#1e1444",
                                  size=7,angle = 75,vjust = 0.5, hjust=0.5))+ 
  theme(axis.text.y= element_text(colour="#1e1444",
                                  size=7))+
  theme(legend.title = element_text(colour="#1e1444",
                                    size=10))+
  theme(legend.text = element_text(colour="#1e1444",
                                   size=8))+
  theme(panel.background = element_rect(color = "#1a1a34"))+
  theme(legend.position="bottom")

ggsave("graph1.png", device = "png", width = 18, height = 6, units = "in", dpi = 300)
addWorksheet(wb, sheetName="Graph 1")
insertImage(wb, sheet="Graph 1", file = "graph1.png", startCol = 1, startRow = 1, width = 18, height = 6, units = "in")

#Time Series total creation
graph2 <- ggplot(aes(x=(row.names(summary2)), y=V1, group=1),data =summary2) +
  geom_point()+
  geom_smooth(method = 'lm',se = FALSE)+
  ggtitle("Number of Aptima Tests per Week")+
  ylab("Accessions")+
  xlab("Week")+
  scale_y_continuous(breaks = seq(0, 1000, 50), limits = c(0, 1000)) +
  theme(plot.title=element_text(size=16, colour ="#1c3d84", face ="bold"))+
  theme(axis.title.x= element_text(colour="#1e1444",
                                   size=10))+ 
  theme(axis.title.y= element_text(colour="#1e1444",
                                   size=10))+ 
  theme(axis.text.x= element_text(colour="#1e1444",
                                  size=7,angle = 75,vjust = 0.5, hjust=0.5))+ 
  theme(axis.text.y= element_text(colour="#1e1444",
                                  size=7))+
  theme(legend.title = element_text(colour="#1e1444",
                                    size=10))+
  theme(legend.text = element_text(colour="#1e1444",
                                   size=8))+
  theme(panel.background = element_rect(color = "#1a1a34"))

ggsave("graph2.png", device = "png", width = 18, height = 6, units = "in", dpi = 300)
addWorksheet(wb, sheetName="Graph 2")
insertImage(wb, sheet="Graph 2", file = "graph2.png", startCol = 1, startRow = 1, width = 18, height = 6, units = "in")

#Write all other data
addWorksheet(wb, sheetName="Regional")
writeData(wb, "Regional", regional, startCol = 1, startRow = 3, rowNames = FALSE)
writeData(wb, "Regional", paste("Weekly Regional Summary (by week starting date)"), startCol = 1, startRow = 1)
writeData(wb, "Regional", paste("Total Accessions ="), startCol = 5, startRow = 1)
writeData(wb, "Regional", total, startCol = 6, startRow = 1)
addStyle(wb, sheet="Regional", header_style, rows = 3, cols = 1:3, gridExpand = FALSE)
addStyle(wb, sheet="Regional", title_style, rows = 1, cols = 1:6, gridExpand = FALSE)
setColWidths(wb, sheet="Regional", cols = 5, widths = 17)

addWorksheet(wb, sheetName="Client")
writeData(wb, "Client", client, startCol = 1, startRow = 3, rowNames = FALSE)
writeData(wb, "Client", paste("Weekly Client Summary (by week starting date)"), startCol = 1, startRow = 1)
addStyle(wb, sheet="Client", header_style, rows = 3, cols = 1:4, gridExpand = FALSE)
addStyle(wb, sheet="Client", title_style, rows = 1, cols = 1, gridExpand = FALSE)
setColWidths(wb, sheet="Client", cols = 2, widths = 42)

#Iteration through split alldf to create tabs specific for each region
for (i in 1:length(fulldata)) {
  addWorksheet(wb, sheetName=names(fulldata[i]))
  writeData(wb, sheet=names(fulldata[i]), x=fulldata[[i]])
  addStyle(wb, sheet=names(fulldata[i]), header_style, rows = 1, cols = 1:ncol(x=fulldata[[i]]), gridExpand = TRUE)
  setColWidths(wb,sheet=names(fulldata[i]),cols = 1:ncol(x=fulldata[[i]]), widths ="auto")
}

outputFile=paste0("AptimaWeeklyCount.xlsx")
saveWorkbook(wb,outputFile,overwrite = TRUE)

output=file.path(getwd(), outputFile) 
result=sprintf('{{ ti.xcom_push(key="filename",value="%s") }}',output)
cat(result)
