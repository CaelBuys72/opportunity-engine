"""Build 6 — format-specific artifact builders + structural validators.

Each format has its own builder (no single giant writer). Files produced are
REAL for their format (validated by re-opening). PDF rendering is attempted only
if a real renderer is available (reportlab / soffice); otherwise render_pdf
returns (None, reason) and the caller marks the PDF format BLOCKED — never faked.
"""
from __future__ import annotations
import csv as _csv
import shutil
import subprocess
from pathlib import Path

from openpyxl import Workbook, load_workbook
from docx import Document


# ---------------------------------------------------------------- XLSX + CSV
def build_xlsx(path: Path, sheets: list[dict]) -> Path:
    """sheets: [{name, instructions?, headers:[...], rows:[[...]], formulas?:{colIndex:template}}]"""
    wb = Workbook()
    wb.remove(wb.active)
    for sh in sheets:
        ws = wb.create_sheet(title=sh["name"][:31])
        r = 1
        if sh.get("instructions"):
            ws.cell(row=r, column=1, value=f"INSTRUCTIONS: {sh['instructions']}")
            r += 2
        headers = sh["headers"]
        for c, h in enumerate(headers, 1):
            ws.cell(row=r, column=c, value=h)
        header_row = r
        for row in sh.get("rows", []):
            r += 1
            for c, val in enumerate(row, 1):
                ws.cell(row=r, column=c, value=val)
        # optional per-column formulas applied to each data row
        for col_idx, tmpl in (sh.get("formulas") or {}).items():
            for dr in range(header_row + 1, r + 1):
                ws.cell(row=dr, column=col_idx, value=tmpl.format(row=dr))
        for c in range(1, len(headers) + 1):
            ws.column_dimensions[ws.cell(row=header_row, column=c).column_letter].width = 20
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def build_csv(path: Path, headers: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return path


# ---------------------------------------------------------------- DOCX
def build_docx(path: Path, title: str, blocks: list[dict]) -> Path:
    """blocks: [{type: heading|para|bullet|check|field, text|items|label}]"""
    doc = Document()
    doc.add_heading(title, level=0)
    for b in blocks:
        t = b["type"]
        if t == "heading":
            doc.add_heading(b["text"], level=b.get("level", 1))
        elif t == "para":
            doc.add_paragraph(b["text"])
        elif t == "bullet":
            for it in b["items"]:
                doc.add_paragraph(it, style="List Bullet")
        elif t == "number":
            for it in b["items"]:
                doc.add_paragraph(it, style="List Number")
        elif t == "check":
            for it in b["items"]:
                doc.add_paragraph(f"☐  {it}")   # ballot box
        elif t == "field":
            doc.add_paragraph(f"{b['label']}: {b.get('placeholder', '__________')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return path


def build_markdown(path: Path, title: str, blocks: list[dict]) -> Path:
    lines = [f"# {title}", ""]
    for b in blocks:
        t = b["type"]
        if t == "heading":
            lines.append(f"{'#' * (b.get('level', 1) + 1)} {b['text']}"); lines.append("")
        elif t == "para":
            lines.append(b["text"]); lines.append("")
        elif t in ("bullet", "check"):
            pre = "- [ ] " if t == "check" else "- "
            lines += [pre + it for it in b["items"]]; lines.append("")
        elif t == "number":
            lines += [f"{i}. {it}" for i, it in enumerate(b["items"], 1)]; lines.append("")
        elif t == "field":
            lines.append(f"**{b['label']}:** {b.get('placeholder', '__________')}"); lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path


# ---------------------------------------------------------------- EBOOK (single sellable PDF)
def build_ebook_pdf(path: Path, title: str, subtitle: str, chapters: list[dict],
                    accent: str = "#6C4CF1") -> Path:
    """Compile document chapters into ONE clean, sellable PDF ebook:
    cover page + table of contents (auto page numbers) + styled chapters + footer.
    chapters: [{"title": str, "blocks": [ {type: heading|para|bullet|number|check|field} ]}]"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                    ListFlowable, ListItem)
    from reportlab.platypus.tableofcontents import TableOfContents

    ACCENT = colors.HexColor(accent)
    INK = colors.HexColor("#1a1a2e")
    MUTED = colors.HexColor("#6b7280")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=ss["BodyText"], fontName="Helvetica",
                          fontSize=10.5, leading=15.5, textColor=INK, spaceAfter=7)
    chap = ParagraphStyle("ChapterTitle", parent=ss["Heading1"], fontName="Helvetica-Bold",
                          fontSize=20, leading=24, textColor=ACCENT, spaceBefore=4, spaceAfter=14)
    sect = ParagraphStyle("Section", parent=ss["Heading1"], fontName="Helvetica-Bold",
                          fontSize=20, leading=24, textColor=ACCENT, spaceAfter=14)
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                        fontSize=13, leading=17, textColor=INK, spaceBefore=10, spaceAfter=5)
    li = ParagraphStyle("Li", parent=body, spaceAfter=3)
    fld = ParagraphStyle("Fld", parent=body, textColor=MUTED, spaceAfter=5)

    # Helvetica (WinAnsi) can't render smart quotes / unicode dashes → they show as
    # tofu boxes. Normalise to safe equivalents before drawing anything.
    _SUBS = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-",
             "—": " - ", "‑": "-", "‐": "-", "−": "-", "…": "...",
             "•": "-", " ": " ", "■": "", "﻿": ""}

    def safe(t):
        s = str(t)
        for k, v in _SUBS.items():
            s = s.replace(k, v)
        return s.encode("latin-1", "ignore").decode("latin-1")   # drop remaining non-WinAnsi

    def esc(t):  # for Paragraph markup (safe() first, then HTML-escape)
        return safe(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def render(b):
        t = b.get("type")
        if t == "heading":
            return [Paragraph(esc(b.get("text", "")), h2)]
        if t == "para":
            return [Paragraph(esc(b.get("text", "")), body)]
        if t in ("bullet", "number"):
            items = [ListItem(Paragraph(esc(x), li)) for x in b.get("items", [])]
            return [ListFlowable(items, bulletType="1" if t == "number" else "bullet",
                                 leftIndent=16), Spacer(1, 4)]
        if t == "check":
            return [Paragraph("[ &nbsp; ]&nbsp;&nbsp;" + esc(x), li) for x in b.get("items", [])] + [Spacer(1, 4)]
        if t == "field":
            return [Paragraph(f"<b>{esc(b.get('label',''))}:</b> " + "_" * 28, fld)]
        return []

    def draw_cover(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setFillColor(ACCENT); canvas.rect(0, h - 6 * cm, w, 6 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white); canvas.setFont("Helvetica-Bold", 26)
        for i, line in enumerate(_wrap(safe(title), 30)[:3]):
            canvas.drawString(2 * cm, h - 2.6 * cm - i * 1.0 * cm, line)
        canvas.setFillColor(INK); canvas.setFont("Helvetica", 13)
        for i, line in enumerate(_wrap(safe(subtitle or ""), 60)[:3]):
            canvas.drawString(2 * cm, h - 8 * cm - i * 0.7 * cm, line)
        canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 9)
        canvas.drawString(2 * cm, 2 * cm, "Produced by the Opportunity Engine")
        canvas.restoreState()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8); canvas.setFillColor(MUTED)
        canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
        canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
        canvas.drawString(2 * cm, 1.05 * cm, safe(title)[:70])
        canvas.drawRightString(A4[0] - 2 * cm, 1.05 * cm, str(doc.page))
        canvas.restoreState()

    class EbookDoc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph) and flowable.style.name == "ChapterTitle":
                self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = EbookDoc(str(path), pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                   leftMargin=2 * cm, rightMargin=2 * cm, title=title)
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("TOC0", fontName="Helvetica", fontSize=11.5,
                                      leading=20, textColor=INK)]
    story = [PageBreak(), Paragraph("Contents", sect), toc, PageBreak()]
    for ch in chapters:
        story.append(Paragraph(esc(ch.get("title", "")), chap))
        for b in ch.get("blocks", []):
            story.extend(render(b))
        story.append(PageBreak())
    doc.multiBuild(story, onFirstPage=draw_cover, onLaterPages=footer)
    return path


def _wrap(text, width):
    words, lines, cur = str(text).split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 <= width:
            cur = (cur + " " + wd).strip()
        else:
            lines.append(cur); cur = wd
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------- PDF (real only)
def pdf_available() -> tuple[bool, str]:
    try:
        import reportlab  # noqa
        return True, "reportlab"
    except Exception:
        pass
    for b in ("soffice", "libreoffice"):
        if shutil.which(b):
            return True, b
    return False, "no PDF renderer (reportlab/soffice/libreoffice) available in this environment"


def build_pdf(path: Path, title: str, blocks: list[dict]) -> tuple[Path | None, str]:
    """Render component content directly to a REAL PDF via reportlab (preferred).
    Returns (path, tool) or (None, reason). No faking."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_LEFT
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        ListFlowable, ListItem)
    except Exception as e:
        return None, f"reportlab unavailable: {e}"
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=20, spaceAfter=12, alignment=TA_LEFT)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10.5, leading=15, spaceAfter=4)
    field = ParagraphStyle("field", parent=body, spaceAfter=8)
    story = [Paragraph(title, h1)]
    for b in blocks:
        t = b["type"]
        if t == "heading":
            story.append(Paragraph(b["text"], h2))
        elif t == "para":
            story.append(Paragraph(b["text"], body))
        elif t in ("bullet", "check"):
            marks = ["☐&nbsp; " + it if t == "check" else it for it in b["items"]]
            story.append(ListFlowable([ListItem(Paragraph(m, body), leftIndent=14,
                                                 bulletColor="white" if t == "check" else "black")
                                       for m in marks],
                                      bulletType="bullet" if t == "bullet" else "bullet",
                                      start="square" if t == "bullet" else None))
        elif t == "number":
            story.append(ListFlowable([ListItem(Paragraph(it, body)) for it in b["items"]],
                                      bulletType="1"))
        elif t == "field":
            story.append(Paragraph(f"<b>{b['label']}:</b> "
                                   f"{b.get('placeholder', '_' * 34)}", field))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        SimpleDocTemplate(str(path), pagesize=LETTER,
                          topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                          leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                          title=title).build(story)
        return path, "reportlab"
    except Exception as e:
        return None, f"reportlab build failed: {e}"


