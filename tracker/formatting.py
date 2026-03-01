"""Sheet structure setup, config defaults, and visual formatting.

Handles tab creation/renaming/reordering, writing missing config
defaults, and applying colors, filters, and conditional formatting
to all tabs in the Google Sheet.
"""

from tracker.constants import CONFIG_DEFAULTS


def setup_sheet_structure(sheets):
    """Ensure the sheet has the correct tab layout.

    Renames the legacy 'Metrics' tab to 'Roster' if needed, creates any
    missing tabs, and reorders them to:
    Roster | Leaderboard | Daily View | Alerts | Daily Raw Metrics | Config.

    Args:
        sheets: SheetsClient instance.
    """
    print("Setting up sheet structure...")

    try:
        sheets.spreadsheet.worksheet("Roster")
        print("  Roster tab already exists")
    except Exception:
        try:
            metrics_ws = sheets.spreadsheet.worksheet("Metrics")
            metrics_ws.update_title("Roster")
            print("  Renamed 'Metrics' → 'Roster'")
            rows = metrics_ws.get_all_values()
            if rows and len(rows[0]) > 2:
                last_col = chr(64 + len(rows[0])) if len(rows[0]) <= 26 else "Z"
                metrics_ws.batch_clear([f"C1:{last_col}{len(rows)}"])
                print("  Cleared columns C-N from Roster tab")
        except Exception:
            sheets.get_worksheet("Roster")
            print("  Created new Roster tab")

    sheets.get_worksheet("Leaderboard")
    sheets.get_worksheet("Weekly Leaderboard")
    sheets.get_worksheet("Monthly Leaderboard")
    sheets.get_worksheet("Custom Leaderboard")
    sheets.get_worksheet("Daily View")
    sheets.get_worksheet("Alerts")
    sheets.get_worksheet("Daily Raw Metrics")
    sheets.get_worksheet("Config")

    desired_order = [
        "Roster", "Leaderboard", "Weekly Leaderboard", "Monthly Leaderboard",
        "Custom Leaderboard", "Daily View", "Alerts", "Daily Raw Metrics", "Config",
    ]
    sheets.reorder_worksheets(desired_order)
    print("  Tabs reordered: " + " | ".join(desired_order))


def ensure_config_defaults(sheets):
    """Write any missing config keys to the Config tab.

    Reads current config values, compares against CONFIG_DEFAULTS, and
    appends any keys that are not yet present so admins can see and edit
    all available tuning parameters.

    Args:
        sheets: SheetsClient instance.
    """
    print("\nEnsuring config defaults...")
    ws = sheets.get_worksheet("Config")
    existing = ws.get_all_values()
    existing_keys = {row[0].strip() for row in existing if len(row) >= 1 and row[0].strip()}

    missing = [[key, value] for key, value in CONFIG_DEFAULTS if key not in existing_keys]

    if missing:
        next_row = len(existing) + 1
        updates = [
            {"range": f"A{next_row + i}:B{next_row + i}", "values": [row_data]}
            for i, row_data in enumerate(missing)
        ]
        ws.batch_update(updates)
        print(f"  Added {len(missing)} missing config keys")
    else:
        print("  All config keys present")


