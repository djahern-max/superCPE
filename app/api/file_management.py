# app/api/file_management.py

"""
Physical file management endpoints.
Handles file system operations, renaming, backups, and filename management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os
import shutil
from pathlib import Path

from ..core.database import get_db
from ..models import CPERecord
from .certificate_data import get_or_create_default_user
from .shared.filename_utils import (
    generate_certificate_filename,
    generate_suggested_filename_with_extension,
    get_filename_format_info,
)


router = APIRouter(
    prefix="/api/certificates/files",
    tags=["File Management"],
    responses={404: {"description": "Not found"}},
)

# Default storage path - can be overridden via parameter
CERTIFICATE_STORAGE_PATH = "/Users/ryze.ai/Desktop/PDF_BOT"


@router.get("/certificate-filenames")
async def get_certificate_filenames(db: Session = Depends(get_db)):
    """Get suggested filenames for all certificates"""
    try:
        user = get_or_create_default_user(db)

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            return {"status": "no_data", "message": "No certificates found"}

        filename_mappings = []

        for cert in certificates:
            # Generate new filename
            suggested_filename = generate_suggested_filename_with_extension(cert)

            mapping = {
                "certificate_id": cert.id,
                "original_filename": cert.certificate_filename,
                "suggested_filename": suggested_filename,
                "course_name": cert.course_name,
                "credits": float(cert.cpe_credits),
                "completion_date": (
                    cert.completion_date.strftime("%m/%d/%Y")
                    if cert.completion_date
                    else "N/A"
                ),
                "course_code": cert.course_code,
            }

            filename_mappings.append(mapping)

        return {
            "status": "success",
            "total_certificates": len(certificates),
            "filename_mappings": filename_mappings,
            "format_info": get_filename_format_info(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Filename generation failed: {str(e)}"
        )
