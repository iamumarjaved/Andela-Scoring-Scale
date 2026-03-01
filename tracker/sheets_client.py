"""Google Sheets API client for reading and writing spreadsheet data."""

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    """Wrapper around gspread for spreadsheet operations.

    Provides worksheet management, row caching for fast lookups,
    batch updates, and config reading from a key-value Config tab.
    """

    def __init__(self, credentials_info, sheet_id):
        """Initialize the client and open the target spreadsheet.

        Args:
            credentials_info: Google service account credentials dict.
            sheet_id: The Google Sheets spreadsheet ID.
        """
        creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(sheet_id)
        self._row_cache = {}

    def get_worksheet(self, tab_name):
        """Get an existing worksheet by name, or create it if missing.

        Args:
            tab_name: The worksheet tab name.

        Returns:
            A gspread Worksheet object.
        """
        try:
            return self.spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=30)

    def rename_worksheet(self, old_name, new_name):
        """Rename a worksheet tab.

        If new_name already exists, returns that worksheet. If old_name
        doesn't exist, returns None.

        Args:
            old_name: Current tab name.
            new_name: Desired tab name.

        Returns:
            The renamed Worksheet, or None if old_name was not found.
        """
        try:
            ws = self.spreadsheet.worksheet(new_name)
            return ws
        except gspread.WorksheetNotFound:
            pass
        try:
            ws = self.spreadsheet.worksheet(old_name)
            ws.update_title(new_name)
            return ws
        except gspread.WorksheetNotFound:
            return None

    def reorder_worksheets(self, tab_names):
        """Reorder tabs to match the given list.

        Tabs not in the list are appended at the end in their
        original order.

        Args:
            tab_names: List of tab names in desired order.
        """
        self.spreadsheet.fetch_sheet_metadata()
        all_ws = self.spreadsheet.worksheets()
        existing = {ws.title: ws for ws in all_ws}
        ordered = []
        for name in tab_names:
            if name in existing:
                ordered.append(existing.pop(name))
        for ws in all_ws:
            if ws.title in existing:
                ordered.append(existing.pop(ws.title))
        self.spreadsheet.reorder_worksheets(ordered)

    def load_rows(self, worksheet):
        """Load all rows into an internal cache for fast lookups.

        Populates a (worksheet_id, username, date) -> row_number cache
        so that find_row and ensure_row can operate without additional
        API calls.

        Args:
            worksheet: A gspread Worksheet object.

        Returns:
            List of all row values (including headers).
        """
        all_values = worksheet.get_all_values()
        self._row_cache_data = all_values
        self._row_cache_ws_id = id(worksheet)
        self._row_count = len(all_values)
        for i, row in enumerate(all_values):
            if len(row) >= 2 and row[0]:
                self._row_cache[(id(worksheet), row[0].lower(), row[1])] = i + 1
        return all_values

    def find_row(self, worksheet, username, date_str):
        """Find the row number for a learner+date combo from cache.

        Args:
            worksheet: A gspread Worksheet object.
            username: The learner's GitHub username.
            date_str: Date string in YYYY-MM-DD format.

        Returns:
            Row number (1-indexed), or None if not found.
        """
        return self._row_cache.get((id(worksheet), username.lower(), date_str))

    def ensure_row(self, worksheet, username, date_str):
        """Find an existing row or allocate a new one.

        Args:
            worksheet: A gspread Worksheet object.
            username: The learner's GitHub username.
            date_str: Date string in YYYY-MM-DD format.

        Returns:
            Row number (1-indexed) for the learner+date combo.
        """
        row = self.find_row(worksheet, username, date_str)
        if row:
            return row
        self._row_count = getattr(self, '_row_count', 0) + 1
        next_row = self._row_count
        self._row_cache[(id(worksheet), username.lower(), date_str)] = next_row
        return next_row

    def batch_update(self, worksheet, updates):
        """Batch update cells on a worksheet.

        Args:
            worksheet: A gspread Worksheet object.
            updates: List of dicts with 'range' and 'values' keys.
        """
        if not updates:
            return
        worksheet.batch_update(updates)

    def write_all_rows(self, worksheet, headers, rows):
        """Write headers and all data rows in one API call.

        Args:
            worksheet: A gspread Worksheet object.
            headers: List of header strings.
            rows: List of row lists.
        """
        data = [headers] + rows
        worksheet.update(values=data, range_name=f"A1:{chr(64+len(headers))}{len(data)}")

    def clear_and_write(self, worksheet, headers, rows):
        """Clear the worksheet then write headers and rows.

        Used for full-tab rewrites where stale rows must be removed.

        Args:
            worksheet: A gspread Worksheet object.
            headers: List of header strings.
            rows: List of row lists.
        """
        worksheet.clear()
        if not rows:
            worksheet.update(values=[headers], range_name=f"A1:{chr(64+len(headers))}1")
            return
        data = [headers] + rows
        col_letter = chr(64 + len(headers)) if len(headers) <= 26 else "Z"
        worksheet.update(values=data, range_name=f"A1:{col_letter}{len(data)}")

    def read_config(self):
        """Read the Config tab into a key-value dict.

        Returns:
            Dict mapping config keys to their string values.
        """
        ws = self.get_worksheet("Config")
        rows = ws.get_all_values()
        config = {}
        for row in rows:
            if len(row) >= 2 and row[0]:
                config[row[0].strip()] = row[1].strip()
        return config

    def update_timestamp(self, worksheet, row, col):
        """Set a cell to the current UTC timestamp.

        Args:
            worksheet: A gspread Worksheet object.
            row: Row number (1-indexed).
            col: Column number (1-indexed).
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        worksheet.update_cell(row, col, now)
