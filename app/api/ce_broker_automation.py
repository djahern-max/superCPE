"""
CE Broker Automation API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import io

from ..core.database import get_db
from ..models import CPERecord
from .certificate_data import get_or_create_default_user
from ..services.ce_broker_service import (
    CEBrokerMappingService, 
    CEBrokerReportGenerator,
    CEBrokerSubmission
)

router = APIRouter(
    prefix="/api/ce-broker",
    tags=["CE Broker Automation"],
    responses={404: {"description": "Not found"}},
)

@router.get("/prepare-submissions")
async def prepare_ce_broker_submissions(
    db: Session = Depends(get_db),
    category_filter: Optional[str] = None,
    include_submitted: bool = False
):
    """Prepare all certificates for CE Broker submission"""
    try:
        user = get_or_create_default_user(db)
        
        # Get certificates
        query = db.query(CPERecord).filter(CPERecord.user_id == user.id)
        
        # Filter out already submitted if requested
        if not include_submitted:
            query = query.filter(CPERecord.ce_broker_submitted == False)
        
        certificates = query.order_by(CPERecord.completion_date.desc()).all()
        
        if not certificates:
            return {
                "status": "no_certificates",
                "message": "No certificates available for CE Broker submission",
                "total_certificates": 0
            }
        
        # Convert to CE Broker submissions
        submissions = []
        for cert in certificates:
            submission = CEBrokerMappingService.map_cpe_record_to_submission(cert)
            submissions.append(submission)
        
        # Generate report
        report_generator = CEBrokerReportGenerator(db)
        report = report_generator.generate_submission_report(submissions)
        
        return {
            "status": "success",
            "user_info": {
                "name": user.full_name,
                "email": user.email,
                "license_number": user.license_number
            },
            "report": report
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to prepare submissions: {str(e)}"
        )

@router.get("/submission-guide")
async def get_submission_guide():
    """Get the complete CE Broker submission guide"""
    generator = CEBrokerReportGenerator(None)
    return generator._get_submission_instructions()

@router.post("/mark-submitted")
async def mark_certificates_submitted(
    certificate_ids: List[int],
    db: Session = Depends(get_db)
):
    """Mark certificates as submitted to CE Broker"""
    try:
        user = get_or_create_default_user(db)
        
        updated_count = 0
        for cert_id in certificate_ids:
            cert = db.query(CPERecord).filter(
                CPERecord.id == cert_id,
                CPERecord.user_id == user.id
            ).first()
            
            if cert:
                cert.ce_broker_submitted = True
                cert.ce_broker_submission_date = datetime.now()
                updated_count += 1
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Marked {updated_count} certificates as submitted",
            "updated_count": updated_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark certificates as submitted: {str(e)}"
        )

@router.get("/export-instructions.pdf")
async def download_submission_instructions(db: Session = Depends(get_db)):
    """Download detailed CE Broker submission instructions as PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        user = get_or_create_default_user(db)
        generator = CEBrokerReportGenerator(db)
        instructions = generator._get_submission_instructions()
        
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "CE Broker Submission Guide - SuperCPE")
        
        # User info
        y = height - 100
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"Generated for: {user.full_name}")
        y -= 20
        p.drawString(50, y, f"Date: {datetime.now().strftime('%m/%d/%Y')}")
        
        # Instructions
        y -= 50
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "11-Step CE Broker Submission Process")
        y -= 30
        
        for step in instructions["steps"]:
            if y < 100:  # New page if needed
                p.showPage()
                y = height - 50
            
            p.setFont("Helvetica-Bold", 11)
            p.drawString(50, y, f"Step {step['step']}: {step['title']}")
            y -= 20
            
            p.setFont("Helvetica", 10)
            # Wrap long descriptions
            description = step["description"]
            if len(description) > 80:
                line1 = description[:80]
                line2 = description[80:]
                p.drawString(70, y, line1)
                y -= 15
                p.drawString(70, y, line2)
            else:
                p.drawString(70, y, description)
            
            y -= 15
            p.drawString(70, y, f"Action: {step['action']}")
            
            if "automation_note" in step:
                y -= 15
                p.setFont("Helvetica-Oblique", 9)
                p.drawString(70, y, f"SuperCPE: {step['automation_note']}")
                p.setFont("Helvetica", 10)
            
            y -= 25
        
        p.save()
        buffer.seek(0)
        
        filename = f"ce_broker_guide_{user.full_name.replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate guide: {str(e)}"
        )
