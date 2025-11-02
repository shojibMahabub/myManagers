import os
import csv
import time
import datetime
import re
import sqlite3
from googleapiclient.discovery import build
from google.oauth2 import service_account
import ollama
import json

# === CONFIG ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_ID = "1822j1bguPxBnXb3VezRiKD6thQJ-QUEmvWn7mKwCtmY"
SHEET_RANGE = "Sheet1!A:Z"
CURR_DIR = os.path.dirname(os.path.realpath(__file__))
CREDENTIAL_FILE = os.path.join(CURR_DIR, "credentials.json")
DB_FILE = os.path.join(CURR_DIR, "transactions.db")
DATA_CSV = os.path.join(CURR_DIR, "data.csv")
SYNC_LOG = os.path.join(CURR_DIR, "sync_log.txt")
DEBUG_LOG = os.path.join(CURR_DIR, "log.txt")
INTERVAL_MINUTES = 30

# === GOOGLE SHEETS AUTH ===
creds = service_account.Credentials.from_service_account_file(CREDENTIAL_FILE, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

# === SQLITE SETUP ===
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATETIME,
            institution TEXT,
            type TEXT,
            merchant TEXT,
            debit_account TEXT,
            amount REAL,
            balance REAL,
            device TEXT,
            card_number TEXT,
            total_due INTEGER,
            minimum_due INTEGER,
            due_date DATETIME,
            raw_content TEXT,
            reference_number TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# === LOGGING ===
def debug_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)

# === HELPERS ===
def parse_flexible_date(date_str):
    try:
        date_str = date_str.strip()
        if len(date_str) >= 2 and date_str[-2:].upper() in ("AM", "PM") and date_str[-3] != " ":
            date_str = date_str[:-2] + " " + date_str[-2:]
        for fmt in ("%B %d, %Y at %I:%M %p", "%B %d, %Y at %I:%M%p"):
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
    except Exception as e:
        debug_log(f"parse_flexible_date error: {e} | input: {date_str}")
    return None
def parse_sms_type(content):
    if re.search(r'\b(bill|client id|due date)\b', content, re.IGNORECASE):
        return 'credit-card-bill'

    if re.search(r'\b(client|due)\b', content, re.IGNORECASE):
        return 'credit-card'



    return None


def connect_ollama(prompt):
    try:
        response = ollama.chat(model="llama3.1:latest",
                               messages=[{'role':'user','content':prompt}])
        return response['message']['content']
    except Exception as e:
        debug_log(f"connect_ollama exception: {e}")
        return ""

def parse_ollama_response(ai_response):
    # Extract JSON-like string
    raw_json = json.loads(ai_response)

    # Flatten nested fields
    def extract_amount(d):
        for key in ["amount", "Amount", "amount_purchased", "AmountDue", "transactionAmount"]:
            if key in d:
                v = d[key]
                if isinstance(v, dict):
                    for subkey in ["value", "Original", "Purchased", "Amount"]:
                        if subkey in v:
                            return float(str(v[subkey]).replace(" ", "").replace(",", ""))
                else:
                    return float(str(v).replace("BDT", "").replace(" ", "").replace(",", ""))
        return None

    def extract_balance(d):
        for key in ["balance", "Balance"]:
            if key in d:
                v = d[key]
                if isinstance(v, dict):
                    for subkey in ["value", "Amount", "Balance"]:
                        if subkey in v:
                            return float(str(v[subkey]).replace(" ", "").replace(",", ""))
                else:
                    return float(str(v).replace("BDT", "").replace(" ", "").replace(",", ""))
        return None

    def extract_card(d):
        for key in ["card_number", "Card Number", "CardNumber", "payment_details"]:
            if key in d:
                val = d[key]
                if isinstance(val, dict):
                    return val.get("masked") or val.get("number")
                return val
        return None

    def extract_date(d):
        for key in ["date", "Date", "transaction_date", "Timestamp", "TransactionDate"]:
            if key in d:
                return str(d[key])
        return None

    return {
        "amount": extract_amount(raw_json),
        "balance": extract_balance(raw_json),
        "card_number": extract_card(raw_json),
        "date": extract_date(raw_json)
    }


def process_row(row, line_no):
    row = list(row) + [""]*(5 - len(row))
    date, institution, _, content, device = row

    parsed_data = {
        "date": parse_flexible_date(date),
        "institution": institution,
        "type": parse_sms_type(content),
        "merchant": "",
        "debit_account": "",
        "amount": "",
        "balance": "",
        "card_number": "",
        "total_due": "",
        "minimum_due": "",
        "due_date": "",
        "raw_content": content,
        "reference_number": "",
        "device": device,
    }

    # conn = sqlite3.connect(DB_FILE)
    # c = conn.cursor()
    # c.execute('''
    #     INSERT INTO transactions (date, bank, type, merchant, amount, balance, device, raw_content)
    #     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    # ''', (sql_date, bank, txn_type, merchant, amount, balance, device, content))
    # conn.commit()
    # conn.close()
    # debug_log(f"Line {line_no}: Inserted {bank} | {txn_type} | {merchant} | {amount} | {balance}")

# === MAIN SYNC ===
def sync_google_sheet():
    try:
        result = service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=SHEET_RANGE).execute()
        values = result.get("values", [])
        if not values or len(values) < 2:
            debug_log("No new data found in sheet.")
            return

        header, rows = values[0], values[1:]

        existing_rows = set()
        if os.path.exists(DATA_CSV):
            with open(DATA_CSV, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    existing_rows.add(tuple(row))

        new_rows = []
        with open(DATA_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for idx, row in enumerate(rows, start=1):
                row_tuple = tuple(row)
                if row_tuple not in existing_rows:
                    new_rows.append((idx, row))  # include line number
                writer.writerow(row)

        for line_no, row in new_rows:
            process_row(row, line_no)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(SYNC_LOG, "a", encoding="utf-8") as log:
            log.write(f"{timestamp} — Synced {len(new_rows)} new rows\n")
        debug_log(f"Sync finished: {len(new_rows)} new rows inserted.")

    except Exception as e:
        debug_log(f"sync_google_sheet exception: {e}")

# === SCHEDULER LOOP ===
print(f"Scheduler started — syncing every {INTERVAL_MINUTES} minutes.")
while True:
    sync_google_sheet()
    time.sleep(INTERVAL_MINUTES * 60)
