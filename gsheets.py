"""
Anesthesia Journal Digest — Live MOC tracking in Google Sheets (Tier 1)
=======================================================================
Rolling, never-resetting MOC tracker in a Google Sheet, plus a Drive folder
structure for future certificate storage.

Auth: a Google Cloud SERVICE ACCOUNT. Two environment variables / GitHub Secrets:
  - GOOGLE_SERVICE_ACCOUNT_JSON : the full service-account key JSON (as a string)
  - GOOGLE_DRIVE_FOLDER_ID      : ID of a Drive folder ("Anesthesia Digest MOC")
                                  that YOU created and shared (Editor) with the
                                  service account's client_email.

On first use this creates, inside that folder:
  - a "Certificates" subfolder (for later use)
  - a "MOC Tracker" spreadsheet with tabs: Activity Log, CME Log, Summary,
    Monthly Top 5

Design:
  - APPEND-ONLY logs (manual edits to Hours/Notes/Score persist).
  - De-duplicated by date so re-runs never double-log.
  - Summary uses LIVE formulas (SUMPRODUCT by month) referencing the logs, so it
    auto-updates when you edit Hours by hand.
If anything Google-related fails, callers fall back to the local xlsx tracker.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_NAME = "MOC Tracker"
CERT_FOLDER_NAME = "Certificates"

ACTIVITY_SHEET = "Activity Log"
CME_SHEET = "CME Log"
SUMMARY_SHEET = "Summary"
TOP5_SHEET = "Monthly Top 5"

ACTIVITY_HEADERS = ["Email Date", "Section", "Journal", "Title", "DOI",
                    "Open Access", "In Email", "Hours", "Credits", "Notes"]
CME_HEADERS = ["Date", "Activity", "# Questions", "Score", "Hours", "Credits"]
TOP5_HEADERS = ["Rank", "Digest Date", "Journal", "Title", "Impact Factor",
                "DOI", "Open Access"]

# Bounded ranges for the Summary formulas (plenty for years of weekly logging).
_LOG_MAXROW = 5000


def is_configured() -> bool:
    """True only if both the key and the target folder id are present."""
    return bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
                and os.environ.get("GOOGLE_DRIVE_FOLDER_ID"))


# ── Auth / handles ───────────────────────────────────────────────────────────

def _creds():
    from google.oauth2.service_account import Credentials
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def _open():
    """Return (gspread_client, drive_service, folder_id)."""
    import gspread
    from googleapiclient.discovery import build
    creds = _creds()
    gc = gspread.authorize(creds)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    return gc, drive, folder_id


def _find_in_folder(drive, folder_id, name, mime):
    q = (f"name = '{name}' and '{folder_id}' in parents "
         f"and mimeType = '{mime}' and trashed = false")
    res = drive.files().list(
        q=q, fields="files(id, name)", spaces="drive",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def _ensure_cert_folder(drive, folder_id):
    fid = _find_in_folder(drive, folder_id, CERT_FOLDER_NAME,
                          "application/vnd.google-apps.folder")
    if fid:
        return fid
    meta = {"name": CERT_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [folder_id]}
    f = drive.files().create(body=meta, fields="id",
                             supportsAllDrives=True).execute()
    logger.info(f"Created Drive subfolder '{CERT_FOLDER_NAME}'")
    return f["id"]


def _ensure_spreadsheet(gc, drive, folder_id):
    # A service account on a PERSONAL Google account has no Drive storage quota,
    # so it cannot CREATE a file it would own (you'd get "storage quota
    # exceeded"). Instead we open a sheet YOU created (the SA can edit a file you
    # own without using quota). Prefer an explicit GOOGLE_SHEET_ID, else find the
    # 'MOC Tracker' sheet by name inside the shared folder.
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if sheet_id:
        return gc.open_by_key(sheet_id)

    sid = _find_in_folder(drive, folder_id, SPREADSHEET_NAME,
                          "application/vnd.google-apps.spreadsheet")
    if sid:
        return gc.open_by_key(sid)

    raise RuntimeError(
        f"'{SPREADSHEET_NAME}' spreadsheet not found and a service account can't "
        f"create one on a personal Google account (no storage quota). Create an "
        f"empty Google Sheet named '{SPREADSHEET_NAME}' inside the shared folder "
        f"(or set the GOOGLE_SHEET_ID secret to a sheet you created), then re-run."
    )


def _ensure_ws(sh, title, headers, rows=200):
    import gspread
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=rows, cols=max(12, len(headers)))
        ws.update(range_name="A1", values=[headers],
                  value_input_option="USER_ENTERED")
        ws.format(f"A1:{chr(64 + len(headers))}1", {"textFormat": {"bold": True}})
        return ws


def _structure(gc=None, drive=None, folder_id=None):
    """Ensure folder + spreadsheet + all tabs exist. Returns the spreadsheet."""
    import gspread
    if gc is None:
        gc, drive, folder_id = _open()
    _ensure_cert_folder(drive, folder_id)
    sh = _ensure_spreadsheet(gc, drive, folder_id)
    _ensure_ws(sh, ACTIVITY_SHEET, ACTIVITY_HEADERS)
    _ensure_ws(sh, CME_SHEET, CME_HEADERS)
    _ensure_ws(sh, SUMMARY_SHEET, ["Month"], rows=120)
    _ensure_ws(sh, TOP5_SHEET, TOP5_HEADERS, rows=20)
    # Remove the default empty "Sheet1" gspread creates with a new spreadsheet.
    try:
        sh.del_worksheet(sh.worksheet("Sheet1"))
    except gspread.WorksheetNotFound:
        pass
    return sh


# ── Logging operations ───────────────────────────────────────────────────────

def log_digest(selected: list, email_date: str) -> str:
    """APPEND one Activity Log row per featured article. Dedup by email_date.

    Returns the spreadsheet URL. Raises on any API/auth failure (caller falls
    back to xlsx).
    """
    gc, drive, folder_id = _open()
    sh = _structure(gc, drive, folder_id)
    ws = sh.worksheet(ACTIVITY_SHEET)

    if email_date in set(ws.col_values(1)):
        logger.info(f"Activity Log already has {email_date} — skip (no double-log)")
        _refresh_summary(sh)
        return sh.url

    start = len(ws.get_all_values()) + 1  # next empty row (1-based)
    rows = []
    for i, art in enumerate(selected):
        r = start + i
        rows.append([
            email_date,
            "Section 2",
            art.get("journal_abbr", ""),
            (art.get("title", "") or "")[:300],
            art.get("doi", ""),
            "Yes" if art.get("is_open_access") else "No",
            "TRUE",            # In Email check
            "",                # Hours — you fill
            f"=H{r}*2",        # Credits = Hours × 2 (Section 2: 2 credits/hr)
            "",                # Notes — you fill
        ])
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    logger.info(f"Appended {len(rows)} rows to '{ACTIVITY_SHEET}' for {email_date}")
    _refresh_summary(sh)
    return sh.url


def log_cme(date: str, num_questions: int, activity: str = "Weekly CME self-assessment") -> str:
    """APPEND one CME Log row. Dedup by date. Returns the spreadsheet URL."""
    gc, drive, folder_id = _open()
    sh = _structure(gc, drive, folder_id)
    ws = sh.worksheet(CME_SHEET)

    if date in set(ws.col_values(1)):
        logger.info(f"CME Log already has {date} — skip (no double-log)")
        _refresh_summary(sh)
        return sh.url

    r = len(ws.get_all_values()) + 1
    row = [date, activity, num_questions,
           "",            # Score — you fill in
           "",            # Hours — you fill in
           f"=E{r}*2"]    # Credits = Hours × 2 (Section 3: 2 credits/hr)
    ws.append_rows([row], value_input_option="USER_ENTERED")
    logger.info(f"Appended CME Log row for {date}")
    _refresh_summary(sh)
    return sh.url


def update_monthly_top5(month: str) -> str:
    """Rewrite 'Monthly Top 5' from that month's Monday open-access picks.

    Reads the Activity Log rows whose Email Date is in ``month`` (YYYY-MM),
    ranks by journal impact factor (tiebreaker), keeps 5. Returns the URL.
    """
    from config import JOURNALS
    if_by_abbr = {j["abbreviation"]: j["impact_factor"] for j in JOURNALS}

    gc, drive, folder_id = _open()
    sh = _structure(gc, drive, folder_id)
    log = sh.worksheet(ACTIVITY_SHEET)
    records = log.get_all_records()  # list of dicts keyed by header

    month_rows = [row for row in records
                  if str(row.get("Email Date", "")).startswith(month)]
    ranked = sorted(
        month_rows,
        key=lambda row: if_by_abbr.get(row.get("Journal", ""), 0.0),
        reverse=True,
    )[:5]

    out = [TOP5_HEADERS]
    for rank, row in enumerate(ranked, 1):
        out.append([
            rank,
            row.get("Email Date", ""),
            row.get("Journal", ""),
            row.get("Title", ""),
            if_by_abbr.get(row.get("Journal", ""), ""),
            row.get("DOI", ""),
            row.get("Open Access", ""),
        ])
    ws = sh.worksheet(TOP5_SHEET)
    ws.clear()
    ws.update(range_name="A1", values=out, value_input_option="USER_ENTERED")
    ws.format("A1:G1", {"textFormat": {"bold": True}})
    logger.info(f"Updated '{TOP5_SHEET}' for {month}: {len(ranked)} articles")
    return sh.url


# ── Live summary ─────────────────────────────────────────────────────────────

def _months_present(sh) -> list:
    """Distinct YYYY-MM across both logs, sorted ascending."""
    months = set()
    for sheet, col in ((ACTIVITY_SHEET, 1), (CME_SHEET, 1)):
        try:
            vals = sh.worksheet(sheet).col_values(col)[1:]  # skip header
        except Exception:
            vals = []
        for v in vals:
            v = str(v).strip()
            if len(v) >= 7:
                months.add(v[:7])
    return sorted(months)


def _refresh_summary(sh):
    """Rewrite the Summary tab with LIVE per-month formulas referencing the logs.

    Month labels + structure are regenerated each run, but every count/total is a
    formula over the logs, so manual Hours edits flow through automatically.
    """
    months = _months_present(sh)
    A = f"'{ACTIVITY_SHEET}'!$A$2:$A${_LOG_MAXROW}"
    AH = f"'{ACTIVITY_SHEET}'!$H$2:$H${_LOG_MAXROW}"
    C = f"'{CME_SHEET}'!$A$2:$A${_LOG_MAXROW}"
    CE = f"'{CME_SHEET}'!$E$2:$E${_LOG_MAXROW}"

    header = ["Month", "S2 Articles", "S2 Hours", "S2 Credits",
              "CME Activities", "S3 Hours", "S3 Credits"]
    values = [header]
    first_data_row = 2
    for idx, m in enumerate(months):
        r = first_data_row + idx
        mref = f"$A{r}"
        values.append([
            m,
            f'=SUMPRODUCT((LEFT({A},7)={mref})*1)',
            f'=SUMPRODUCT((LEFT({A},7)={mref})*IFERROR({AH}*1,0))',
            f"=C{r}*2",
            f'=SUMPRODUCT((LEFT({C},7)={mref})*1)',
            f'=SUMPRODUCT((LEFT({C},7)={mref})*IFERROR({CE}*1,0))',
            f"=F{r}*2",
        ])
    total_r = first_data_row + len(months)
    if months:
        rng = f"{first_data_row}:{total_r - 1}"
        values.append([
            "TOTAL",
            f"=SUM(B{rng})", f"=SUM(C{rng})", f"=SUM(D{rng})",
            f"=SUM(E{rng})", f"=SUM(F{rng})", f"=SUM(G{rng})",
        ])
    else:
        values.append(["TOTAL", 0, 0, 0, 0, 0, 0])

    ws = sh.worksheet(SUMMARY_SHEET)
    ws.clear()
    ws.update(range_name="A1", values=values, value_input_option="USER_ENTERED")
    ws.format("A1:G1", {"textFormat": {"bold": True}})
    ws.format(f"A{total_r}:G{total_r}", {"textFormat": {"bold": True}})


def refresh_summary() -> str:
    """Public: ensure structure and refresh the live Summary. Returns URL."""
    sh = _structure()
    _refresh_summary(sh)
    return sh.url


def spreadsheet_url() -> str:
    """Ensure structure exists and return the spreadsheet URL."""
    return _structure().url
