import pandas as pd
from datetime import datetime, timedelta

now = datetime.now()
last_month = now -timedelta(days=now.day)
myyr = last_month.strftime('%Y')
test_codes = []


dept_uc_2024 = pd.read_csv(f'deptuc_{myyr}.txt', sep='\t')
# print(dept_uc_2024.head())


with open('tjcodes.txt', 'r') as file:
    for line in file:
        value = line.strip()  # Remove any whitespace
        try:
            # Convert to int or float
            test_codes.append(int(value))
        except ValueError:
            # Handle or ignore lines that cannot be converted
            pass

dept_uc_2024 = dept_uc_2024.dropna(subset=['UnitCode'])
dept_uc_2024['UnitCode'] = dept_uc_2024['UnitCode'].astype(int)
filtered_code_df = dept_uc_2024[dept_uc_2024['UnitCode'].isin(test_codes)]



print(filtered_code_df)
second_to_last_column = filtered_code_df.columns[-2]
total = filtered_code_df[second_to_last_column].sum()
print(f"Total of the second to last column ({second_to_last_column}): {total}")

with open('data_to_cat_email.txt', 'w') as file:
        file.write(f"{total}")
        

categories = {
    'CT/NG': [3771, 3772, 5396, 5397, 5398, 5399, 5400, 5401, 5402, 5403, 375500, 377000, 411200],
    'TRICH': [3910, 3911, 3912, 3913, 4445],
    'HPV': [4037, 7890, 7891, 8037, 8038],
    'HIV': [3954, 4141, 4705, 7501],
    'HCV': [4492, 4563, 4571, 7500],
    'HBV': [4286, 7534],
    'CMV': [4019, 4187, 7576]
}

# Open a file to write
with open('Molecular_AP_Volume_Monthly.txt', 'w') as file:
    for category, codes in categories.items():
        # Write the category name
        file.write(f"{category}\n")
        
        # Filter rows belonging to the current category
        category_df = filtered_code_df[filtered_code_df['UnitCode'].isin(codes)]
        
        # Iterate through each row in the category DataFrame
        for index, row in category_df.iterrows():
            # Start with 'MOLECULAR' and then append all column values separated by tabs
            output_line = 'MOLECULAR' + '\t' + '\t'.join(row.astype(str))
            
            # Write the constructed line to the file
            file.write(output_line + "\n")
        