#!/usr/bin/env python

import sys
import xlrd

from datetime import datetime, timedelta

def xls_to_csv(workbook_path, worksheet_id, output_filename):
    try:
        book = xlrd.open_workbook(workbook_path)
        sheet = book.sheet_by_index(worksheet_id)

        with open(output_filename, 'w', encoding='utf-8') as output_file:
            for r in range(sheet.nrows):
                row_values = [str(sheet.cell(r, c).value) for c in range(sheet.ncols)]
                output_file.write('\t'.join(row_values) + '\n')
    except Exception as e:
        print(f"Error processing the Excel file: {e}")

now = datetime.now()
last_month = now - timedelta(days=now.day)
myyr = last_month.strftime('%Y')

workbook_path = f"Dept UC Statistics Report for {myyr}.xls"
worksheet_id = 0
output_filename = f"deptuc_{myyr}.txt"

xls_to_csv(workbook_path, worksheet_id, output_filename)