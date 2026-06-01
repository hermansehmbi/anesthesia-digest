"""
Anesthesia Journal Digest — RCPSC MOC Tracker
"""

import logging
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)
MOC_FILE = "moc_tracker.xlsx"


def get_or_create(filepath: str = MOC_FILE) -> openpyxl.Workbook:
    if Path(filepath).exists():
        return openpyxl.load_workbook(filepath)
    return _create_new()


def log_articles(articles: list, filepath: str = MOC_FILE):
    """Log articles as Section 2 (self-learning) candidates. User fills in hours/credits."""
    wb = get_or_create(filepath)
    ws = wb["Activity Log"]

    for art in articles:
        r = ws.max_row + 1
        ws.cell(r, 1, value=art.get("date_str", datetime.now().strftime("%Y-%m-%d")))
        ws.cell(r, 2, value="Section 2")
        ws.cell(r, 3, value="Journal Article")
        ws.cell(r, 4, value=art.get("title", "")[:100])
        ws.cell(r, 5, value=art.get("journal", ""))
        ws.cell(r, 6, value=art.get("doi", ""))
        ws.cell(r, 7, value=art.get("url", ""))
        ws.cell(r, 8, value="")  # Hours — user fills
        ws.cell(r, 9, value="")  # Credits — user fills
        ws.cell(r, 10, value="Open Access" if art.get("is_open_access") else "Subscription")
        ws.cell(r, 11, value="")  # Notes — user fills

    wb.save(filepath)
    logger.info(f"Logged {len(articles)} articles to MOC tracker")


def log_cme(questions: list, filepath: str = MOC_FILE):
    """Log CME questions completed as Section 3 (self-assessment) entries."""
    wb = get_or_create(filepath)
    ws = wb["Activity Log"]

    today = datetime.now().strftime("%Y-%m-%d")
    r = ws.max_row + 1
    ws.cell(r, 1, value=today)
    ws.cell(r, 2, value="Section 3")
    ws.cell(r, 3, value="Self-Assessment (AI-generated CME)")
    ws.cell(r, 4, value=f"Weekly CME — {len(questions)} questions")
    ws.cell(r, 5, value="Multiple journals")
    ws.cell(r, 6, value="")
    ws.cell(r, 7, value="")
    ws.cell(r, 8, value="")  # Hours — user fills
    ws.cell(r, 9, value="")  # Credits — user fills
    ws.cell(r, 10, value="")
    ws.cell(r, 11, value="; ".join(q.get("source_journal", "") for q in questions))

    wb.save(filepath)
    logger.info("Logged weekly CME to MOC tracker")


def update_summary(filepath: str = MOC_FILE):
    wb = get_or_create(filepath)
    ws_log = wb["Activity Log"]
    ws_sum = wb["Summary"]

    counts = {"Section 1": 0, "Section 2": 0, "Section 3": 0}
    for row in ws_log.iter_rows(min_row=2, values_only=True):
        sec = str(row[1]) if row[1] else ""
        if sec in counts:
            counts[sec] += 1

    ws_sum["B4"] = counts["Section 1"]
    ws_sum["B5"] = counts["Section 2"]
    ws_sum["B6"] = counts["Section 3"]
    ws_sum["B7"] = sum(counts.values())
    ws_sum["B9"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    wb.save(filepath)
    logger.info("Updated MOC summary")


def _create_new() -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    hfont = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="1A5276", end_color="1A5276", fill_type="solid")

    # Summary sheet
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "RCPSC MOC Activity Tracker"
    ws["A1"].font = Font(bold=True, size=14, color="1A5276")
    ws["A2"] = "Anesthesiology — Maintenance of Certification"
    ws["A2"].font = Font(size=11, color="888888")

    for col, h in [(2, "Count"), (3, "Hours"), (4, "Credits")]:
        ws.cell(3, col, value=h).font = Font(bold=True)
    ws["A4"] = "Section 1 — Group Learning"
    ws["A5"] = "Section 2 — Self-Learning"
    ws["A6"] = "Section 3 — Self-Assessment"
    ws["A7"] = "TOTAL"
    ws["A7"].font = Font(bold=True)
    for r in range(4, 8):
        for c in range(2, 5):
            ws.cell(r, c, value=0)

    ws["A9"] = "Last Updated:"
    ws["B9"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws["A11"] = "RCPSC: 40 credits/year minimum. Section 2 = 2 credits/hr. Section 3 = 2 credits/hr."
    ws["A11"].font = Font(italic=True, color="888888", size=10)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 12

    # Activity Log
    ws2 = wb.create_sheet("Activity Log")
    headers = ["Date", "RCPSC Section", "Activity Type", "Title", "Journal",
               "DOI", "URL", "Hours", "Credits", "Access Type", "Notes"]
    widths = [12, 14, 22, 50, 18, 25, 35, 8, 8, 14, 30]
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws2.cell(1, i, value=h)
        cell.font = hfont
        cell.fill = hfill
        ws2.column_dimensions[get_column_letter(i)].width = w
    ws2.freeze_panes = "A2"

    # Journal Reference
    ws3 = wb.create_sheet("Journal Reference")
    ws3["A1"] = "Tracked Journals"
    ws3["A1"].font = Font(bold=True, size=14, color="1A5276")
    for i, h in enumerate(["Journal", "Abbreviation", "ISSN", "IF", "Podcast"], 1):
        cell = ws3.cell(3, i, value=h)
        cell.font = hfont
        cell.fill = hfill
    from config import JOURNALS
    for i, j in enumerate(JOURNALS, 4):
        ws3.cell(i, 1, value=j["name"])
        ws3.cell(i, 2, value=j["abbreviation"])
        ws3.cell(i, 3, value=j["issn"])
        ws3.cell(i, 4, value=j["impact_factor"])
        ws3.cell(i, 5, value="Yes" if j.get("podcast") else "No")
    ws3.column_dimensions["A"].width = 45

    return wb
