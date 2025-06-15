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
from app.api.auth import get_current_user

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
        return vision.extract_text(file_content, filename)  # Use the new method
    except Exception as e:
        return f"Vision extraction failed: {str(e)}"


def parse_certificate_data(text: str, filename: str) -> dict:
    """Enhanced certificate data parser with better pattern recognition"""
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

    if not text or len(text) < 10:
        return data

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text_lower = text.lower()

    # =================
    # PROVIDER EXTRACTION
    # =================
    provider_patterns = [
        r"^([A-Za-z\s&.,-]+)(?:\n|$)",  # First line often contains provider
        r"(MasterCPE|NASBA|CPE\s*Central|Becker|Wiley|Thomson Reuters|CCH)",
        r"([A-Za-z\s&.,-]+)\s*(?:Professional|Education|Training|Institute|Academy)",
    ]

    for pattern in provider_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and len(match.group(1).strip()) > 3:
            # Clean up common OCR artifacts
            provider = re.sub(r"[^\w\s&.,-]", "", match.group(1).strip())
            if provider and provider.lower() not in [
                "certificate",
                "completion",
                "awarded",
            ]:
                data["provider_name"] = provider
                break

    # =================
    # COURSE NAME EXTRACTION
    # =================
    course_name_patterns = [
        # Pattern 1: "for successfully completing [COURSE NAME]"
        r"for\s+successfully\s+completing\s*[\n\r]*\s*([^\n\r]+)",
        # Pattern 2: "completion of [COURSE NAME]"
        r"completion\s+of\s*[\n\r]*\s*([^\n\r]+)",
        # Pattern 3: After "subject:" or "course:"
        r"(?:subject|course|title)\s*:?\s*[\n\r]*\s*([^\n\r]+)",
        # Pattern 4: Line after "certificate of completion"
        r"certificate\s+of\s+completion\s*[\n\r]+(?:[^\n\r]*[\n\r]+)*?\s*([^\n\r]+)",
        # Pattern 5: Between common certificate phrases
        r"(?:awarded\s+to\s+[^\n\r]+\s*[\n\r]+\s*(?:for\s+)?(?:successfully\s+)?(?:completing\s+)?)\s*([^\n\r]+)",
    ]

    for pattern in course_name_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            course_name = match.group(1).strip()
            # Clean the course name
            course_name = re.sub(
                r"^\W+|\W+$", "", course_name
            )  # Remove leading/trailing non-word chars
            course_name = re.sub(r"\s+", " ", course_name)  # Normalize whitespace

            # Filter out common false positives
            if (
                len(course_name) > 5
                and course_name.lower()
                not in [
                    "certificate",
                    "completion",
                    "awarded",
                    "daniel ahern",
                    "elizabeth kolar",
                ]
                and not re.match(r"^[A-Z]\d+", course_name)
            ):  # Skip course codes
                data["course_name"] = course_name
                break

    # =================
    # COURSE CODE EXTRACTION
    # =================
    course_code_patterns = [
        r"course\s+code\s*:?\s*([A-Z]\d+[-\w]*)",
        r"(?:code|id)\s*:?\s*([A-Z]\d+[-\w]*)",
        r"\b([A-Z]\d{2,5}[-\w]*)\b",  # General pattern like M290-20
    ]

    for pattern in course_code_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["course_code"] = match.group(1)
            break

    # =================
    # CPE CREDITS EXTRACTION
    # =================
    credit_patterns = [
        r"(\d+\.?\d*)\s*(?:cpe\s*)?(?:hours?|credits?)",
        r"(?:hours?|credits?)\s*:?\s*(\d+\.?\d*)",
        r"(\d+\.?\d*)\s*continuing\s+professional\s+education",
        r"total\s*:?\s*(\d+\.?\d*)\s*(?:hours?|credits?)",
    ]

    for pattern in credit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                credits = float(match.group(1))
                if 0.5 <= credits <= 40:  # Reasonable range for CPE credits
                    data["cpe_credits"] = credits
                    break
            except ValueError:
                continue

    # =================
    # DATE EXTRACTION
    # =================
    date_patterns = [
        r"(?:completed?|dated?|issued)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(\w+\s+\d{1,2},?\s+\d{4})",  # "January 15, 2024"
        r"(\d{1,2}\s+\w+\s+\d{4})",  # "15 January 2024"
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for date_str in matches:
            try:
                # Try different date formats
                for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
                        # Check if date is reasonable (not in future, not too old)
                        if date(2020, 1, 1) <= parsed_date <= date.today():
                            data["completion_date"] = parsed_date
                            break
                    except ValueError:
                        continue
                if data["completion_date"] != date.today():
                    break
            except:
                continue

    # =================
    # ETHICS DETECTION
    # =================
    ethics_keywords = [
        "ethics",
        "ethical",
        "professional responsibility",
        "professional conduct",
        "integrity",
        "independence",
    ]

    if any(keyword in text_lower for keyword in ethics_keywords):
        data["is_ethics"] = True

    # =================
    # FIELD OF STUDY DETECTION
    # =================
    field_mapping = {
        "accounting": ["accounting", "financial", "gaap", "fasb", "audit"],
        "taxation": ["tax", "taxation", "irs", "revenue", "deduction"],
        "auditing": ["audit", "auditing", "assurance", "review", "compilation"],
        "consulting": ["consulting", "advisory", "business", "management"],
        "ethics": ["ethics", "ethical", "professional responsibility"],
        "regulatory": ["regulation", "compliance", "law", "legal"],
        "technology": ["technology", "software", "digital", "cyber", "it"],
    }

    for field, keywords in field_mapping.items():
        if any(keyword in text_lower for keyword in keywords):
            data["field_of_study"] = field.title()
            break

    # Default to 1.0 credits if none found
    if data["cpe_credits"] == 0.0:
        data["cpe_credits"] = 1.0

    return data


# =================
# UPLOAD ENDPOINTS
# =================


@router.post("/process-document")
async def process_single_certificate(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FREE: Process and extract data from CPE certificate
    PAID: Store certificate securely and enable CE Broker integration
    """
    try:
        # Validate file type
        is_valid, file_ext = validate_file_type(file.filename)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Supported: PDF, JPG, PNG, TIFF",
            )

        user = current_user

        # Read file content
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded"
            )

        # Generate file hash for duplicate detection
        file_hash = generate_file_hash(file_content)

        # Check for duplicates (by hash AND user)
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
                "message": "You've already processed this certificate",
                "existing_record_id": existing_record.id,
                "original_filename": existing_record.original_filename,
                "user_id": user.id,
                "extracted_data": {
                    "course_name": existing_record.course_name,
                    "cpe_credits": float(existing_record.cpe_credits),
                    "completion_date": existing_record.completion_date.isoformat(),
                },
            }

        # Extract text from certificate (FREE feature)
        extracted_text = extract_basic_text(file_content, file.filename)

        # Parse certificate data (FREE feature)
        parsed_data = parse_certificate_data(extracted_text, file.filename)

        # Determine storage tier (business logic)
        storage_tier = "free"  # Default for now
        is_stored = False  # Files not stored in free tier
        certificate_url = None  # No storage URL for free tier

        # TODO: Check if user has paid subscription
        # if user.subscription_plan in ["premium", "enterprise"]:
        #     storage_tier = user.subscription_plan
        #     is_stored = True
        #     # Generate smart filename and upload to Digital Ocean
        #     smart_filename = generate_smart_filename(parsed_data, file_ext)
        #     certificate_url = upload_to_digital_ocean(file_content, smart_filename)

        # Create database record
        cpe_record = CPERecord(
            user_id=user.id,
            # Course data (extracted for free)
            course_name=parsed_data["course_name"],
            course_code=parsed_data["course_code"],
            provider_name=parsed_data["provider_name"],
            field_of_study=parsed_data["field_of_study"],
            cpe_credits=parsed_data["cpe_credits"],
            delivery_method=parsed_data["delivery_method"],
            completion_date=parsed_data["completion_date"],
            is_ethics=parsed_data["is_ethics"],
            # File tracking
            original_filename=file.filename,  # NEW: User's original filename
            certificate_filename=None,  # Smart filename (paid feature)
            certificate_url=certificate_url,  # Storage URL (paid feature)
            certificate_hash=file_hash,
            # Business model
            is_stored=is_stored,  # NEW: Storage status
            storage_tier=storage_tier,  # NEW: User's tier
            # Metadata
            nasba_sponsor_id="112530",
            extracted_at=datetime.utcnow(),
            extraction_confidence=0.8,
            manually_verified=False,
            ce_broker_submitted=False,
        )

        # Save to database
        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        # Response varies by tier
        response = {
            "status": "success",
            "message": "Certificate processed successfully",
            "record_id": cpe_record.id,
            "original_filename": file.filename,  # NEW: Always show original name
            "user_id": user.id,
            "user_name": user.full_name,
            "storage_tier": storage_tier,  # NEW: Show user's tier
            "extracted_data": {
                "course_name": cpe_record.course_name,
                "provider_name": cpe_record.provider_name,
                "cpe_credits": float(cpe_record.cpe_credits),
                "completion_date": cpe_record.completion_date.isoformat(),
                "field_of_study": cpe_record.field_of_study,
                "is_ethics": cpe_record.is_ethics,
                "course_code": cpe_record.course_code,
            },
            "database_record": {
                "id": cpe_record.id,
                "course_name": cpe_record.course_name,
                "credits": float(cpe_record.cpe_credits),
                "completion_date": cpe_record.completion_date.isoformat(),
                "field_of_study": cpe_record.field_of_study,
            },
        }

        # Add premium features info for free users
        if storage_tier == "free":
            response["upgrade_info"] = {
                "premium_features": [
                    "Secure cloud storage of certificates",
                    "Smart filename organization",
                    "Automatic CE Broker reporting",
                    "Advanced compliance tracking",
                    "Export to multiple formats",
                ],
                "message": "Upgrade to Premium to store certificates securely and automate CE Broker reporting!",
            }
        else:
            # For paid users, include storage info
            response["storage_info"] = {
                "stored": is_stored,
                "storage_url": certificate_url,
                "smart_filename": cpe_record.certificate_filename,
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )


@router.post("/bulk-process-documents")
async def bulk_process_certificates(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FREE: Process multiple certificates and extract data
    PAID: Store all certificates securely with smart organization
    """
    user = current_user

    results = []
    total_credits = 0.0
    saved_count = 0
    duplicate_count = 0
    error_count = 0

    # Determine user's tier
    storage_tier = "free"  # Default
    # TODO: Check user subscription
    # storage_tier = user.subscription_plan if hasattr(user, 'subscription_plan') else "free"

    for file in files:
        try:
            # Validate file type
            is_valid, file_ext = validate_file_type(file.filename)
            if not is_valid:
                results.append(
                    {
                        "original_filename": file.filename,
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
                        "original_filename": file.filename,
                        "status": "duplicate",
                        "existing_record_id": existing_record.id,
                        "credits": float(existing_record.cpe_credits),
                        "existing_original_filename": existing_record.original_filename,
                    }
                )
                duplicate_count += 1
                continue

            # Extract and parse
            extracted_text = extract_basic_text(file_content, file.filename)
            parsed_data = parse_certificate_data(extracted_text, file.filename)

            # Handle storage based on tier
            is_stored = storage_tier != "free"
            certificate_url = None
            smart_filename = None

            # TODO: For paid users, upload to Digital Ocean
            # if is_stored:
            #     smart_filename = generate_smart_filename(parsed_data, file_ext)
            #     certificate_url = upload_to_digital_ocean(file_content, smart_filename)

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
                # File tracking
                original_filename=file.filename,
                certificate_filename=smart_filename,
                certificate_url=certificate_url,
                certificate_hash=file_hash,
                # Business model
                is_stored=is_stored,
                storage_tier=storage_tier,
                # Metadata
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

            result = {
                "original_filename": file.filename,
                "status": "success",
                "record_id": cpe_record.id,
                "credits": parsed_data["cpe_credits"],
                "course_name": parsed_data["course_name"],
                "completion_date": parsed_data["completion_date"].isoformat(),
            }

            # Add storage info for paid users
            if is_stored:
                result["storage_info"] = {
                    "smart_filename": smart_filename,
                    "storage_url": certificate_url,
                }

            results.append(result)

        except Exception as e:
            results.append(
                {
                    "original_filename": file.filename,
                    "status": "failed",
                    "error": str(e),
                }
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

    response = {
        "summary": {
            "total_files": len(files),
            "processed_successfully": saved_count,
            "duplicates_found": duplicate_count,
            "processing_errors": error_count,
            "total_credits_processed": total_credits,
            "user_name": user.full_name,
            "storage_tier": storage_tier,
        },
        "results": results,
        "status": "bulk_processing_complete",
    }

    # Add upgrade info for free users
    if storage_tier == "free":
        response["upgrade_info"] = {
            "premium_features": [
                "Secure cloud storage for all certificates",
                "Smart filename organization",
                "Bulk CE Broker reporting",
                "Advanced compliance dashboard",
                "Priority support",
            ],
            "processed_count": saved_count,
            "message": f"Successfully processed {saved_count} certificates! Upgrade to Premium to store them securely and automate reporting.",
        }

    return response