def render_pdf(docx_path: Path, out_path: Path) -> tuple[Path | None, str]:
    ok, tool = pdf_available()
    if not ok:
        return None, tool
    if tool == "reportlab":
        return None, "reportlab present but docx->pdf conversion path not implemented"  # honest: no fake
    try:
        subprocess.run([tool, "--headless", "--convert-to", "pdf", "--outdir",
                        str(out_path.parent), str(docx_path)], check=True,
                       capture_output=True, timeout=120)
        produced = out_path.parent / (docx_path.stem + ".pdf")
        if produced.exists():
            if produced != out_path:
                produced.rename(out_path)
            return out_path, tool
        return None, "conversion produced no file"
    except Exception as e:
        return None, f"conversion failed: {e}"


# ---------------------------------------------------------------- structural validators
def validate_xlsx(path: Path, expect_sheets: list[str] | None = None) -> list[str]:
    errs = []
    try:
        wb = load_workbook(path)
    except Exception as e:
        return [f"xlsx will not open: {e}"]
    for s in (expect_sheets or []):
        if s[:31] not in wb.sheetnames:
            errs.append(f"missing sheet '{s}'")
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith("="):
                    if v.count("(") != v.count(")"):
                        errs.append(f"{ws.title}!{cell.coordinate}: unbalanced formula parens")
                    if "#REF!" in v:
                        errs.append(f"{ws.title}!{cell.coordinate}: #REF!")
    return errs


def validate_docx(path: Path) -> list[str]:
    try:
        doc = Document(path)
    except Exception as e:
        return [f"docx will not open: {e}"]
    if not any(p.text.strip() for p in doc.paragraphs):
        return ["docx has no text content"]
    return []


def validate_pdf(path: Path) -> list[str]:
    try:
        head = path.read_bytes()[:5]
    except Exception as e:
        return [f"pdf unreadable: {e}"]
    return [] if head.startswith(b"%PDF-") else ["not a valid PDF (missing %PDF- header)"]
