import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self, credentials_info, sheet_id):
        creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(sheet_id)
        self._row_cache = {}  # (tab_id, username, date) -> row number

    def get_worksheet(self, tab_name):
        """Get existing worksheet or create it."""
        try:
            return self.spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=30)

    def load_rows(self, worksheet):
        """Load all rows into cache for fast lookups."""
        all_values = worksheet.get_all_values()
        self._row_cache_data = all_values
        self._row_cache_ws_id = id(worksheet)
        self._row_count = len(all_values)
        for i, row in enumerate(all_values):
            if len(row) >= 2 and row[0]:
                self._row_cache[(id(worksheet), row[0].lower(), row[1])] = i + 1
        return all_values

    def find_row(self, worksheet, username, date_str):
        """Find row index for a learner+date combo. Returns row number or None."""
        return self._row_cache.get((id(worksheet), username.lower(), date_str))

    def ensure_row(self, worksheet, username, date_str):
        """Find existing row or append a new one. Returns row number."""
        row = self.find_row(worksheet, username, date_str)
        if row:
            return row
        self._row_count = getattr(self, '_row_count', 0) + 1
        next_row = self._row_count
        self._row_cache[(id(worksheet), username.lower(), date_str)] = next_row
        return next_row

    def batch_update(self, worksheet, updates):
        """Batch update cells. updates = [{"range": "A1", "values": [[val]]}]."""
        if not updates:
            return
        worksheet.batch_update(updates)

    def write_all_rows(self, worksheet, headers, rows):
        """Write headers + all data rows in one API call."""
        data = [headers] + rows
        worksheet.update(values=data, range_name=f"A1:{chr(64+len(headers))}{len(data)}")

    def read_config(self):
        """Read Config tab key-value pairs into a dict."""
        ws = self.get_worksheet("Config")
        rows = ws.get_all_values()
        config = {}
        for row in rows:
            if len(row) >= 2 and row[0]:
                config[row[0].strip()] = row[1].strip()
        return config

    def update_timestamp(self, worksheet, row, col):
        """Set a timestamp cell."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        worksheet.update_cell(row, col, now)
