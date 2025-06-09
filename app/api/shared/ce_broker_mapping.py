# app/api/shared/ce_broker_mapping.py

"""
CE Broker format mapping utilities and constants.
"""

from typing import List, Dict


# Field mapping for CE Broker compatibility
CE_BROKER_SUBJECT_MAPPING = {
    "Taxes": ["Taxes"],
    "Tax": ["Taxes"],
    "Accounting": ["Public accounting"],
    "Auditing": ["Public auditing"],
    "Auditing - Fraud": ["Public auditing"],
    "Economics": ["Economics"],
    "Personnel / Human Resources": ["Personnel and human resources"],
    "Communications and Marketing": ["Communications", "Marketing"],
    "General": ["General"],
}

CE_BROKER_DELIVERY_MAPPING = {
    "QAS Self-Study": "Computer-Based Training (ie: online courses)",
    "Self-Study": "Computer-Based Training (ie: online courses)",
    "Online": "Computer-Based Training (ie: online courses)",
    "Webinar": "Live (Involves live interaction with presenter/host)",
    "Live": "Live (Involves live interaction with presenter/host)",
    "Correspondence": "Correspondence",
}


def map_to_ce_broker_format(extracted_data: dict) -> dict:
    """Map extracted certificate data to CE Broker format"""
    from ...main import map_to_ce_broker_format as main_map

    return main_map(extracted_data)


def map_to_ce_broker_subjects(field_of_study: str) -> List[str]:
    """Map internal field of study to CE Broker subject categories"""
    return CE_BROKER_SUBJECT_MAPPING.get(field_of_study, ["General"])


def map_to_ce_broker_delivery(delivery_method: str) -> str:
    """Map internal delivery method to CE Broker format"""
    return CE_BROKER_DELIVERY_MAPPING.get(
        delivery_method, "Computer-Based Training (ie: online courses)"
    )


def format_ce_broker_record(cert, completion_date: str = None) -> Dict:
    """
    Format a certificate record for CE Broker submission

    Args:
        cert: CPERecord instance
        completion_date: Optional formatted date string

    Returns:
        Dictionary formatted for CE Broker
    """
    # Map subjects
    ce_subjects = map_to_ce_broker_subjects(cert.field_of_study)

    # Format completion date if not provided
    if completion_date is None:
        completion_date = (
            cert.completion_date.strftime("%m/%d/%Y") if cert.completion_date else ""
        )

    return {
        "course_name": cert.course_name or "Unknown Course",
        "provider_name": cert.provider_name or "Professional Education Services",
        "completion_date": completion_date,
        "credits": float(cert.cpe_credits),
        "delivery_method": map_to_ce_broker_delivery(
            cert.delivery_method or "QAS Self-Study"
        ),
        "subject_areas": ", ".join(ce_subjects),
        "course_code": cert.course_code or "",
        "field_of_study": cert.field_of_study or "General",
        "certificate_filename": cert.certificate_filename or "",
        "nasba_sponsor": cert.nasba_sponsor_id or "112530",
        "ce_broker_subjects_list": ce_subjects,  # For easier frontend handling
    }


def get_ce_broker_instructions() -> Dict:
    """Get standardized CE Broker submission instructions"""
    return {
        "step_1": "Copy course_name for 'What is the name of the CE course?'",
        "step_2": "Copy provider_name for 'What is the name of the educational provider?'",
        "step_3": "Select the checkboxes matching the subject_areas",
        "step_4": "Enter completion_date and select delivery_method",
        "step_5": "Upload the certificate file",
        "provider_note": "Provider for all courses: Professional Education Services",
        "delivery_note": "Delivery Method for all: Computer-Based Training (ie: online courses)",
    }
