# app/api/shared/certificate_processing.py

"""
Shared utilities for certificate text extraction and parsing.
"""

import hashlib
from datetime import datetime, date
from typing import Dict, Optional


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """Extract text from various file types - imported from main logic"""
    from ...main import extract_text_from_file as main_extract

    return main_extract(file_content, filename)


def parse_date(date_str: str) -> Optional[date]:
    """Parse various date formats from certificates"""
    if not date_str:
        return None

    try:
        # Handle ISO format first
        if "-" in date_str and len(date_str.split("-")) == 3:
            return datetime.fromisoformat(date_str).date()

        # Handle "Friday, June 6, 2025" format
        if "," in date_str and len(date_str.split()) >= 3:
            parts = date_str.replace(",", "").split()
            month_name = parts[-3]
            day = int(parts[-2])
            year = int(parts[-1])

            month_map = {
                "January": 1,
                "February": 2,
                "March": 3,
                "April": 4,
                "May": 5,
                "June": 6,
                "July": 7,
                "August": 8,
                "September": 9,
                "October": 10,
                "November": 11,
                "December": 12,
            }

            month = month_map.get(month_name)
            if month:
                return date(year, month, day)

        # Try other common formats
        for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

    except (ValueError, KeyError, IndexError):
        pass

    return date.today()  # Default to today if parsing fails


def generate_file_hash(file_content: bytes) -> str:
    """Generate SHA256 hash for file content"""
    return hashlib.sha256(file_content).hexdigest()


def validate_file_type(filename: str) -> tuple[bool, str]:
    """
    Validate if file type is supported
    Returns: (is_valid, file_extension)
    """
    supported_types = ["pdf", "jpg", "jpeg", "png", "tiff", "bmp"]
    file_ext = filename.lower().split(".")[-1] if "." in filename else ""

    is_valid = file_ext in supported_types
    return is_valid, file_ext


def extract_and_parse_certificate(file_content: bytes, filename: str) -> Dict:
    """
    Complete certificate processing pipeline
    Returns extracted and parsed data
    """
    # Validate file type
    is_valid, file_ext = validate_file_type(filename)
    if not is_valid:
        raise ValueError(f"Unsupported file type: {file_ext}")

    # Generate hash
    file_hash = generate_file_hash(file_content)

    # Extract text and parse data
    extracted_text = extract_text_from_file(file_content, filename)
    extracted_data = parse_certificate_text(extracted_text)

    return {
        "file_hash": file_hash,
        "file_ext": file_ext,
        "extracted_text": extracted_text,
        "extracted_data": extracted_data,
    }


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """Extract text from various file types - with fallback for missing Google Vision"""
    try:
        from ...services.vision_service import VisionService

        vision = VisionService()
        return vision.extract_text(file_content, filename)
    except ImportError as e:
        print(f"Google Vision not available: {e}")
        # Fallback: return placeholder text for testing
        return f"Text extraction not available for {filename} - Google Vision SDK not installed. This is placeholder text for testing."
    except Exception as e:
        print(f"Text extraction failed: {e}")
        return f"Text extraction failed for {filename}: {str(e)}"


