import os
import csv
import re


data = list(csv.reader(
    open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "data.csv"),
        'r',
        newline='',
        encoding='utf-8'
    )
))

header, data = data[0], data[1:]

parsed_data = {
    "date": '',
    "institution": '',
    "type": '',
    "merchant": "",
    "debit_account": "",
    "amount": "",
    "balance": "",
    "card_number": "",
    "total_due": "",
    "minimum_due": "",
    "due_date": "",
    "raw_content": '',
    "reference_number": "",
    "device": '',
}

json = list()

def detect_type(text):

    if re.search(r'\b(DPDC)\b', text, re.IGNORECASE):
        print(text + '\n')
        return
    else:
        return 0

for row in data:
    parsed_data['date'] = row[0]
    parsed_data['institution'] = row[1]
    parsed_data['raw_content'] = row[3]
    parsed_data['device'] = row[4]
    parsed_data['type'] = detect_type(row[3])

    json.append(parsed_data)




