"""Build a Word (.docx) manuscript section from the report the researcher assembled.

The interface sends plain text and simple tables (already in the chosen language); this module only
lays them out: headings, paragraphs, three-line APA tables with captions and notes, and right-to-left
paragraphs for Arabic.
"""
from __future__ import annotations

import io

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

MAX_SECTIONS = 60
MAX_TABLE_ROWS = 400
MAX_TEXT = 20_000


def _clean(value, limit=MAX_TEXT) -> str:
    text = "" if value is None else str(value)
    # Strip control characters Word rejects.
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    return text[:limit]


def _rtl(paragraph):
    properties = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    properties.append(bidi)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in paragraph.runs:
        run_properties = run._r.get_or_add_rPr()
        run_properties.append(OxmlElement("w:rtl"))


def _border(cell, edges, size=8):
    properties = cell._tc.get_or_add_tcPr()
    borders = properties.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        properties.append(borders)
    for edge in edges:
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))
        element.set(qn("w:color"), "000000")
        borders.append(element)


def _paragraph(document, text, arabic, style=None, size=None, bold=False, italic=False):
    paragraph = document.add_paragraph(style=style)
    run = paragraph.add_run(_clean(text))
    run.bold, run.italic = bold, italic
    if size:
        run.font.size = Pt(size)
    if arabic:
        _rtl(paragraph)
    return paragraph


def _table(document, spec, arabic):
    columns = [_clean(c, 200) for c in (spec.get("columns") or [])][:12]
    rows = [[_clean(cell, 500) for cell in row][: len(columns)] for row in (spec.get("rows") or [])[:MAX_TABLE_ROWS]]
    if not columns:
        return
    if spec.get("caption"):
        _paragraph(document, spec["caption"], arabic, bold=True, size=11)
    table = document.add_table(rows=1 + len(rows), cols=len(columns))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for index, name in enumerate(columns):
        cell = table.rows[0].cells[index]
        cell.text = name
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(10)
        _border(cell, ["top", "bottom"], 12)
    for row_index, row in enumerate(rows, start=1):
        for column_index in range(len(columns)):
            cell = table.rows[row_index].cells[column_index]
            cell.text = row[column_index] if column_index < len(row) else ""
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(10)
            if column_index:
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT if not arabic else WD_ALIGN_PARAGRAPH.LEFT
            if row_index == len(rows):
                _border(cell, ["bottom"], 12)
    if spec.get("note"):
        _paragraph(document, spec["note"], arabic, size=9, italic=True)


def build(report: dict) -> bytes:
    arabic = report.get("lang") == "ar"
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman" if not arabic else "Arial"
    normal.font.size = Pt(12)
    title = _clean(report.get("title") or ("تقرير التحليل الإحصائي" if arabic else "Statistical analysis report"), 300)
    heading = document.add_heading(title, level=1)
    if arabic:
        _rtl(heading)
    if report.get("subtitle"):
        _paragraph(document, report["subtitle"], arabic, size=10, italic=True)
    for section in (report.get("sections") or [])[:MAX_SECTIONS]:
        if not isinstance(section, dict):
            continue
        if section.get("heading"):
            sub = document.add_heading(_clean(section["heading"], 300), level=2)
            if arabic:
                _rtl(sub)
        for text in section.get("paragraphs") or []:
            _paragraph(document, text, arabic)
        for spec in section.get("tables") or []:
            if isinstance(spec, dict):
                _table(document, spec, arabic)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
