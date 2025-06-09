# app/api/ce_broker_exports.py

"""
CE Broker export and reporting endpoints.
Handles all CE Broker format exports including CSV, PDF, and JSON reports.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
import csv
import io

from ..core.database import get_db
from ..models import CPERecord
from .certificate_data import get_or_create_default_user
from .shared.ce_broker_mapping import (
    format_ce_broker_record,
    get_ce_broker_instructions,
)
from .shared.filename_utils import generate_suggested_filename_with_extension


router = APIRouter(
    prefix="/api/certificates/ce-broker",
    tags=["CE Broker Exports"],
    responses={404: {"description": "Not found"}},
)


@router.get("/report")
async def get_ce_broker_report(
    db: Session = Depends(get_db), format: str = "json"  # json or csv
):
    """Get CE Broker formatted report of all certificates"""
    try:
        # Get existing user
        user = get_or_create_default_user(db)

        # Get all certificates for this user
        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            return {
                "status": "no_data",
                "message": "No certificates found. Upload some certificates first.",
                "user_id": user.id,
            }

        # Format data for CE Broker
        ce_broker_data = []
        total_credits = 0

        for cert in certificates:
            ce_record = format_ce_broker_record(cert)
            ce_broker_data.append(ce_record)
            total_credits += float(cert.cpe_credits)

        # Summary by field of study
        field_summary = {}
        for record in ce_broker_data:
            field = record["field_of_study"]
            if field not in field_summary:
                field_summary[field] = {"count": 0, "credits": 0}
            field_summary[field]["count"] += 1
            field_summary[field]["credits"] += record["credits"]

        report_data = {
            "user_info": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "jurisdiction": user.primary_jurisdiction,
                "license_number": user.license_number,
            },
            "summary": {
                "total_certificates": len(certificates),
                "total_credits": total_credits,
                "by_field_of_study": field_summary,
                "report_generated": datetime.utcnow().isoformat(),
            },
            "certificates": ce_broker_data,
            "ce_broker_instructions": get_ce_broker_instructions(),
        }

        if format.lower() == "csv":
            # Return as CSV download
            return await generate_ce_broker_csv(ce_broker_data, user)
        else:
            # Return as JSON
            return {"status": "success", "report": report_data}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Report generation failed: {str(e)}"
        )


@router.get("/export.csv")
async def download_ce_broker_csv(db: Session = Depends(get_db)):
    """Download CE Broker data as CSV file"""
    try:
        user = get_or_create_default_user(db)

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            raise HTTPException(status_code=404, detail="No certificates found")

        # Format data for CE Broker CSV
        ce_broker_data = []
        for cert in certificates:
            ce_record = format_ce_broker_record(cert)

            # Convert to CSV format with proper headers
            csv_record = {
                "Course Name": ce_record["course_name"],
                "Provider Name": ce_record["provider_name"],
                "Completion Date": ce_record["completion_date"],
                "Credits": ce_record["credits"],
                "Delivery Method": ce_record["delivery_method"],
                "Subject Areas": ce_record["subject_areas"],
                "Course Code": ce_record["course_code"],
                "Field of Study": ce_record["field_of_study"],
                "Certificate File": ce_record["certificate_filename"],
                "NASBA Sponsor": ce_record["nasba_sponsor"],
            }
            ce_broker_data.append(csv_record)

        return await generate_ce_broker_csv(ce_broker_data, user)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")


@router.get("/export-with-filenames.csv")
async def download_ce_broker_csv_with_filenames(db: Session = Depends(get_db)):
    """Download CE Broker CSV with suggested filenames"""
    try:
        user = get_or_create_default_user(db)

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            raise HTTPException(status_code=404, detail="No certificates found")

        # Format data for CE Broker CSV with suggested filenames
        ce_broker_data = []
        for cert in certificates:
            ce_record = format_ce_broker_record(cert)
            suggested_filename = generate_suggested_filename_with_extension(cert)

            csv_record = {
                "Course Name": ce_record["course_name"],
                "Provider Name": ce_record["provider_name"],
                "Completion Date": ce_record["completion_date"],
                "Credits": ce_record["credits"],
                "Delivery Method": ce_record["delivery_method"],
                "Subject Areas": ce_record["subject_areas"],
                "Course Code": ce_record["course_code"],
                "Field of Study": ce_record["field_of_study"],
                "Original Certificate File": ce_record["certificate_filename"],
                "Suggested Filename": suggested_filename,
                "NASBA Sponsor": ce_record["nasba_sponsor"],
            }
            ce_broker_data.append(csv_record)

        return await generate_ce_broker_csv(ce_broker_data, user)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")


@router.get("/export.pdf")
async def download_ce_broker_simple_pdf(db: Session = Depends(get_db)):
    """Download CE Broker data as a simple PDF file"""
    try:
        user = get_or_create_default_user(db)

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            raise HTTPException(status_code=404, detail="No certificates found")

        # Create PDF using simple canvas approach
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "CE Broker Submission Report")

        # User info
        y = height - 100
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Name: {user.full_name or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"Email: {user.email or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"License: {user.license_number or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"Jurisdiction: {user.primary_jurisdiction or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"Report Date: {datetime.now().strftime('%m/%d/%Y')}")

        # Summary
        y -= 40
        total_credits = sum(float(cert.cpe_credits) for cert in certificates)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Summary")
        y -= 25
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Total Certificates: {len(certificates)}")
        y -= 20
        p.drawString(50, y, f"Total Credits: {total_credits:.1f}")

        # Certificate list header
        y -= 40
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Certificates for CE Broker Submission")
        y -= 30

        # Instructions
        p.setFont("Helvetica", 10)
        p.drawString(
            50, y, "Instructions: Copy the information below into CE Broker forms"
        )
        y -= 15
        p.drawString(50, y, "Provider for all courses: Professional Education Services")
        y -= 15
        p.drawString(
            50,
            y,
            "Delivery Method for all: Computer-Based Training (ie: online courses)",
        )
        y -= 30

        # Certificate details
        for i, cert in enumerate(certificates, 1):
            # Check if we need a new page
            if y < 100:
                p.showPage()
                y = height - 50

            ce_record = format_ce_broker_record(cert)

            p.setFont("Helvetica-Bold", 11)
            p.drawString(50, y, f"Certificate #{i}")
            y -= 20

            p.setFont("Helvetica", 10)

            # Course name (might be long, so wrap it)
            course_name = ce_record["course_name"]
            if len(course_name) > 80:
                line1 = course_name[:80]
                line2 = course_name[80:]
                p.drawString(70, y, f"Course: {line1}")
                y -= 15
                p.drawString(70, y, f"        {line2}")
            else:
                p.drawString(70, y, f"Course: {course_name}")

            y -= 15
            p.drawString(70, y, f"Provider: {ce_record['provider_name']}")
            y -= 15
            p.drawString(70, y, f"Date: {ce_record['completion_date']}")
            y -= 15
            p.drawString(70, y, f"Credits: {ce_record['credits']:.1f}")
            y -= 15
            p.drawString(70, y, f"Subject Areas: {ce_record['subject_areas']}")
            y -= 15
            p.drawString(70, y, f"Course Code: {ce_record['course_code'] or 'N/A'}")
            y -= 15
            p.drawString(
                70, y, f"Certificate File: {ce_record['certificate_filename'] or 'N/A'}"
            )
            y -= 25

        # Save PDF
        p.save()
        buffer.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"ce_broker_report_{user.full_name.replace(' ', '_')}_{timestamp}.pdf"
        )

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@router.get("/export-with-filenames.pdf")
async def download_ce_broker_pdf_with_filenames(db: Session = Depends(get_db)):
    """Download CE Broker PDF with suggested filenames"""
    try:
        user = get_or_create_default_user(db)

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            raise HTTPException(status_code=404, detail="No certificates found")

        # Create PDF using simple canvas approach
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(
            50, height - 50, "CE Broker Submission Report with Suggested Filenames"
        )

        # User info section
        y = height - 100
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Name: {user.full_name or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"Email: {user.email or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"License: {user.license_number or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"Jurisdiction: {user.primary_jurisdiction or 'N/A'}")
        y -= 20
        p.drawString(50, y, f"Report Date: {datetime.now().strftime('%m/%d/%Y')}")

        # Summary
        y -= 40
        total_credits = sum(float(cert.cpe_credits) for cert in certificates)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Summary")
        y -= 25
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Total Certificates: {len(certificates)}")
        y -= 20
        p.drawString(50, y, f"Total Credits: {total_credits:.1f}")

        # Filename explanation
        y -= 40
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Suggested Filename Format: YYYYMMDD_XCPe_Course_Name.pdf")
        y -= 20
        p.setFont("Helvetica", 10)
        p.drawString(50, y, "Example: 20250606_15CPE_Defensive_Divorce.pdf")
        y -= 15
        p.drawString(
            50, y, "Benefits: Easy identification, sortable by date, shows credits"
        )

        # Certificate list header
        y -= 40
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Certificates for CE Broker Submission")
        y -= 30

        # Instructions
        p.setFont("Helvetica", 10)
        p.drawString(
            50,
            y,
            "Instructions: Save your certificates with the suggested filenames, then use info below for CE Broker",
        )
        y -= 15
        p.drawString(50, y, "Provider for all courses: Professional Education Services")
        y -= 15
        p.drawString(
            50,
            y,
            "Delivery Method for all: Computer-Based Training (ie: online courses)",
        )
        y -= 30

        # Certificate details
        for i, cert in enumerate(certificates, 1):
            # Check if we need a new page
            if y < 150:
                p.showPage()
                y = height - 50

            ce_record = format_ce_broker_record(cert)
            suggested_filename = generate_suggested_filename_with_extension(cert)

            p.setFont("Helvetica-Bold", 11)
            p.drawString(50, y, f"Certificate #{i}")
            y -= 20

            p.setFont("Helvetica", 10)

            # Course name (might be long, so wrap it)
            course_name = ce_record["course_name"]
            if len(course_name) > 80:
                line1 = course_name[:80]
                line2 = course_name[80:]
                p.drawString(70, y, f"Course: {line1}")
                y -= 15
                p.drawString(70, y, f"        {line2}")
            else:
                p.drawString(70, y, f"Course: {course_name}")

            y -= 15

            # Suggested filename (highlighted)
            p.setFont("Helvetica-Bold", 10)
            p.drawString(70, y, f"Suggested Filename: {suggested_filename}")
            p.setFont("Helvetica", 10)
            y -= 15

            p.drawString(
                70, y, f"Original File: {ce_record['certificate_filename'] or 'N/A'}"
            )
            y -= 15
            p.drawString(70, y, f"Provider: {ce_record['provider_name']}")
            y -= 15
            p.drawString(70, y, f"Date: {ce_record['completion_date']}")
            y -= 15
            p.drawString(70, y, f"Credits: {ce_record['credits']:.1f}")
            y -= 15
            p.drawString(70, y, f"Subject Areas: {ce_record['subject_areas']}")
            y -= 15
            p.drawString(70, y, f"Course Code: {ce_record['course_code'] or 'N/A'}")
            y -= 25

        # Save PDF
        p.save()
        buffer.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ce_broker_report_with_filenames_{user.full_name.replace(' ', '_')}_{timestamp}.pdf"

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


async def generate_ce_broker_csv(data: list, user) -> StreamingResponse:
    """Generate CSV file for CE Broker data"""
    # Create CSV in memory
    output = io.StringIO()

    if not data:
        writer = csv.writer(output)
        writer.writerow(["No certificates found"])
        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=ce_broker_no_data.csv"
            },
        )

    # Get field names from first record
    fieldnames = list(data[0].keys())

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

    output.seek(0)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ce_broker_report_{user.full_name.replace(' ', '_')}_{timestamp}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
