"""
Generates PDF invoices for orders using ReportLab.

Returns PDF as bytes — can be:
  - Attached to an email (no file storage needed)
  - Returned directly as an HTTP response for download
"""

import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


def generate_invoice_pdf(order):
    """
    Generates a PDF invoice for the given Order instance.

    Args:
        order: Order model instance with related
               order.items (OrderItem queryset) and order.user

    Returns:
        bytes — the PDF file content
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#000000'),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
    )

    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#000000'),
        spaceBefore=12,
        spaceAfter=6,
    )

    right_align_style = ParagraphStyle(
        'RightAlign',
        parent=styles['Normal'],
        alignment=TA_RIGHT,
    )

    elements = []

    # Header -> Company name + Invoice label
    header_table = Table(
        [[
            Paragraph("<b>e-Bazaar</b>", title_style),
            Paragraph("<b>INVOICE</b>", ParagraphStyle(
                'InvoiceLabel', parent=styles['Heading1'],
                fontSize=24, alignment=TA_RIGHT,
                textColor=colors.HexColor('#000000'),
            )),
        ]],
        colWidths=[None, None],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)

    elements.append(Paragraph(
        "Premium Products for Everyday Life", subtitle_style
    ))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#e0e0e0')))
    elements.append(Spacer(1, 12))

    # Order Meta - Invoice #, Date, Status
    invoice_number = f"INV-{order.id:06d}"
    order_date = order.created_at.strftime("%d %B %Y")

    meta_table = Table(
        [
            ["Invoice Number:", invoice_number, "Order Status:", order.status.replace("_", " ").title()],
            ["Order Date:", order_date, "Order ID:", f"#{order.id}"],
        ],
        colWidths=[80, 140, 80, 140],
    )
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 16))

    #  Bill TO — Customer + Shipping info
    elements.append(Paragraph("BILL TO", section_header_style))

    user = order.user
    bill_to_lines = [
        order.shipping_name or user.name or user.email,
        user.email,
    ]

    if order.shipping_address:
        bill_to_lines.append(order.shipping_address)

    city_line_parts = []
    if order.shipping_city:
        city_line_parts.append(order.shipping_city)
    if order.shipping_state:
        city_line_parts.append(order.shipping_state)
    if order.shipping_pincode:
        city_line_parts.append(f"- {order.shipping_pincode}")

    if city_line_parts:
        bill_to_lines.append(" ".join(city_line_parts))

    if order.shipping_phone:
        bill_to_lines.append(f"Phone: {order.shipping_phone}")

    for line in bill_to_lines:
        elements.append(Paragraph(line, styles['Normal']))
        
    elements.append(Spacer(1, 16))

    # ITEMS TABLE
    elements.append(Paragraph("ORDER ITEMS", section_header_style))

    table_data = [
        ["#", "Item", "Price", "Qty", "Total"]
    ]

    items = order.items.select_related('product').all()

    for idx, item in enumerate(items, start=1):
        item_total = item.price * item.quantity
        table_data.append([
            str(idx),
            Paragraph(item.product.title, styles['Normal']),
            f"Rs. {item.price:,.2f}",
            str(item.quantity),
            f"Rs. {item_total:,.2f}",
        ])

    items_table = Table(
        table_data,
        colWidths=[20, 230, 80, 40, 80],
    )
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#000000')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),

        # Body
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f8f8')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 16))

    # TOTALS — Subtotal, Delivery, Tax, Grand Total
    totals_data = [
        ["Subtotal:", f"Rs. {order.total:,.2f}"],
    ]

    if order.delivery_charges > 0:
        totals_data.append(["Delivery:", f"Rs. {order.delivery_charges:,.2f}"])
    else:
        totals_data.append(["Delivery:", "FREE"])

    totals_data.append(["Tax (5%):", f"Rs. {order.tax:,.2f}"])
    totals_data.append(["", ""])  # spacer row
    totals_data.append(["Grand Total:", f"Rs. {order.grand_total:,.2f}"])

    totals_table = Table(
        totals_data,
        colWidths=[370, 80],
    )
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 13),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#000000')),
        ('TEXTCOLOR', (0, 0), (-1, -2), colors.HexColor('#555555')),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 30))

    # Footer
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#e0e0e0')))
    elements.append(Spacer(1, 8))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER,
    )

    elements.append(Paragraph(
        "Thank you for shopping with e-Bazaar!", footer_style
    ))
    elements.append(Paragraph(
        f"This is a computer-generated invoice. "
        f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')}",
        footer_style
    ))

    # ── Build PDF ─────
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