def parse_certificate_text(text: str) -> dict:
    """
    Enhanced certificate text parsing with proper date extraction
    """
    import re
    from datetime import date, datetime

    # Initialize defaults
    result = {
        "raw_text": text,
        "course_title": "Unknown Course",
        "completion_date": date.today(),  # Fallback to today if no date found
        "hours": 0.0,
        "provider": "Unknown Provider",
        "subject": "General",
        "course_code": None,
        "field_of_study": "Accounting",
        "delivery_method": "Self-Study",
        "is_ethics": False,
    }

    if not text:
        return result

    # Extract course title
    course_patterns = [
        r"for successfully completing\s+([^\n]+)",
        r"Course[:\s]*([^\n]+)",
        r"Subject[:\s]*([^\n]+)",
    ]

    for pattern in course_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["course_title"] = match.group(1).strip()
            break

    # Extract course code
    code_patterns = [r"Course Code[:\s]*([A-Z0-9\-]+)", r"Code[:\s]*([A-Z0-9\-]+)"]

    for pattern in code_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["course_code"] = match.group(1).strip()
            break

    # Extract CPE credits/hours
    hours_patterns = [
        r"CPE\s*Credits?[:\s]*(\d+\.?\d*)",
        r"(\d+\.?\d*)\s*CPE",
        r"(\d+\.?\d*)\s*hours?",
        r"Credits?[:\s]*(\d+\.?\d*)",
    ]

    for pattern in hours_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                result["hours"] = float(match.group(1))
                break
            except ValueError:
                continue

    # Extract provider/sponsor
    provider_patterns = [
        r"(MasterCPE|NASBA|AICPA|[A-Z][a-z]+\s+[A-Z][a-z]+)\s*\n.*Education",
        r"Sponsor[:\s]*([^\n]+)",
        r"Provider[:\s]*([^\n]+)",
    ]

    for pattern in provider_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["provider"] = match.group(1).strip()
            break

    # Extract field of study
    field_patterns = [
        r"Field of Study[:\s]*([^\n]+)",
        r"Subject[:\s]*([^\n]+)",
        r"Category[:\s]*([^\n]+)",
    ]

    for pattern in field_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            field = match.group(1).strip()
            result["field_of_study"] = field
            result["subject"] = field
            break

    # Check if it's ethics
    ethics_keywords = [
        "ethics",
        "professional responsibility",
        "professional conduct",
        "conduct",
    ]
    text_lower = text.lower()
    result["is_ethics"] = any(keyword in text_lower for keyword in ethics_keywords)

    # Extract completion date - CRITICAL FIX
    date_patterns = [
        r"Date[:\s]*([A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4})",  # "Monday, June 2, 2025"
        r"Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})",  # "6/2/2025"
        r"Date[:\s]*(\d{4}-\d{1,2}-\d{1,2})",  # "2025-06-02"
        r"Date[:\s]*([A-Za-z]+\s+\d{1,2},?\s+\d{4})",  # "June 2, 2025"
        r"(\d{1,2}/\d{1,2}/\d{4})",  # Any MM/DD/YYYY in text
        r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",  # Any "Month Day, Year" in text
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            parsed_date = parse_date_string(match)
            if parsed_date:
                result["completion_date"] = parsed_date
                break
        if result["completion_date"] != date.today():
            break

    # Extract delivery method
    if "self-study" in text.lower() or "self study" in text.lower():
        result["delivery_method"] = "Self-Study"
    elif "live" in text.lower() or "webinar" in text.lower():
        result["delivery_method"] = "Live"
    elif "online" in text.lower():
        result["delivery_method"] = "Online"

    return result


def parse_date_string(date_str: str) -> Optional[date]:
    """
    Parse various date formats with better error handling
    """
    if not date_str:
        return None

    # Clean up the date string
    date_str = date_str.strip().replace(",", "")

    # List of date formats to try
    date_formats = [
        "%B %d %Y",  # "June 2 2025"
        "%b %d %Y",  # "Jun 2 2025"
        "%m/%d/%Y",  # "6/2/2025"
        "%m-%d-%Y",  # "6-2-2025"
        "%Y-%m-%d",  # "2025-06-02"
        "%d/%m/%Y",  # "2/6/2025"
        "%A %B %d %Y",  # "Monday June 2 2025"
        "%A, %B %d, %Y",  # "Monday, June 2, 2025"
    ]

    # Try each format
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    # Try parsing with dateutil if available
    try:
        from dateutil.parser import parse as dateutil_parse

        parsed = dateutil_parse(date_str)
        return parsed.date()
    except (ImportError, ValueError):
        pass

    # If all else fails, return None (will default to today in calling function)
    return None
