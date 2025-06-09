# app/api/certificate_upload.py

"""
Certificate upload and processing endpoints.
Handles single and bulk certificate uploads with text extraction and parsing.
"""

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..core.database import get_db
from ..models import CPERecord, User
from .shared.certificate_processing import (
    extract_and_parse_certificate,
    parse_date,
    validate_file_type,
)
from .shared.ce_broker_mapping import (
    map_to_ce_broker_format,
    format_ce_broker_record,
)
from .certificate_data import get_or_create_default_user


router = APIRouter(
    prefix="/api/certificates",
    tags=["Certificate Upload"],
    responses={404: {"description": "Not found"}},
)


@router.post("/upload")
async def upload_single_certificate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and process a single CPE certificate with database save"""
    try:
        # Get existing user
        user = get_or_create_default_user(db)

        # Read and process file
        file_content = await file.read()

        # Extract and parse certificate data
        processing_result = extract_and_parse_certificate(file_content, file.filename)

        file_hash = processing_result["file_hash"]
        extracted_data = processing_result["extracted_data"]

        # Check for duplicates for this user
        existing_record = (
            db.query(CPERecord)
            .filter(
                CPERecord.certificate_hash == file_hash, CPERecord.user_id == user.id
            )
            .first()
        )

        if existing_record:
            return {
                "status": "duplicate",
                "message": "Certificate already exists in database",
                "existing_record_id": existing_record.id,
                "filename": file.filename,
                "user_id": user.id,
            }

        # Create database record
        cpe_record = CPERecord(
            user_id=user.id,
            course_name=extracted_data.get("course_name", "Unknown Course"),
            course_code=extracted_data.get("course_code"),
            provider_name=extracted_data.get("provider_name", "Unknown Provider"),
            field_of_study=extracted_data.get("field_of_study", "General"),
            cpe_credits=float(extracted_data.get("cpe_credits", 0)),
            delivery_method="QAS Self-Study",
            completion_date=parse_date(extracted_data.get("completion_date")),
            certificate_filename=file.filename,
            certificate_hash=file_hash,
            nasba_sponsor_id="112530",
            extracted_at=datetime.utcnow(),
            extraction_confidence=0.9,
        )

        # Save to database
        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        return {
            "status": "success",
            "message": "Certificate processed and saved successfully",
            "record_id": cpe_record.id,
            "filename": file.filename,
            "user_id": user.id,
            "user_name": user.full_name,
            "extracted_data": extracted_data,
            "database_record": {
                "id": cpe_record.id,
                "course_name": cpe_record.course_name,
                "credits": float(cpe_record.cpe_credits),
                "completion_date": (
                    cpe_record.completion_date.isoformat()
                    if cpe_record.completion_date
                    else None
                ),
                "field_of_study": cpe_record.field_of_study,
            },
            "note": f"Using existing default user (ID: {user.id})",
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/bulk-upload")
async def bulk_upload_certificates(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload and process multiple CPE certificates with database save"""
    # Get or create default user
    user = get_or_create_default_user(db)

    results = []
    total_credits = 0.0
    saved_count = 0
    duplicate_count = 0
    error_count = 0

    for file in files:
        try:
            # Read and process file
            file_content = await file.read()

            # Extract and parse certificate data
            processing_result = extract_and_parse_certificate(
                file_content, file.filename
            )

            file_hash = processing_result["file_hash"]
            extracted_data = processing_result["extracted_data"]

            # Check for duplicates
            existing_record = (
                db.query(CPERecord)
                .filter(CPERecord.certificate_hash == file_hash)
                .first()
            )

            if existing_record:
                results.append(
                    {
                        "filename": file.filename,
                        "status": "duplicate",
                        "message": "Certificate already exists",
                        "existing_record_id": existing_record.id,
                    }
                )
                duplicate_count += 1
                continue

            # Map to CE Broker format
            ce_broker_data = map_to_ce_broker_format(extracted_data)

            # Create database record
            cpe_record = CPERecord(
                user_id=user.id,
                course_name=extracted_data.get("course_name", "Unknown Course"),
                course_code=extracted_data.get("course_code"),
                provider_name=extracted_data.get("provider_name", "Unknown Provider"),
                field_of_study=extracted_data.get("field_of_study", "General"),
                cpe_credits=float(extracted_data.get("cpe_credits", 0)),
                delivery_method="QAS Self-Study",
                completion_date=parse_date(extracted_data.get("completion_date")),
                certificate_filename=file.filename,
                certificate_hash=file_hash,
                nasba_sponsor_id="112530",
                extracted_at=datetime.utcnow(),
                extraction_confidence=0.9,
            )

            # Save to database
            db.add(cpe_record)
            db.commit()
            db.refresh(cpe_record)

            credits = float(extracted_data.get("cpe_credits", 0))
            total_credits += credits
            saved_count += 1

            results.append(
                {
                    "filename": file.filename,
                    "status": "success",
                    "record_id": cpe_record.id,
                    "extracted_data": extracted_data,
                    "ce_broker_submission": ce_broker_data,
                    "credits": credits,
                }
            )

        except ValueError as ve:
            results.append(
                {
                    "filename": file.filename,
                    "status": "failed",
                    "error": f"Validation error: {str(ve)}",
                }
            )
            error_count += 1
        except Exception as e:
            db.rollback()
            results.append(
                {"filename": file.filename, "status": "failed", "error": str(e)}
            )
            error_count += 1

    # Calculate summary by field of study
    successful_results = [r for r in results if r["status"] == "success"]
    by_field = {}
    for result in successful_results:
        field = result["extracted_data"].get("field_of_study", "Unknown")
        credits = result["credits"]
        by_field[field] = by_field.get(field, 0) + credits

    return {
        "summary": {
            "total_files": len(files),
            "saved_successfully": saved_count,
            "duplicates_found": duplicate_count,
            "processing_errors": error_count,
            "total_credits_added": total_credits,
            "by_field_of_study": by_field,
            "user_name": user.full_name,
        },
        "results": results,
        "status": "bulk_upload_complete",
        "note": "Authentication will be added later - using default user for now",
    }


@router.post("/process-for-ce-broker/")
async def process_for_ce_broker_legacy(file: UploadFile = File(...)):
    """Legacy endpoint - Process certificate and return CE Broker formatted data"""
    try:
        # Read and process file
        file_content = await file.read()

        # Extract and parse certificate data
        processing_result = extract_and_parse_certificate(file_content, file.filename)

        extracted_data = processing_result["extracted_data"]
        file_ext = processing_result["file_ext"]

        # Map to CE Broker format
        ce_broker_data = map_to_ce_broker_format(extracted_data)

        return {
            "filename": file.filename,
            "file_type": file_ext,
            "extracted_data": extracted_data,
            "ce_broker_submission": ce_broker_data,
            "status": "ready_for_ce_broker",
            "message": f"Certificate processed and mapped for CE Broker submission using {'PDF extraction' if file_ext == 'pdf' else 'OCR'}",
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing certificate: {str(e)}"
        )
