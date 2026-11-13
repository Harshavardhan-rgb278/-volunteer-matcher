from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#0f172a")
GREEN = colors.HexColor("#059669")
GREY = colors.HexColor("#64748b")


def build_certificate_pdf(certificate):
    """Return PDF bytes for a volunteer certificate signed by the organizer."""
    signup = certificate.signup
    volunteer = signup.volunteer
    drive = signup.drive
    organizer_profile = drive.organizer.profile

    buffer = BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle(f"Volunteer Certificate - {volunteer.get_full_name() or volunteer.username}")

    # Border
    c.setStrokeColor(GREEN)
    c.setLineWidth(6)
    c.rect(25, 25, width - 50, height - 50)
    c.setStrokeColor(NAVY)
    c.setLineWidth(1)
    c.rect(38, 38, width - 76, height - 76)

    cx = width / 2
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx, height - 95, "COMMUNITY IMPACT NETWORK")

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(cx, height - 150, "Certificate of Service")

    c.setFillColor(GREY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(cx, height - 195, "This certifies that")

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(cx, height - 240, volunteer.get_full_name() or volunteer.username)

    c.setFillColor(GREY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(cx, height - 280, "has completed")

    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(cx, height - 315, f"{certificate.total_hours:g} verified volunteer hours")

    c.setFillColor(NAVY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(cx, height - 350, f"for \"{drive.title}\" on {drive.date:%B %d, %Y}")

    # Signature block
    c.setStrokeColor(NAVY)
    c.line(cx - 130, 110, cx + 130, 110)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx, 92, drive.organizer.get_full_name() or drive.organizer.username)
    c.setFont("Helvetica", 11)
    c.setFillColor(GREY)
    c.drawCentredString(cx, 76, f"{organizer_profile.organization_name} - Verified Organizer")

    c.setFont("Helvetica", 9)
    c.drawString(55, 52, f"Issued: {certificate.issued_at:%Y-%m-%d}")
    c.drawRightString(width - 55, 52, f"Verification code: {certificate.code}")

    c.showPage()
    c.save()
    return buffer.getvalue()
