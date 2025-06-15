# app/api/file_management.py

"""
Physical file management endpoints.
Handles file system operations, renaming, backups, and filename management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os
import shutil
from pathlib import Path

from ..core.database import get_db
from ..models import CPERecord
from .certificate_data import get_or_create_default_user
from .shared.filename_utils import (
    generate_certificate_filename,
    generate_suggested_filename_with_extension,
    get_filename_format_info,
)


router = APIRouter(
    prefix="/api/certificates/files",
    tags=["File Management"],
    responses={404: {"description": "Not found"}},
)

# Default storage path - can be overridden via parameter
CERTIFICATE_STORAGE_PATH = "/Users/ryze.ai/Desktop/PDF_BOT"
