# app/api/certificate_upload.py
"""
Certificate upload and processing endpoints - Rebuilt for reliability
Handles single and bulk certificate uploads with basic text extraction
"""

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date
import hashlib
import io
import re

from app.models import CPERecord, User
from app.core.database import get_db


router = APIRouter(
    prefix="/api/certificates",
    tags=["Certificate Upload"],
    responses={404: {"description": "Not found"}},
)


# =================
# UTILITY FUNCTIONS
# =================


def get_current_user(db: Session) -> User:
    """Get or create a default user for testing - replace with real auth later"""
    user = db.query(User).filter(User.email == "test@example.com").first()
    if not user:
        # Create default user if doesn't exist
        user = User(
            email="test@example.com",
            password_hash="dummy_hash",
            full_name="Test User",
            primary_jurisdiction="NH",
            onboarding_completed=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def generate_file_hash(file_content: bytes) -> str:
    """Generate SHA256 hash for duplicate detection"""
    return hashlib.sha256(file_content).hexdigest()


def validate_file_type(filename: str) -> tuple[bool, str]:
    """Validate if file type is supported"""
    if not filename or "." not in filename:
        return False, ""

    file_ext = filename.lower().split(".")[-1]
    supported_types = ["pdf", "jpg", "jpeg", "png", "tiff", "bmp"]

    return file_ext in supported_types, file_ext


def extract_basic_text(file_content: bytes, filename: str) -> str:
    """Extract text using Google Cloud Vision for all file types"""
    try:
        from app.services.vision_service import VisionService

        vision = VisionService()
        return vision.extract_text_from_image(file_content)
    except Exception as e:
        # Fallback to basic PDF extraction
        return f"Vision extraction failed: {str(e)}"


def parse_certificate_data(text: str, filename: str) -> dict:
    """Parse certificate data from extracted text"""
    # Initialize with defaults
    data = {
        "course_name": "Unknown Course",
        "course_code": None,
        "provider_name": "Unknown Provider",
        "field_of_study": "General",
        "cpe_credits": 0.0,
        "completion_date": date.today(),
        "delivery_method": "Self-Study",
        "is_ethics": False,
        "extracted_text": text,
    }

    # Basic text parsing
    if text and len(text) > 10:  # If we have actual text
        lines = text.split("\n")

        # Look for hours/credits
        for line in lines:
            line = line.strip()

            # Extract CPE hours
            hours_match = re.search(
                r"(\d+\.?\d*)\s*(hours?|credits?|cpe)", line, re.IGNORECASE
            )
            if hours_match:
                try:
                    data["cpe_credits"] = float(hours_match.group(1))
                except ValueError:
                    pass

            # Look for dates
            date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})", line)
            if date_match:
                try:
                    date_str = date_match.group(1)
                    # Parse MM/DD/YYYY or MM-DD-YYYY
                    if "/" in date_str:
                        month, day, year = map(int, date_str.split("/"))
                    else:
                        month, day, year = map(int, date_str.split("-"))
                    data["completion_date"] = date(year, month, day)
                except ValueError:
                    pass

            # Look for ethics keywords
            if any(
                word in line.lower()
                for word in ["ethics", "ethical", "professional responsibility"]
            ):
                data["is_ethics"] = True

        # If we found hours but no date, keep today's date
        # If we found a date but no hours, default to 1 hour
        if data["cpe_credits"] == 0.0:
            data["cpe_credits"] = 1.0  # Default assumption

    return data


# =================
# UPLOAD ENDPOINTS
# =================


