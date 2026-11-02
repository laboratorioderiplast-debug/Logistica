"""
Generazione del PDF del certificato EN 10204 MOD. 3.1, replicando il
layout del certificato Deriplast Group allegato:
  - logo in testata (ripetuto piccolo su ogni pagina)
  - titolo con doppia riga blu
  - tabella dati (Id Certificate, Line, DN, SDR, Date, Article, ecc.)
  - sezioni di prova separate da barre blu, righe con "Conformity"
    e colonne di valori variabili
  - piede pagina con luogo/data, "Prepared" / "Approved" e firma
  - numero di pagina "Pagina X di Y"
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
)

from .config import get_config

NAVY = colors.HexColor("#33339A")
GREY_LINE = colors.HexColor("#bbbbbb")

PAGE_W, PAGE_H = A4
MARGIN = 1.3 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ---------------------------------------------------------------------------
# Stili
# ---------------------------------------------------------------------------
style_title = ParagraphStyle(
    "TitoloCert", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER,
    textColor=colors.black, spaceBefore=2, spaceAfter=2,
)
style_label_bold = ParagraphStyle("LabelBold", fontName="Helvetica-Bold", fontSize=8.5, leading=10)
style_value = ParagraphStyle("Value", fontName="Helvetica", fontSize=8.5, leading=10)
style_desc = ParagraphStyle("Desc", fontName="Helvetica", fontSize=8, leading=10)
style_stack = ParagraphStyle("Stack", fontName="Helvetica", fontSize=8, leading=10, alignment=TA_CENTER)
style_footer_label = ParagraphStyle("FooterLabel", fontName="Helvetica-Bold", fontSize=9, leading=12)
style_footer_value = ParagraphStyle("FooterValue", fontName="Helvetica", fontSize=9, leading=12)


def _stacked(label, value):
    label = label or ""
    value = value if value not in (None, "") else "&nbsp;"
    return Paragraph(f"<b>{label}</b><br/>{value}", style_stack)


# ---------------------------------------------------------------------------
# Canvas personalizzato per numerazione "Pagina X di Y" + logo ripetuto
# ---------------------------------------------------------------------------
class _CertCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, logo_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []
        self._logo_path = logo_path

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_page_furniture(total)
            super().showPage()
        super().save()

    def _draw_page_furniture(self, total_pages):
        # Logo piccolo ripetuto in alto (come pagina 2 del certificato originale)
        if self._logo_path and os.path.exists(self._logo_path):
            try:
                from PIL import Image as PILImage
                with PILImage.open(self._logo_path) as im:
                    ratio = im.height / im.width
                h = 1.0 * cm
                w = h / ratio
                self.drawImage(
                    self._logo_path,
                    (PAGE_W - w) / 2.0,
                    PAGE_H - MARGIN - h + 0.3 * cm,
                    width=w, height=h,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                pass

        # Numero di pagina in basso a destra
        self.setFont("Helvetica-Oblique", 7.5)
        self.setFillColor(colors.HexColor("#333333"))
        text = f"Pagina {self._pageNumber} di {total_pages}"
        self.drawRightString(PAGE_W - MARGIN, MARGIN * 0.4, text)


def _make_canvas_factory(logo_path):
    def _factory(*args, **kwargs):
        return _CertCanvas(*args, logo_path=logo_path, **kwargs)
    return _factory


# ---------------------------------------------------------------------------
# Costruzione del contenuto (Platypus "story")
# ---------------------------------------------------------------------------
def _build_header_table(header, ragione_sociale):
    rows = [
        [Paragraph("Id Certificate", style_label_bold), Paragraph(header.get("id_certificate", ""), style_value),
         Paragraph("Line", style_label_bold), Paragraph(header.get("line", ""), style_value),
         Paragraph("DN", style_label_bold), Paragraph(header.get("dn", ""), style_value),
         Paragraph("SDR", style_label_bold), Paragraph(header.get("sdr", ""), style_value),
         Paragraph("Date", style_label_bold), Paragraph(header.get("date", ""), style_value)],
        [Paragraph("Article - HDPE PIPE", style_label_bold), Paragraph(header.get("article", ""), style_value),
         "", "", "", "", "", "", "", ""],
        [Paragraph("Ref. Standard", style_label_bold), Paragraph(header.get("ref_standard", ""), style_value),
         "", "", "", "", "", "", "", ""],
        [Paragraph("Lot 1 Raw material", style_label_bold), Paragraph(header.get("lot1", ""), style_value),
         "", "", "", "", "", "", "", ""],
        [Paragraph("Lot 2 Raw material", style_label_bold), Paragraph(header.get("lot2", ""), style_value),
         "", "", "", "", "", "", "", ""],
        [Paragraph("Production Batch", style_label_bold), Paragraph(header.get("production_batch", ""), style_value),
         "", "", "", "", "", "", "", ""],
        [Paragraph("Notes", style_label_bold), Paragraph(header.get("notes", ""), style_value),
         "", "", "", "", "", "", "", ""],
    ]
    col_w = [3.0 * cm, 3.0 * cm, 1.3 * cm, 1.3 * cm, 1.1 * cm, 1.3 * cm, 1.1 * cm, 1.3 * cm, 1.3 * cm, CONTENT_W]
    # ricalcolo per far tornare la somma esattamente a CONTENT_W
    fixed = [3.0, 1.6, 1.3, 1.3, 1.1, 1.3, 1.1, 1.3, 1.3]
    last = CONTENT_W - sum(c * cm for c in fixed)
    col_w = [c * cm for c in fixed] + [last]

    t = Table(rows, colWidths=col_w)
    style = [
        ("SPAN", (1, 1), (9, 1)),
        ("SPAN", (1, 2), (9, 2)),
        ("SPAN", (1, 3), (9, 3)),
        ("SPAN", (1, 4), (9, 4)),
        ("SPAN", (1, 5), (9, 5)),
        ("SPAN", (1, 6), (9, 6)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, GREY_LINE, 1, (2, 2)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]
    t.setStyle(TableStyle(style))
    return t


def _make_row_flowable(row, content_w):
    desc = row.get("desc", "")
    conf_label = row.get("conf_label", "Conformity")
    conf_value = row.get("conf_value", "Pos")
    columns = row.get("columns", []) or []

    blocks = [_stacked(conf_label, conf_value)]
    for c in columns:
        blocks.append(_stacked(c.get("label", ""), c.get("value", "")))

    desc_w = content_w * 0.44
    right_w = content_w - desc_w
    n = len(blocks)

    # La prima colonna ("Conformity") ha bisogno di piu' spazio delle altre
    # (parola piu' lunga), altrimenti va a capo in modo brutto.
    conf_w = min(2.3 * cm, right_w * 0.32) if n > 1 else right_w
    other_w = (right_w - conf_w) / (n - 1) if n > 1 else 0
    col_widths = [conf_w] + [other_w] * (n - 1) if n > 1 else [conf_w]

    inner = Table([blocks], colWidths=col_widths)
    inner.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    outer = Table([[Paragraph(desc, style_desc), inner]], colWidths=[desc_w, right_w])
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, GREY_LINE, None, (2, 2)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, 0), 2),
        ("RIGHTPADDING", (0, 0), (0, 0), 6),
    ]))
    return outer


def _divider_bar():
    t = Table([[""]], colWidths=[CONTENT_W], rowHeights=[0.3 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY)]))
    return t


def _footer_flowable(footer, firma_path):
    loc_para = Paragraph(
        f"<b>{footer.get('location','')}</b>, {footer.get('date','')}", style_footer_value
    )

    sig_cell = [
        Paragraph(f"Prepared {footer.get('prepared_by','')}", style_footer_label),
        Spacer(1, 10),
        Paragraph(f"Approved {footer.get('approved_by','')}", style_footer_label),
    ]
    if firma_path and os.path.exists(firma_path):
        try:
            from PIL import Image as PILImage
            with PILImage.open(firma_path) as im:
                ratio = im.height / im.width
            h = 1.3 * cm
            w = h / ratio
            sig_cell.append(Spacer(1, 2))
            sig_cell.append(Image(firma_path, width=w, height=h, hAlign="RIGHT"))
        except Exception:
            pass

    right_table = Table([[c] for c in sig_cell], colWidths=[6 * cm])
    right_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    t = Table([[loc_para, right_table]], colWidths=[CONTENT_W - 6 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, GREY_LINE, None, (2, 2)),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def genera_pdf(dati_certificato, percorso_output):
    """
    dati_certificato: dict con chiavi "header", "sections", "footer"
    (vedi app.modelli_certificato).
    percorso_output: percorso del file .pdf da creare.
    """
    cfg = get_config()
    logo_path = cfg.logo_path()
    firma_path = cfg.firma_path()

    doc = SimpleDocTemplate(
        percorso_output, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN + 1.1 * cm, bottomMargin=MARGIN,
        title="Certificate of control laboratory EN10204 MOD. 3.1",
    )

    story = []

    # Logo grande in testa (solo inizio documento, poi si ripete piccolo su ogni pagina)
    if os.path.exists(logo_path):
        try:
            from PIL import Image as PILImage
            with PILImage.open(logo_path) as im:
                ratio = im.height / im.width
            w = 6.5 * cm
            h = w * ratio
            story.append(Image(logo_path, width=w, height=h, hAlign="CENTER"))
        except Exception:
            pass
    story.append(Spacer(1, 6))

    title_tbl = Table(
        [[Paragraph("Certificate of control laboratory EN10204 MOD. 3.1", style_title)]],
        colWidths=[CONTENT_W],
    )
    title_tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 2, NAVY),
        ("LINEBELOW", (0, 0), (-1, 0), 2, NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 6))

    story.append(_build_header_table(dati_certificato.get("header", {}), cfg.ragione_sociale))
    story.append(Spacer(1, 4))

    sections = dati_certificato.get("sections", [])
    for i, section in enumerate(sections):
        rows_flowables = [_make_row_flowable(r, CONTENT_W) for r in section.get("rows", [])]
        story.append(KeepTogether(rows_flowables) if len(rows_flowables) <= 1 else rows_flowables[0])
        for rf in rows_flowables[1:]:
            story.append(rf)
        if i < len(sections) - 1:
            story.append(Spacer(1, 3))
            story.append(_divider_bar())
            story.append(Spacer(1, 3))

    story.append(Spacer(1, 6))

    footer = dati_certificato.get("footer", {})
    if footer.get("notes"):
        story.append(Paragraph(f"<b>Notes</b><br/>{footer['notes']}", style_value))
        story.append(Spacer(1, 4))

    story.append(_footer_flowable(footer, firma_path))

    doc.build(story, canvasmaker=_make_canvas_factory(logo_path))
    return percorso_output
