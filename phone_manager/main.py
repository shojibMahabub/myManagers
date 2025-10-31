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
SHEET_ID = ""
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
            bank TEXT,
            type TEXT,
            merchant TEXT,
            amount REAL,
            balance REAL,
            device TEXT,
            raw_content TEXT
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
    match = re.search(r'```json(.*?)```', ai_response, re.DOTALL) or re.search(r'```(.*?)```', ai_response, re.DOTALL)
    if not match:
        return None

    raw_json = match.group(1).strip()

    try:
        data = json.loads(raw_json.replace("// masked.*", ""))  # remove comments
    except json.JSONDecodeError:
        return None

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
        "amount": extract_amount(data),
        "balance": extract_balance(data),
        "card_number": extract_card(data),
        "date": extract_date(data)
    }


def process_row(row, line_no):
    row = list(row) + [""]*(5 - len(row))
    date_str, bank, _, content, device = row
    sql_date = parse_flexible_date(date_str)

    prompt = f"Extract financial fields from this message as JSON-like string: \"\"\"{content}\"\"\""
    response_text = connect_ollama(prompt)
    debug_log(f"Line {line_no}: AI response: {response_text}")

    txn_type, merchant, amount, balance = parse_ollama_response(response_text)

    if "16216" in bank:
        bank = "DUTCH BANGLA BANK"

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (date, bank, type, merchant, amount, balance, device, raw_content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (sql_date, bank, txn_type, merchant, amount, balance, device, content))
    conn.commit()
    conn.close()
    debug_log(f"Line {line_no}: Inserted {bank} | {txn_type} | {merchant} | {amount} | {balance}")

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
