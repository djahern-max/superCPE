from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date
import PyPDF2
import io
import re
from PIL import Image
import os
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute

# Import the existing API router (for auth and other endpoints)
from app.api import api_router

# Import the new modular certificate routers
from app.api import (
    certificate_upload,
    certificate_data,
    ce_broker_exports,
    file_management,
)

# Import our vision service
try:
    from app.services.vision_service import VisionService

    vision_service = VisionService()
    VISION_AVAILABLE = True
except Exception as e:
    print(f"Warning: Google Vision not available: {e}")
    VISION_AVAILABLE = False

app = FastAPI(title="SuperCPE API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the existing API router (auth, etc.)
app.include_router(api_router)

# Include the new modular certificate routers


@app.get("/")
async def root():
    return {"message": "SuperCPE API is running!", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "ocr_available": VISION_AVAILABLE,
        "modular_routers": {
            "certificate_upload": "✅ Active",
            "certificate_data": "✅ Active",
            "ce_broker_exports": "✅ Active",
            "file_management": "✅ Active",
        },
    }


# =================
# LEGACY ENDPOINTS (Keep for backward compatibility)
# =================


def extract_pdf_text(pdf_content: bytes) -> str:
    """Extract text from PDF bytes"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """Extract text from various file types"""
    file_ext = filename.lower().split(".")[-1]

    if file_ext == "pdf":
        return extract_pdf_text(file_content)
    elif file_ext in ["jpg", "jpeg", "png", "tiff", "bmp"]:
        if not VISION_AVAILABLE:
            raise HTTPException(
                status_code=400, detail="OCR not available - missing Google credentials"
            )
        return vision_service.extract_text_from_image(file_content)
    else:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {file_ext}"
        )


def parse_certificate_text(text: str) -> dict:
    """Parse certificate text (works with both PDF and OCR text)"""

    # Extract course name (look for pattern after "completing")
    course_match = re.search(
        r"completing\s+(.+?)(?:\s+Course Code:|$)", text, re.IGNORECASE
    )
    course_name = course_match.group(1).strip() if course_match else "Unknown Course"

    # Extract course code
    code_match = re.search(r"Course Code:\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
    course_code = code_match.group(1) if code_match else "Unknown"

    # Extract field of study
    field_match = re.search(r"Field of Study:\s*([^\n]+)", text, re.IGNORECASE)
    field_of_study = field_match.group(1).strip() if field_match else "General"

    # Extract CPE credits
    credits_match = re.search(r"CPE Credits:\s*(\d+\.?\d*)", text, re.IGNORECASE)
    cpe_credits = float(credits_match.group(1)) if credits_match else 0.0

    # Extract date (look for "Date:" followed by a date)
    date_match = re.search(r"Date:\s*([^\n]+)", text, re.IGNORECASE)
    date_str = date_match.group(1).strip() if date_match else ""

    # Try to parse the date
    completion_date = date.today()  # Default to today
    if date_str:
        try:
            # Try different date formats
            for fmt in ["%A, %B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                try:
                    completion_date = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
        except:
            pass

    # Extract provider (look for common patterns)
    provider = "Professional Education Services"  # Default based on your certificates

    return {
        "course_name": course_name,
        "course_code": course_code,
        "provider_name": provider,
        "field_of_study": field_of_study,
        "cpe_credits": cpe_credits,
        "completion_date": completion_date.isoformat(),
    }


def map_to_ce_broker_format(extracted_data: dict) -> dict:
    """Map extracted CPE data to CE Broker submission format"""

    # Field of Study mapping to CE Broker subject areas
    field_mapping = {
        "Taxes": ["Taxes"],
        "Accounting": ["Public accounting"],
        "Economics": ["Economics"],
        "Personnel / Human Resources": ["Personnel and human resources"],
        "Communications and Marketing": ["Communications", "Marketing"],
        "Auditing": ["Public auditing"],
        "Auditing - Fraud": ["Public auditing", "Administrative practices"],
    }

    # Map field of study to CE Broker subjects
    subject_areas = field_mapping.get(extracted_data["field_of_study"], ["General"])

    # Format date for CE Broker (MM/DD/YYYY)
    completion_date = datetime.fromisoformat(
        extracted_data["completion_date"]
    ).strftime("%m/%d/%Y")

    return {
        "course_name": extracted_data["course_name"],
        "provider_name": extracted_data["provider_name"],
        "completion_date": completion_date,
        "course_type": "Computer-Based Training (ie: online courses)",
        "subject_areas": subject_areas,
        "hours": extracted_data["cpe_credits"],
        "certificate_file": f"{extracted_data['course_code']}.pdf",
    }


@app.get("/test-data")
async def get_test_data():
    """Get sample data for testing"""
    return {
        "sample_certificates": [
            {
                "course_name": "Debt: Selected Debt Related Issues",
                "credits": 2.0,
                "field": "Taxes",
            },
            {
                "course_name": "The New Lease Standard ASU 2016-02",
                "credits": 4.0,
                "field": "Accounting",
            },
        ],
        "total_credits": 6.0,
        "supported_formats": ["PDF", "JPG", "PNG", "TIFF", "BMP"],
        "ocr_available": VISION_AVAILABLE,
        "new_features": {
            "modular_routers": True,
            "enhanced_file_management": True,
            "improved_ce_broker_exports": True,
            "better_error_handling": True,
        },
    }


@app.get("/routes-simple", response_class=PlainTextResponse)
async def get_routes_simple():
    """
    Returns a concise list of all routes with their paths and methods.
    """
    routes = []

    # Add a header
    routes.append("=== SUPERCPE API ROUTES ===")
    routes.append("")

    # Categorize routes
    legacy_routes = []
    new_certificate_routes = []
    auth_routes = []
    utility_routes = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = ", ".join(route.methods)
            route_info = f"{methods}: {route.path}"

            if route.path.startswith("/api/certificates/"):
                new_certificate_routes.append(route_info)
            elif route.path.startswith("/api/auth/"):
                auth_routes.append(route_info)
            elif route.path in ["/", "/health", "/routes-simple", "/test-data"]:
                utility_routes.append(route_info)
            else:
                legacy_routes.append(route_info)

    # Add categorized routes
    routes.append("NEW CERTIFICATE API ENDPOINTS (Modular):")
    for route in sorted(new_certificate_routes):
        routes.append(route)
    routes.append("")

    routes.append("AUTHENTICATION ENDPOINTS:")
    for route in sorted(auth_routes):
        routes.append(route)
    routes.append("")

    routes.append("UTILITY ENDPOINTS:")
    for route in sorted(utility_routes):
        routes.append(route)
    routes.append("")

    if legacy_routes:
        routes.append("LEGACY ENDPOINTS (Backward Compatibility):")
        for route in sorted(legacy_routes):
            routes.append(route)

    # Add endpoint summary
    routes.append("")
    routes.append("=== ENDPOINT SUMMARY ===")
    routes.append(f"Certificate Management: {len(new_certificate_routes)} endpoints")
    routes.append(f"Authentication: {len(auth_routes)} endpoints")
    routes.append(f"Utility: {len(utility_routes)} endpoints")
    routes.append(f"Legacy: {len(legacy_routes)} endpoints")
    routes.append("")
    routes.append("📁 New Modular Structure:")
    routes.append("├── /api/certificates/upload & bulk-upload")
    routes.append("├── /api/certificates/summary & list")
    routes.append("├── /api/certificates/ce-broker/* (exports)")
    routes.append("└── /api/certificates/files/* (file management)")

    return "\n".join(routes)
