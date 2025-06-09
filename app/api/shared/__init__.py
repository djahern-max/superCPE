# app/api/shared/__init__.py

"""
Shared utilities for certificate processing across all routers.
"""

from .certificate_processing import (
    extract_text_from_file,
    parse_certificate_text,
    parse_date,
    generate_file_hash,
    validate_file_type,
    extract_and_parse_certificate,
)

from .ce_broker_mapping import (
    map_to_ce_broker_format,
    map_to_ce_broker_subjects,
    map_to_ce_broker_delivery,
    format_ce_broker_record,
    get_ce_broker_instructions,
    CE_BROKER_SUBJECT_MAPPING,
    CE_BROKER_DELIVERY_MAPPING,
)

from .filename_utils import (
    sanitize_filename,
    generate_certificate_filename,
    generate_suggested_filename_with_extension,
    get_filename_format_info,
)

__all__ = [
    # Certificate processing
    "extract_text_from_file",
    "parse_certificate_text",
    "parse_date",
    "generate_file_hash",
    "validate_file_type",
    "extract_and_parse_certificate",
    # CE Broker mapping
    "map_to_ce_broker_format",
    "map_to_ce_broker_subjects",
    "map_to_ce_broker_delivery",
    "format_ce_broker_record",
    "get_ce_broker_instructions",
    "CE_BROKER_SUBJECT_MAPPING",
    "CE_BROKER_DELIVERY_MAPPING",
    # Filename utilities
    "sanitize_filename",
    "generate_certificate_filename",
    "generate_suggested_filename_with_extension",
    "get_filename_format_info",
]