def format_sheets(sheets):
    """Apply formatting, colors, filters, and conditional formatting to all tabs.

    Runs in two phases: first cleans up existing conditional formats and
    basic filters, then applies tab colors, frozen headers, header styling,
    auto-filters, column auto-resize, and classification/score/alert
    conditional formatting rules in a single batch update.

    Args:
        sheets: SheetsClient instance.
    """
    print("\nFormatting sheets...")
    sp = sheets.spreadsheet

    def hex_to_rgb(hex_color):
        """Convert a hex color string to a Google Sheets RGB dict (0-1 range)."""
        h = hex_color.lstrip("#")
        return {
            "red": int(h[0:2], 16) / 255,
            "green": int(h[2:4], 16) / 255,
            "blue": int(h[4:6], 16) / 255,
        }

    metadata = sp.fetch_sheet_metadata()
    cleanup_requests = []
    for sheet_data in metadata.get("sheets", []):
        sheet_id = sheet_data["properties"]["sheetId"]
        cond_formats = sheet_data.get("conditionalFormats", [])
        for i in range(len(cond_formats) - 1, -1, -1):
            cleanup_requests.append({
                "deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}
            })
        if "basicFilter" in sheet_data:
            cleanup_requests.append({"clearBasicFilter": {"sheetId": sheet_id}})

    if cleanup_requests:
        sp.batch_update({"requests": cleanup_requests})

    tab_names = [
        "Roster", "Leaderboard", "Weekly Leaderboard", "Monthly Leaderboard",
        "Custom Leaderboard", "Daily View", "Alerts", "Daily Raw Metrics", "Config",
    ]
    tabs = {}
    for name in tab_names:
        try:
            tabs[name] = sp.worksheet(name)
        except Exception:
            pass

    tab_colors = {
        "Roster": "#70AD47",
        "Leaderboard": "#FFD700",
        "Weekly Leaderboard": "#00B0F0",
        "Monthly Leaderboard": "#92D050",
        "Custom Leaderboard": "#FFC000",
        "Daily View": "#4472C4",
        "Alerts": "#FF0000",
        "Daily Raw Metrics": "#808080",
        "Config": "#7030A0",
    }

    header_bg = hex_to_rgb("#1F3864")
    header_fg = {"red": 1, "green": 1, "blue": 1}
    requests = []

    for tab_name, ws in tabs.items():
        num_cols = ws.col_count
        num_rows = ws.row_count

        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "tabColorStyle": {"rgbColor": hex_to_rgb(tab_colors[tab_name])},
                },
                "fields": "tabColorStyle",
            }
        })

        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": ws.id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        })

        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": header_bg,
                        "textFormat": {"bold": True, "foregroundColor": header_fg},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })

        requests.append({
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": ws.id,
                        "startRowIndex": 0,
                        "endRowIndex": num_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    }
                }
            }
        })

        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": num_cols,
                }
            }
        })

    leaderboard_tabs = [
        "Leaderboard", "Weekly Leaderboard", "Monthly Leaderboard", "Custom Leaderboard",
    ]
    classification_colors = [
        ("EXCELLENT", "#C6EFCE"),
        ("GOOD", "#BDD7EE"),
        ("AVERAGE", "#FFF2CC"),
        ("NEEDS IMPROVEMENT", "#FCE4CC"),
        ("AT RISK", "#FFC7CE"),
    ]
    for lb_name in leaderboard_tabs:
        if lb_name not in tabs:
            continue
        lb_ws = tabs[lb_name]
        for idx, (text, color) in enumerate(classification_colors):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": lb_ws.id,
                            "startRowIndex": 1, "endRowIndex": 1000,
                            "startColumnIndex": 2, "endColumnIndex": 3,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": text}],
                            },
                            "format": {"backgroundColor": hex_to_rgb(color)},
                        },
                    },
                    "index": idx,
                }
            })

        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": lb_ws.id,
                    "startRowIndex": 1, "endRowIndex": 1000,
                    "startColumnIndex": 0, "endColumnIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
            }
        })

    if "Daily View" in tabs:
        dv_ws = tabs["Daily View"]
        dv_rules = [
            {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "8"}], "color": "#C6EFCE"},
            {"type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "5"}, {"userEnteredValue": "7"}], "color": "#FFF2CC"},
            {"type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "3"}, {"userEnteredValue": "4"}], "color": "#FCE4CC"},
            {"type": "NUMBER_LESS", "values": [{"userEnteredValue": "3"}], "color": "#FFC7CE"},
        ]
        for idx, rule in enumerate(dv_rules):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": dv_ws.id,
                            "startRowIndex": 1, "endRowIndex": 1000,
                            "startColumnIndex": 8, "endColumnIndex": 9,
                        }],
                        "booleanRule": {
                            "condition": {"type": rule["type"], "values": rule["values"]},
                            "format": {"backgroundColor": hex_to_rgb(rule["color"])},
                        },
                    },
                    "index": idx,
                }
            })

    if "Alerts" in tabs:
        alerts_ws = tabs["Alerts"]
        alert_colors = [
            ("INACTIVE", "#FFC7CE"),
            ("AT RISK", "#FCE4CC"),
            ("DECLINING", "#FFF2CC"),
        ]
        for idx, (text, color) in enumerate(alert_colors):
            requests.append({
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": alerts_ws.id,
                            "startRowIndex": 1, "endRowIndex": 1000,
                            "startColumnIndex": 1, "endColumnIndex": 2,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": text}],
                            },
                            "format": {"backgroundColor": hex_to_rgb(color)},
                        },
                    },
                    "index": idx,
                }
            })

    if requests:
        sp.batch_update({"requests": requests})

    print("  Formatting applied to all tabs")
