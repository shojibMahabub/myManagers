from googleapiclient.discovery import build
from google.oauth2 import service_account
import os

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]  # or remove `.readonly` for write access


CURR_DIR = os.path.dirname(os.path.realpath(__file__))
credential_file = os.path.join(CURR_DIR, 'credentials.json')

creds = service_account.Credentials.from_service_account_file(
    credential_file,
    scopes=SCOPES,
)

service = build("sheets", "v4", credentials=creds)

# Example: read a range
SAMPLE_SPREADSHEET_ID = ""
SAMPLE_RANGE_NAME = "Sheet1"

result = (
    service.spreadsheets()
    .values()
    .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME)
    .execute()
)
values = result.get("values", [])
headers = values[0]
