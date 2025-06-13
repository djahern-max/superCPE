# app/api/certificate_upload.py

"""
Certificate upload and processing endpoints.
Handles single and bulk certificate uploads with text extraction and parsing.
"""

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..models import CPERecord, User, CPAJurisdiction

import re
from datetime import date
from typing import Optional, Dict

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


def safe_parse_date(date_input):
    """Safely parse date input - handles both date objects and strings"""
    if isinstance(date_input, date):
        return date_input
    elif isinstance(date_input, str):
        return parse_date(date_input)
    else:
        return date.today()


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


def extract_credits_from_filename(filename: str) -> Optional[float]:
    """Extract CPE credits from structured filenames like '10.00CPE_Code_M252...'"""

    # Pattern for your certificates: "10.00CPE_Code_M252-2025-01-SSDL_Daniel_Ahern_fo.pdf"
    pattern = r"^(\d+\.?\d*)CPE_"
    match = re.match(pattern, filename)
    if match:
        return float(match.group(1))

    return None


def extract_course_info_from_filename(filename: str) -> Dict[str, any]:
    """Extract detailed course information from your structured filenames"""

    info = {
        "course_code": None,
        "completion_date": None,
        "provider_name": None,
        "participant_name": None,
        "year": None,
        "month": None,
    }

    # Extract course code: M252, M260, etc.
    code_match = re.search(r"Code_(M\d+)", filename)
    if code_match:
        info["course_code"] = code_match.group(1)

    # Extract date: 2025-01, 2024-01
    date_match = re.search(r"(20\d{2})-(\d{2})", filename)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        info["year"] = year
        info["month"] = month
        # Create completion date (first day of month)
        info["completion_date"] = date(year, month, 1)

    # Extract provider (SSDL in your case)
    provider_match = re.search(r"-(\w+)_[^_]+_[^_]+\.pdf", filename)
    if provider_match:
        info["provider_name"] = provider_match.group(1)

    # Extract participant name
    name_match = re.search(r"SSDL_([^_]+)_([^_]+)_", filename)
    if name_match:
        info["participant_name"] = f"{name_match.group(1)} {name_match.group(2)}"

    return info


