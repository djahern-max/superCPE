# app/api/shared/filename_utils.py

"""
Filename generation and sanitization utilities.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import CPERecord


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system use"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove extra spaces and replace with underscores
    filename = re.sub(r"\s+", "_", filename)
    # Remove any double underscores
    filename = re.sub(r"_+", "_", filename)
    # Limit length to 200 characters (leaving room for extension)
    if len(filename) > 200:
        filename = filename[:200]
    return filename.strip("_")


def generate_certificate_filename(cert: "CPERecord") -> str:
    """Generate a meaningful filename for a certificate"""
    # Extract key components
    course_name = cert.course_name or "Unknown_Course"
    credits = f"{float(cert.cpe_credits):.0f}CPE"

    # Get completion date
    if cert.completion_date:
        date_str = cert.completion_date.strftime("%Y%m%d")
    else:
        date_str = "NoDate"

    # Shorten course name if too long
    if len(course_name) > 50:
        # Try to keep meaningful parts
        words = course_name.split()
        short_name = ""
        for word in words:
            if len(short_name + word) < 45:
                short_name += word + "_"
            else:
                break
        course_name = short_name.rstrip("_")

    # Build filename: Date_Credits_CourseName
    new_filename = f"{date_str}_{credits}_{course_name}"

    # Sanitize for file system
    new_filename = sanitize_filename(new_filename)

    return new_filename


def generate_suggested_filename_with_extension(cert: "CPERecord") -> str:
    """Generate suggested filename with appropriate extension"""
    base_filename = generate_certificate_filename(cert)

    # Get original extension
    original_filename = cert.certificate_filename or ""
    extension = ".pdf"  # Default
    if "." in original_filename:
        extension = "." + original_filename.split(".")[-1].lower()

    return base_filename + extension


def get_filename_format_info() -> dict:
    """Get information about the filename format"""
    return {
        "format": "YYYYMMDD_XCPe_Course_Name.pdf",
        "example": "20250606_15CPE_Defensive_Divorce.pdf",
        "benefits": [
            "Easy to identify course content",
            "Sortable by date",
            "Shows CPE credits at a glance",
            "Matches CE Broker reporting data",
        ],
        "components": {
            "date": "YYYYMMDD format for easy sorting",
            "credits": "Number followed by 'CPE'",
            "course_name": "Sanitized course name with underscores",
            "extension": "Original file extension preserved",
        },
    }
