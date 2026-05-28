"""PDF invoice generator using ReportLab."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

NAVY = colors.HexColor("#0B1020")
SLATE = colors.HexColor("#8FA9C7")
OFFWHITE = colors.HexColor("#F5F7FA")
CHARCOAL = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")


def generate_invoice_pdf(invoice: dict) -> bytes:
    """Generate an invoice PDF. `invoice` is a dict with required keys."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Invoice {invoice['invoice_number']}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=26, textColor=NAVY, leading=30,
    )
    small = ParagraphStyle(
        "small", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, textColor=MUTED, leading=12,
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=CHARCOAL, leading=14,
    )
    bold = ParagraphStyle(
        "bold", parent=body, fontName="Helvetica-Bold", textColor=NAVY,
    )
    right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT)

    story = []

    # Header
    header = Table(
        [[
            Paragraph("<b>VOIDD HIRE</b><br/><font size=8 color='#8FA9C7'>BUILT FOR BETTER HIRING</font>", title_style),
            Paragraph(
                f"<b>INVOICE</b><br/>"
                f"<font size=9 color='#6B7280'>#{invoice['invoice_number']}</font><br/>"
                f"<font size=9 color='#6B7280'>Date: {invoice.get('date') or ''}</font>",
                right,
            ),
        ]],
        colWidths=[100 * mm, 70 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=SLATE))
    story.append(Spacer(1, 14))

    # From / Bill To
    from_block = (
        "<b>From</b><br/>"
        "VOIDD Hire<br/>"
        "Recruitment Operations<br/>"
        "Nigdi, Pimpri-Chinchwad, Pune 411033<br/>"
        "+91 87936 67303<br/>"
        "hello@voiddhire.com"
    )
    to_block = (
        f"<b>Bill To</b><br/>"
        f"{invoice.get('company_name') or ''}<br/>"
        f"{(invoice.get('company_address') or '').replace(chr(10), '<br/>')}<br/>"
        f"{invoice.get('company_email') or ''}<br/>"
        f"{('GSTIN: ' + invoice['company_gstin']) if invoice.get('company_gstin') else ''}"
    )
    parties = Table(
        [[Paragraph(from_block, body), Paragraph(to_block, body)]],
        colWidths=[85 * mm, 85 * mm],
    )
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(parties)
    story.append(Spacer(1, 20))

    # Items table
    data = [
        [Paragraph("<b>Description</b>", bold),
         Paragraph("<b>Candidate</b>", bold),
         Paragraph("<b>Date</b>", bold),
         Paragraph("<b>Amount</b>", bold)],
        [
            Paragraph(f"Placement Fee — {invoice.get('role') or ''}", body),
            Paragraph(invoice.get("candidate_name") or "—", body),
            Paragraph(invoice.get("placement_date") or "—", body),
            Paragraph(f"₹ {invoice['placement_fee']:,.2f}", right),
        ],
    ]
    items = Table(data, colWidths=[70 * mm, 45 * mm, 25 * mm, 30 * mm])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), OFFWHITE),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, SLATE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(items)
    story.append(Spacer(1, 16))

    # Totals
    subtotal = float(invoice["placement_fee"])
    gst_rate = float(invoice.get("gst_rate", 18.0))
    gst_amount = round(subtotal * gst_rate / 100, 2)
    total = round(subtotal + gst_amount, 2)

    totals = Table(
        [
            ["Subtotal", f"₹ {subtotal:,.2f}"],
            [f"GST ({gst_rate:.0f}%)", f"₹ {gst_amount:,.2f}"],
            ["Total Due", f"₹ {total:,.2f}"],
        ],
        colWidths=[40 * mm, 30 * mm],
        hAlign="RIGHT",
    )
    totals.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, -2), CHARCOAL),
        ("TEXTCOLOR", (0, -1), (-1, -1), NAVY),
        ("FONTSIZE", (0, 0), (-1, -2), 10),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, SLATE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(totals)
    story.append(Spacer(1, 30))

    if invoice.get("notes"):
        story.append(Paragraph("<b>Notes</b>", bold))
        story.append(Spacer(1, 4))
        story.append(Paragraph(invoice["notes"], body))
        story.append(Spacer(1, 20))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Payment due within 15 days. Bank transfer / UPI preferred. "
        "For queries reach out to hello@voiddhire.com.",
        small,
    ))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    return pdf