@router.post("/bulk-upload-enhanced")
async def bulk_upload_certificates_enhanced(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Enhanced bulk upload that handles your specific filename patterns
    Plus existing random UUID certificate files
    """

    # Get existing user (from your existing function)
    user = get_or_create_default_user(db)

    results = {
        "user_info": {"id": user.id, "name": user.full_name, "email": user.email},
        "processing_summary": {
            "total_files": len(files),
            "filename_parsed": 0,
            "pdf_parsed": 0,
            "manual_review": 0,
            "failed": 0,
            "total_credits": 0.0,
        },
        "certificates": [],
        "errors": [],
    }

    for file in files:
        try:
            # Read file content
            file_content = await file.read()

            # Initialize certificate data
            cert_data = {
                "filename": file.filename,
                "extraction_method": None,
                "cpe_credits": 0.0,
                "course_name": "Unknown Course",
                "course_code": None,
                "provider_name": "Unknown Provider",
                "completion_date": date.today(),
                "field_of_study": "General",
                "participant_name": user.full_name,
            }

            # Method 1: Try filename parsing for structured names
            filename_credits = extract_credits_from_filename(file.filename)
            if filename_credits:
                # Structured filename - extract all info
                cert_data["cpe_credits"] = filename_credits
                cert_data["extraction_method"] = "filename_parsing"

                course_info = extract_course_info_from_filename(file.filename)
                if course_info["course_code"]:
                    cert_data["course_code"] = course_info["course_code"]
                    cert_data["course_name"] = f"Course {course_info['course_code']}"

                if course_info["completion_date"]:
                    cert_data["completion_date"] = safe_parse_date(
                        extracted_data.get("completion_date")
                    )

                if course_info["provider_name"]:
                    cert_data["provider_name"] = course_info["provider_name"]

                if course_info["participant_name"]:
                    cert_data["participant_name"] = course_info["participant_name"]

                # Set field of study based on provider/course pattern
                cert_data["field_of_study"] = (
                    "Accounting & Auditing"  # Default for SSDL courses
                )

                results["processing_summary"]["filename_parsed"] += 1

            # Method 2: PDF parsing for UUID files or to enhance filename data
            elif file.filename.startswith("Certificate_") or not filename_credits:
                try:
                    # Use existing PDF processing
                    processing_result = extract_and_parse_certificate(
                        file_content, file.filename
                    )
                    extracted_data = processing_result["extracted_data"]

                    if extracted_data.get("cpe_credits"):
                        cert_data["cpe_credits"] = float(extracted_data["cpe_credits"])
                        cert_data["course_name"] = extracted_data.get(
                            "course_name", "Unknown Course"
                        )
                        cert_data["provider_name"] = extracted_data.get(
                            "provider_name", "Unknown Provider"
                        )
                        cert_data["field_of_study"] = extracted_data.get(
                            "field_of_study", "General"
                        )

                        if extracted_data.get("completion_date"):
                            cert_data["completion_date"] = parse_date(
                                extracted_data["completion_date"]
                            )

                        cert_data["extraction_method"] = "pdf_parsing"
                        results["processing_summary"]["pdf_parsed"] += 1
                    else:
                        cert_data["extraction_method"] = "manual_review"
                        results["processing_summary"]["manual_review"] += 1

                except Exception as pdf_error:
                    cert_data["extraction_method"] = "failed"
                    results["processing_summary"]["failed"] += 1
                    results["errors"].append(
                        {
                            "filename": file.filename,
                            "error": f"PDF parsing failed: {str(pdf_error)}",
                        }
                    )

            # Calculate file hash for duplicate detection
            processing_result = extract_and_parse_certificate(
                file_content, file.filename
            )
            file_hash = processing_result["file_hash"]

            # Check for duplicates
            existing_record = (
                db.query(CPERecord)
                .filter(
                    CPERecord.certificate_hash == file_hash,
                    CPERecord.user_id == user.id,
                )
                .first()
            )

            if existing_record:
                results["certificates"].append(
                    {
                        "filename": file.filename,
                        "status": "duplicate",
                        "existing_record_id": existing_record.id,
                        "credits": existing_record.cpe_credits,
                    }
                )
                continue

            # Create database record
            cpe_record = CPERecord(
                user_id=user.id,
                course_name=cert_data["course_name"],
                course_code=cert_data["course_code"],
                provider_name=cert_data["provider_name"],
                field_of_study=cert_data["field_of_study"],
                cpe_credits=cert_data["cpe_credits"],
                completion_date=cert_data["completion_date"],
                certificate_filename=file.filename,
                certificate_hash=file_hash,
                delivery_method="Self-Study",  # Default assumption
                nasba_sponsor_id="112530",  # Default
                extracted_at=datetime.utcnow(),
                extraction_confidence=(
                    0.9 if cert_data["extraction_method"] == "filename_parsing" else 0.7
                ),
            )

            db.add(cpe_record)

            # Track results
            results["processing_summary"]["total_credits"] += cert_data["cpe_credits"]
            results["certificates"].append(
                {
                    "filename": file.filename,
                    "status": "success",
                    "record_id": None,  # Will be set after commit
                    "credits": cert_data["cpe_credits"],
                    "extraction_method": cert_data["extraction_method"],
                    "course_name": cert_data["course_name"],
                    "completion_date": (
                        cert_data["completion_date"].isoformat()
                        if cert_data["completion_date"]
                        else None
                    ),
                    "provider": cert_data["provider_name"],
                }
            )

        except Exception as e:
            results["processing_summary"]["failed"] += 1
            results["errors"].append({"filename": file.filename, "error": str(e)})

    # Commit all records
    try:
        db.commit()

        # Update record IDs in results
        user_records = db.query(CPERecord).filter(CPERecord.user_id == user.id).all()
        for cert in results["certificates"]:
            if cert["status"] == "success":
                matching_record = next(
                    (
                        r
                        for r in user_records
                        if r.certificate_filename == cert["filename"]
                    ),
                    None,
                )
                if matching_record:
                    cert["record_id"] = matching_record.id

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Add compliance check
    nh_jurisdiction = (
        db.query(CPAJurisdiction).filter(CPAJurisdiction.code == "NH").first()
    )
    if nh_jurisdiction:
        compliance_info = {
            "nh_requirements": {
                "total_hours_required": nh_jurisdiction.general_hours_required,
                "ethics_hours_required": nh_jurisdiction.ethics_hours_required,
                "reporting_period": nh_jurisdiction.reporting_period_description,
            },
            "your_status": {
                "total_credits_found": results["processing_summary"]["total_credits"],
                "credits_needed": max(
                    0,
                    nh_jurisdiction.general_hours_required
                    - results["processing_summary"]["total_credits"],
                ),
                "compliance_percentage": min(
                    100,
                    (
                        results["processing_summary"]["total_credits"]
                        / nh_jurisdiction.general_hours_required
                    )
                    * 100,
                ),
            },
        }
        results["compliance_check"] = compliance_info

    return results


# Add this to your existing endpoint list
@router.get("/daniel-compliance-check")
async def daniel_compliance_check(db: Session = Depends(get_db)):
    """
    Quick compliance check specifically for Daniel Ahern's certificates
    """

    # Find Daniel's user record
    daniel = db.query(User).filter(User.full_name.ilike("%daniel%ahern%")).first()

    if not daniel:
        return {
            "error": "Daniel Ahern user record not found",
            "suggestion": "Create user account first",
        }

    # Get all his CPE records
    cpe_records = db.query(CPERecord).filter(CPERecord.user_id == daniel.id).all()

    # Get NH requirements
    nh_req = db.query(CPAJurisdiction).filter(CPAJurisdiction.code == "NH").first()

    total_credits = sum(record.cpe_credits for record in cpe_records)

    # Analyze by extraction method
    by_method = {}
    for record in cpe_records:
        method = (
            "filename_parsing" if record.extraction_confidence > 0.85 else "pdf_parsing"
        )
        if method not in by_method:
            by_method[method] = {"count": 0, "credits": 0}
        by_method[method]["count"] += 1
        by_method[method]["credits"] += record.cpe_credits

    return {
        "user": {
            "name": daniel.full_name,
            "license_number": daniel.license_number,
            "email": daniel.email,
        },
        "nh_requirements": {
            "total_hours_required": nh_req.general_hours_required if nh_req else 120,
            "ethics_hours_required": nh_req.ethics_hours_required if nh_req else 4,
            "period": nh_req.reporting_period_description if nh_req else "3-year cycle",
        },
        "current_status": {
            "total_certificates": len(cpe_records),
            "total_credits": total_credits,
            "credits_needed": max(
                0, (nh_req.general_hours_required if nh_req else 120) - total_credits
            ),
            "is_compliant": total_credits
            >= (nh_req.general_hours_required if nh_req else 120),
            "compliance_percentage": min(
                100,
                (total_credits / (nh_req.general_hours_required if nh_req else 120))
                * 100,
            ),
        },
        "extraction_analysis": by_method,
        "certificates": [
            {
                "filename": record.certificate_filename,
                "credits": record.cpe_credits,
                "completion_date": (
                    record.completion_date.isoformat()
                    if record.completion_date
                    else None
                ),
                "course_name": record.course_name,
                "provider": record.provider_name,
                "extraction_confidence": record.extraction_confidence,
            }
            for record in sorted(
                cpe_records, key=lambda x: x.completion_date, reverse=True
            )
        ],
    }


@router.get("/test-filename-parsing")
async def test_filename_parsing():
    """Test endpoint to verify filename parsing works"""

    test_filenames = [
        "10.00CPE_Code_M252-2025-01-SSDL_Daniel_Ahern_fo.pdf",
        "Certificate_13086b3a-25e1-4633-a96f-e9dd152311ee.pdf",
    ]

    results = []

    for filename in test_filenames:
        credits = extract_credits_from_filename(filename)
        course_info = extract_course_info_from_filename(filename)

        results.append(
            {
                "filename": filename,
                "credits_extracted": credits,
                "course_info": course_info,
                "method": "filename_parsing" if credits else "pdf_parsing_needed",
            }
        )

    return {"test_results": results, "status": "filename_parsing_test_complete"}
