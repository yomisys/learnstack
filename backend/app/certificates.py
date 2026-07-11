"""PDF certificate generation.

Certificates are generated on demand from data already in the database
(no separate storage step) — this keeps them always correctly branded
even if a tenant updates its colors/logo after a learner already finished
a course, and avoids depending on object storage before that lands.
"""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def _wrap_hex(color: str, fallback: str) -> HexColor:
    try:
        return HexColor(color)
    except Exception:
        return HexColor(fallback)


def generate_certificate_pdf(
    *,
    learner_name: str,
    curriculum_title: str,
    tenant_name: str,
    branding: dict,
    code: str,
    issued_at: datetime,
    frontend_url: str,
) -> bytes:
    """Render a landscape A4 certificate PDF and return its bytes."""
    primary = _wrap_hex(branding.get("primary_color", ""), "#1a7f5a")
    secondary = _wrap_hex(branding.get("secondary_color", ""), "#12325c")
    text_color = HexColor("#333333")
    product_name = branding.get("product_name") or "LearnStack"

    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # Border
    c.setStrokeColor(primary)
    c.setLineWidth(8)
    c.rect(0.3 * inch, 0.3 * inch, width - 0.6 * inch, height - 0.6 * inch)
    c.setStrokeColor(secondary)
    c.setLineWidth(2)
    c.rect(0.5 * inch, 0.5 * inch, width - 1.0 * inch, height - 1.0 * inch)

    # Title
    c.setFillColor(secondary)
    c.setFont("Helvetica-Bold", 36)
    title_y = height - 1.5 * inch
    c.drawCentredString(width / 2, title_y, "CERTIFICATE OF COMPLETION")

    c.setFont("Helvetica", 16)
    c.setFillColor(text_color)
    c.drawCentredString(width / 2, title_y - 0.5 * inch, tenant_name)

    c.setStrokeColor(primary)
    c.setLineWidth(2)
    line_y = title_y - 0.8 * inch
    c.line(2 * inch, line_y, width - 2 * inch, line_y)

    c.setFont("Helvetica", 14)
    c.setFillColor(text_color)
    body_y = line_y - 0.6 * inch
    c.drawCentredString(width / 2, body_y, "This is to certify that")

    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(secondary)
    name_y = body_y - 0.6 * inch
    c.drawCentredString(width / 2, name_y, learner_name)

    c.setStrokeColor(primary)
    c.setLineWidth(1)
    name_width = c.stringWidth(learner_name, "Helvetica-Bold", 28)
    c.line(width / 2 - name_width / 2, name_y - 0.1 * inch,
           width / 2 + name_width / 2, name_y - 0.1 * inch)

    c.setFont("Helvetica", 14)
    c.setFillColor(text_color)
    achievement_y = name_y - 0.7 * inch
    c.drawCentredString(width / 2, achievement_y, "has successfully completed")
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, achievement_y - 0.35 * inch, curriculum_title)

    c.setFont("Helvetica-Oblique", 12)
    c.setFillColor(text_color)
    date_y = achievement_y - 0.95 * inch
    c.drawCentredString(width / 2, date_y, f"Completed on {issued_at.strftime('%B %d, %Y')}")

    # Verification footer
    c.setFont("Helvetica", 10)
    verify_y = 1.2 * inch
    verify_host = frontend_url.replace("https://", "").replace("http://", "").rstrip("/")
    c.drawCentredString(width / 2, verify_y, f"Verify this certificate at: {verify_host}/verify")
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(secondary)
    c.drawCentredString(width / 2, verify_y - 0.25 * inch, f"Verification Code: {code}")

    c.drawCentredString(width / 2, 0.55 * inch, product_name)

    c.save()
    return buffer.getvalue()
