# app/api/certificate_upload.py - FIXED VERSION
"""
Certificate upload and processing endpoints - Rebuilt for reliability
Handles single and bulk certificate uploads with basic text extraction
"""

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date
import hashlib
import re

# FIXED: Use relative import to avoid circular dependency
from ..models import CPERecord, User
from ..core.database import get_db

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
        return vision.extract_text(file_content, filename)
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
        r"^([A-Za-z\s&.,-]+)(?:\n|$)",
        r"(MasterCPE|NASBA|CPE\s*Central|Becker|Wiley|Thomson Reuters|CCH)",
        r"([A-Za-z\s&.,-]+)\s*(?:Professional|Education|Training|Institute|Academy)",
    ]

    for pattern in provider_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and len(match.group(1).strip()) > 3:
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
        r"for\s+successfully\s+completing\s*[\n\r]*\s*([^\n\r]+)",
        r"completion\s+of\s*[\n\r]*\s*([^\n\r]+)",
        r"(?:subject|course|title)\s*:?\s*[\n\r]*\s*([^\n\r]+)",
        r"certificate\s+of\s+completion\s*[\n\r]+(?:[^\n\r]*[\n\r]+)*?\s*([^\n\r]+)",
        r"(?:awarded\s+to\s+[^\n\r]+\s*[\n\r]+\s*(?:for\s+)?(?:successfully\s+)?(?:completing\s+)?)\s*([^\n\r]+)",
    ]

    for pattern in course_name_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            course_name = match.group(1).strip()
            course_name = re.sub(r"^\W+|\W+$", "", course_name)
            course_name = re.sub(r"\s+", " ", course_name)

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
            ):
                data["course_name"] = course_name
                break

    # =================
    # COURSE CODE EXTRACTION
    # =================
    course_code_patterns = [
        r"course\s+code\s*:?\s*([A-Z]\d+[-\w]*)",
        r"(?:code|id)\s*:?\s*([A-Z]\d+[-\w]*)",
        r"\b([A-Z]\d{2,5}[-\w]*)\b",
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
                if 0.5 <= credits <= 40:
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
        r"(\w+\s+\d{1,2},?\s+\d{4})",
        r"(\d{1,2}\s+\w+\s+\d{4})",
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for date_str in matches:
            try:
                for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt).date()
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
# AUTH DEPENDENCY - FIXED
# =================


async def get_current_user_for_upload(db: Session = Depends(get_db)):
    """Temporary auth function - will be replaced with proper JWT auth"""
    # For now, get or create a default user
    user = db.query(User).first()
    if not user:
        # Create a default user for testing
        user = User(
            email="default@test.com",
            full_name="Default User",
            password_hash="dummy_hash",
            primary_jurisdiction="NH",
            onboarding_step="complete",
            is_active=True,
            email_reminders=True,
            newsletter_subscription=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# =================
# UPLOAD ENDPOINTS
# =================


@router.post("/upload")
async def upload_single_certificate(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_for_upload),
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

        user = current_user

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
            original_filename=file.filename,  # NEW: Store original filename
            certificate_filename=file.filename,
            certificate_hash=file_hash,
            is_stored=False,  # NEW: Free tier
            storage_tier="free",  # NEW: Business model
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

        return {
            "status": "success",
            "message": "Certificate uploaded and processed successfully",
            "record_id": cpe_record.id,
            "original_filename": file.filename,  # NEW
            "user_id": user.id,
            "user_name": user.full_name,
            "storage_tier": "free",  # NEW
            "extracted_data": {
                "course_name": cpe_record.course_name,
                "provider_name": cpe_record.provider_name,
                "cpe_credits": float(cpe_record.cpe_credits),
                "completion_date": cpe_record.completion_date.isoformat(),
                "field_of_study": cpe_record.field_of_study,
                "is_ethics": cpe_record.is_ethics,
                "course_code": cpe_record.course_code,
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
            "upgrade_info": {  # NEW: Business model
                "premium_features": [
                    "Secure cloud storage of certificates",
                    "Smart filename organization",
                    "Automatic CE Broker reporting",
                    "Advanced compliance tracking",
                ],
                "message": "Upgrade to Premium to store certificates securely!",
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
    current_user: User = Depends(get_current_user_for_upload),
    db: Session = Depends(get_db),
):
    """Upload and process multiple CPE certificates"""
    user = current_user

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
                original_filename=file.filename,  # NEW
                certificate_filename=file.filename,
                certificate_hash=file_hash,
                is_stored=False,  # NEW
                storage_tier="free",  # NEW
                nasba_sponsor_id="112530",
                extracted_at=datetime.utcnow(),
                extraction_confidence=0.8,
                manually_verified=False,
                ce_broker_submitted=False,
            )

            db.add(cpe_record)
            db.flush()

            total_credits += parsed_data["cpe_credits"]
            saved_count += 1

            results.append(
                {
                    "original_filename": file.filename,
                    "status": "success",
                    "record_id": cpe_record.id,
                    "credits": parsed_data["cpe_credits"],
                    "course_name": parsed_data["course_name"],
                    "completion_date": parsed_data["completion_date"].isoformat(),
                }
            )

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

    return {
        "summary": {
            "total_files": len(files),
            "saved_successfully": saved_count,
            "duplicates_found": duplicate_count,
            "processing_errors": error_count,
            "total_credits_added": total_credits,
            "user_name": user.full_name,
            "storage_tier": "free",  # NEW
        },
        "results": results,
        "status": "bulk_upload_complete",
        "upgrade_info": {  # NEW
            "premium_features": [
                "Secure cloud storage for all certificates",
                "Smart filename organization",
                "Bulk CE Broker reporting",
            ],
            "processed_count": saved_count,
            "message": f"Successfully processed {saved_count} certificates! Upgrade to Premium to store them securely.",
        },
    }
