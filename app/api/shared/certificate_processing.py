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


def parse_certificate_text(text: str) -> dict:
    """Parse certificate text - imported from main logic"""
    from ...main import parse_certificate_text as main_parse

    return main_parse(text)


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
    """Extract text from various file types using VisionService"""
    try:
        from ...services.vision_service import VisionService

        vision = VisionService()
        return vision.extract_text(file_content, filename)
    except Exception as e:
        print(f"Text extraction failed: {e}")
        return f"Text extraction failed for {filename}"


def parse_certificate_text(text: str) -> dict:
    """Parse certificate text for relevant data"""
    import re
    from datetime import date, datetime

    # Basic parsing logic
    parsed_data = {
        "raw_text": text,
        "course_title": "Unknown Course",
        "completion_date": date.today(),  # Default to today if not found
        "hours": 0.0,
        "provider": "Unknown Provider",
        "subject": "General",
    }

    # Simple text parsing
    lines = text.split("\n")
    for line in lines:
        line = line.strip()

        # Extract hours/credits
        if "hours" in line.lower() or "credit" in line.lower():
            hours_match = re.search(r"(\d+\.?\d*)\s*hours?", line, re.IGNORECASE)
            if hours_match:
                try:
                    parsed_data["hours"] = float(hours_match.group(1))
                except ValueError:
                    pass

        # Extract dates - try multiple patterns
        date_patterns = [
            r"(\d{1,2}\/\d{1,2}\/\d{4})",  # MM/DD/YYYY
            r"(\d{4}-\d{1,2}-\d{1,2})",  # YYYY-MM-DD
            r"(\w+ \d{1,2}, \d{4})",  # Month DD, YYYY
            r"(\d{1,2}-\d{1,2}-\d{4})",  # MM-DD-YYYY
        ]

        for pattern in date_patterns:
            date_match = re.search(pattern, line)
            if date_match:
                date_str = date_match.group(1)
                try:
                    parsed_date = parse_date(date_str)
                    if parsed_date and isinstance(parsed_date, date):
                        parsed_data["completion_date"] = parsed_date
                        break
                except Exception as e:
                    print(f"Date parsing error: {e}")
                    continue

    return parsed_data