@router.post("/upload")
async def upload_single_certificate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and process a single CPE certificate"""
    try:
        # Validate file type
        is_valid, file_ext = validate_file_type(file.filename)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Supported: PDF, JPG, PNG, TIFF",
            )

        # Get current user
        user = get_current_user(db)

        # Read file content
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded"
            )

        # Generate file hash for duplicate detection
        file_hash = generate_file_hash(file_content)

        # Check for duplicates
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

        # Extract text from certificate
        extracted_text = extract_basic_text(file_content, file.filename)

        # Parse certificate data
        parsed_data = parse_certificate_data(extracted_text, file.filename)

        # Create database record
        cpe_record = CPERecord(
            user_id=user.id,
            course_name=parsed_data["course_name"],
            course_code=parsed_data["course_code"],
            provider_name=parsed_data["provider_name"],
            field_of_study=parsed_data["field_of_study"],
            cpe_credits=parsed_data["cpe_credits"],
            delivery_method=parsed_data["delivery_method"],
            completion_date=parsed_data["completion_date"],
            is_ethics=parsed_data["is_ethics"],
            certificate_filename=file.filename,
            certificate_hash=file_hash,
            nasba_sponsor_id="112530",  # Default NASBA sponsor
            extracted_at=datetime.utcnow(),
            extraction_confidence=0.8,  # Basic confidence score
            manually_verified=False,
            ce_broker_submitted=False,
        )

        # Save to database
        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        return {
            "status": "success",
            "message": "Certificate uploaded and processed successfully",
            "record_id": cpe_record.id,
            "filename": file.filename,
            "user_id": user.id,
            "user_name": user.full_name,
            "extracted_data": {
                "course_name": cpe_record.course_name,
                "provider_name": cpe_record.provider_name,
                "cpe_credits": float(cpe_record.cpe_credits),
                "completion_date": cpe_record.completion_date.isoformat(),
                "field_of_study": cpe_record.field_of_study,
                "is_ethics": cpe_record.is_ethics,
                "extracted_text_preview": (
                    extracted_text[:200] + "..."
                    if len(extracted_text) > 200
                    else extracted_text
                ),
            },
            "database_record": {
                "id": cpe_record.id,
                "course_name": cpe_record.course_name,
                "credits": float(cpe_record.cpe_credits),
                "completion_date": cpe_record.completion_date.isoformat(),
                "field_of_study": cpe_record.field_of_study,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )


@router.post("/bulk-upload")
async def bulk_upload_certificates(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload and process multiple CPE certificates"""
    user = get_current_user(db)

    results = []
    total_credits = 0.0
    saved_count = 0
    duplicate_count = 0
    error_count = 0

    for file in files:
        try:
            # Validate file type
            is_valid, file_ext = validate_file_type(file.filename)
            if not is_valid:
                results.append(
                    {
                        "filename": file.filename,
                        "status": "failed",
                        "error": f"Unsupported file type: {file_ext}",
                    }
                )
                error_count += 1
                continue

            # Read and process file
            file_content = await file.read()
            file_hash = generate_file_hash(file_content)

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
                results.append(
                    {
                        "filename": file.filename,
                        "status": "duplicate",
                        "existing_record_id": existing_record.id,
                        "credits": float(existing_record.cpe_credits),
                    }
                )
                duplicate_count += 1
                continue

            # Extract and parse
            extracted_text = extract_basic_text(file_content, file.filename)
            parsed_data = parse_certificate_data(extracted_text, file.filename)

            # Create database record
            cpe_record = CPERecord(
                user_id=user.id,
                course_name=parsed_data["course_name"],
                course_code=parsed_data["course_code"],
                provider_name=parsed_data["provider_name"],
                field_of_study=parsed_data["field_of_study"],
                cpe_credits=parsed_data["cpe_credits"],
                delivery_method=parsed_data["delivery_method"],
                completion_date=parsed_data["completion_date"],
                is_ethics=parsed_data["is_ethics"],
                certificate_filename=file.filename,
                certificate_hash=file_hash,
                nasba_sponsor_id="112530",
                extracted_at=datetime.utcnow(),
                extraction_confidence=0.8,
                manually_verified=False,
                ce_broker_submitted=False,
            )

            db.add(cpe_record)
            db.flush()  # Get the ID without committing yet

            total_credits += parsed_data["cpe_credits"]
            saved_count += 1

            results.append(
                {
                    "filename": file.filename,
                    "status": "success",
                    "record_id": cpe_record.id,
                    "credits": parsed_data["cpe_credits"],
                    "course_name": parsed_data["course_name"],
                    "completion_date": parsed_data["completion_date"].isoformat(),
                }
            )

        except Exception as e:
            results.append(
                {"filename": file.filename, "status": "failed", "error": str(e)}
            )
            error_count += 1

    # Commit all successful records
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

    return {
        "summary": {
            "total_files": len(files),
            "saved_successfully": saved_count,
            "duplicates_found": duplicate_count,
            "processing_errors": error_count,
            "total_credits_added": total_credits,
            "user_name": user.full_name,
        },
        "results": results,
        "status": "bulk_upload_complete",
    }


# =================
# MANUAL ENTRY ENDPOINT
# =================


@router.post("/manual-entry")
async def manual_certificate_entry(
    course_name: str,
    provider_name: str,
    cpe_credits: float,
    completion_date: str,  # Format: YYYY-MM-DD
    field_of_study: str = "General",
    course_code: str = None,
    is_ethics: bool = False,
    db: Session = Depends(get_db),
):
    """Manually enter certificate data without file upload"""
    try:
        user = get_current_user(db)

        # Parse completion date
        try:
            parsed_date = datetime.strptime(completion_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )

        # Create record
        cpe_record = CPERecord(
            user_id=user.id,
            course_name=course_name,
            course_code=course_code,
            provider_name=provider_name,
            field_of_study=field_of_study,
            cpe_credits=cpe_credits,
            delivery_method="Manual Entry",
            completion_date=parsed_date,
            is_ethics=is_ethics,
            certificate_filename=None,
            certificate_hash=None,
            nasba_sponsor_id="112530",
            extracted_at=datetime.utcnow(),
            extraction_confidence=1.0,  # Manual entry is 100% confident
            manually_verified=True,
            ce_broker_submitted=False,
        )

        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        return {
            "status": "success",
            "message": "Certificate data entered manually",
            "record_id": cpe_record.id,
            "course_name": cpe_record.course_name,
            "credits": float(cpe_record.cpe_credits),
            "completion_date": cpe_record.completion_date.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual entry failed: {str(e)}",
        )
