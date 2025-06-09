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


@router.get("/certificate-filenames")
async def get_certificate_filenames(db: Session = Depends(get_db)):
    """Get suggested filenames for all certificates"""
    try:
        user = get_or_create_default_user(db)

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            return {"status": "no_data", "message": "No certificates found"}

        filename_mappings = []

        for cert in certificates:
            # Generate new filename
            suggested_filename = generate_suggested_filename_with_extension(cert)

            mapping = {
                "certificate_id": cert.id,
                "original_filename": cert.certificate_filename,
                "suggested_filename": suggested_filename,
                "course_name": cert.course_name,
                "credits": float(cert.cpe_credits),
                "completion_date": (
                    cert.completion_date.strftime("%m/%d/%Y")
                    if cert.completion_date
                    else "N/A"
                ),
                "course_code": cert.course_code,
            }

            filename_mappings.append(mapping)

        return {
            "status": "success",
            "total_certificates": len(certificates),
            "filename_mappings": filename_mappings,
            "format_info": get_filename_format_info(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Filename generation failed: {str(e)}"
        )


@router.get("/list-certificate-files")
async def list_certificate_files(
    storage_path: str = CERTIFICATE_STORAGE_PATH, db: Session = Depends(get_db)
):
    """List all certificate files and their database matches"""
    try:
        user = get_or_create_default_user(db)

        # Check if storage path exists
        if not os.path.exists(storage_path):
            return {
                "status": "error",
                "message": f"Storage path not found: {storage_path}",
                "suggestion": "Update the storage_path parameter",
            }

        # Get files from directory
        actual_files = os.listdir(storage_path)
        pdf_files = [f for f in actual_files if f.lower().endswith(".pdf")]

        # Get certificates from database
        certificates = db.query(CPERecord).filter(CPERecord.user_id == user.id).all()
        db_filenames = [
            cert.certificate_filename
            for cert in certificates
            if cert.certificate_filename
        ]

        # Match files with database records
        file_analysis = []

        for filename in pdf_files:
            matching_cert = next(
                (
                    cert
                    for cert in certificates
                    if cert.certificate_filename == filename
                ),
                None,
            )

            if matching_cert:
                suggested_name = generate_suggested_filename_with_extension(
                    matching_cert
                )

                file_info = {
                    "filename": filename,
                    "status": "matched",
                    "certificate_id": matching_cert.id,
                    "course_name": matching_cert.course_name,
                    "credits": float(matching_cert.cpe_credits),
                    "completion_date": (
                        matching_cert.completion_date.strftime("%m/%d/%Y")
                        if matching_cert.completion_date
                        else "N/A"
                    ),
                    "suggested_new_name": suggested_name,
                }
            else:
                file_info = {
                    "filename": filename,
                    "status": "unmatched",
                    "note": "File exists but no database record found",
                }

            file_analysis.append(file_info)

        # Check for database records without files
        missing_files = []
        for cert in certificates:
            if cert.certificate_filename and cert.certificate_filename not in pdf_files:
                missing_files.append(
                    {
                        "certificate_id": cert.id,
                        "filename": cert.certificate_filename,
                        "course_name": cert.course_name,
                        "status": "file_missing",
                    }
                )

        return {
            "status": "success",
            "storage_path": storage_path,
            "summary": {
                "total_pdf_files": len(pdf_files),
                "matched_files": len(
                    [f for f in file_analysis if f["status"] == "matched"]
                ),
                "unmatched_files": len(
                    [f for f in file_analysis if f["status"] == "unmatched"]
                ),
                "missing_files": len(missing_files),
                "database_records": len(certificates),
            },
            "file_analysis": file_analysis,
            "missing_files": missing_files,
            "instructions": {
                "next_steps": [
                    "Review the file analysis above",
                    "Use POST /rename-physical-files?dry_run=true to preview renames",
                    "Use POST /rename-physical-files?dry_run=false to execute renames",
                ]
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File listing failed: {str(e)}")


@router.post("/rename-physical-files")
async def rename_physical_certificate_files(
    db: Session = Depends(get_db),
    dry_run: bool = True,
    storage_path: str = CERTIFICATE_STORAGE_PATH,
):
    """Rename the actual physical certificate files on disk"""
    try:
        user = get_or_create_default_user(db)

        # Check if storage path exists
        if not os.path.exists(storage_path):
            raise HTTPException(
                status_code=404, detail=f"Storage path not found: {storage_path}"
            )

        certificates = (
            db.query(CPERecord)
            .filter(CPERecord.user_id == user.id)
            .order_by(CPERecord.completion_date.desc())
            .all()
        )

        if not certificates:
            return {"status": "no_data", "message": "No certificates found in database"}

        # Get list of actual files in directory
        actual_files = os.listdir(storage_path)
        pdf_files = [f for f in actual_files if f.lower().endswith(".pdf")]

        rename_results = []
        successful_renames = 0
        failed_renames = 0
        files_not_found = 0

        for cert in certificates:
            try:
                original_filename = cert.certificate_filename
                if not original_filename:
                    rename_results.append(
                        {
                            "certificate_id": cert.id,
                            "course_name": cert.course_name,
                            "status": "skipped",
                            "reason": "No filename in database",
                        }
                    )
                    continue

                # Check if file actually exists
                original_file_path = os.path.join(storage_path, original_filename)
                if not os.path.exists(original_file_path):
                    rename_results.append(
                        {
                            "certificate_id": cert.id,
                            "course_name": cert.course_name,
                            "original_filename": original_filename,
                            "status": "file_not_found",
                            "reason": f"File not found in {storage_path}",
                        }
                    )
                    files_not_found += 1
                    continue

                # Generate new filename
                new_filename = generate_suggested_filename_with_extension(cert)
                new_file_path = os.path.join(storage_path, new_filename)

                # Check if target filename already exists
                counter = 1
                base_new_filename = new_filename
                while (
                    os.path.exists(new_file_path)
                    and new_file_path != original_file_path
                ):
                    name_without_ext = new_filename.rsplit(".", 1)[0] + f"_{counter}"
                    extension = (
                        "." + new_filename.split(".")[-1] if "." in new_filename else ""
                    )
                    new_filename = name_without_ext + extension
                    new_file_path = os.path.join(storage_path, new_filename)
                    counter += 1

                rename_info = {
                    "certificate_id": cert.id,
                    "course_name": cert.course_name,
                    "original_filename": original_filename,
                    "new_filename": new_filename,
                    "original_path": original_file_path,
                    "new_path": new_file_path,
                    "status": "pending",
                }

                if not dry_run:
                    # Actually rename the physical file
                    os.rename(original_file_path, new_file_path)

                    # Update database record
                    cert.certificate_filename = new_filename
                    cert.updated_at = datetime.utcnow()

                    rename_info["status"] = "renamed"
                    successful_renames += 1
                else:
                    rename_info["status"] = "dry_run"

                rename_results.append(rename_info)

            except Exception as e:
                rename_info = {
                    "certificate_id": cert.id,
                    "course_name": cert.course_name or "Unknown",
                    "original_filename": cert.certificate_filename or "",
                    "error": str(e),
                    "status": "failed",
                }
                rename_results.append(rename_info)
                failed_renames += 1

        if not dry_run and successful_renames > 0:
            # Commit database changes
            db.commit()

        return {
            "status": "success" if not dry_run else "dry_run",
            "message": f"Physical file renaming {'completed' if not dry_run else 'simulated'}",
            "storage_path": storage_path,
            "summary": {
                "total_certificates": len(certificates),
                "successful_renames": successful_renames,
                "failed_renames": failed_renames,
                "files_not_found": files_not_found,
                "dry_run_mode": dry_run,
            },
            "files_in_directory": {
                "total_files": len(actual_files),
                "pdf_files": len(pdf_files),
                "file_list": (
                    pdf_files[:10]
                    if len(pdf_files) <= 10
                    else pdf_files[:10] + [f"... and {len(pdf_files) - 10} more"]
                ),
            },
            "rename_results": rename_results,
            "instructions": {
                "dry_run": "Set dry_run=false to actually rename physical files",
                "backup_note": "Consider backing up your files before renaming",
                "path_note": f"Files will be renamed in: {storage_path}",
            },
        }

    except Exception as e:
        if not dry_run:
            db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Physical file rename failed: {str(e)}"
        )


@router.post("/backup-certificate-files")
async def backup_certificate_files(
    storage_path: str = CERTIFICATE_STORAGE_PATH, backup_suffix: str = "_backup"
):
    """Create backup copies of all certificate files before renaming"""
    try:
        if not os.path.exists(storage_path):
            raise HTTPException(
                status_code=404, detail=f"Storage path not found: {storage_path}"
            )

        # Create backup directory
        backup_dir = storage_path + backup_suffix
        os.makedirs(backup_dir, exist_ok=True)

        # Get all PDF files
        actual_files = os.listdir(storage_path)
        pdf_files = [f for f in actual_files if f.lower().endswith(".pdf")]

        backup_results = []
        successful_backups = 0
        failed_backups = 0

        for filename in pdf_files:
            try:
                source_path = os.path.join(storage_path, filename)
                backup_path = os.path.join(backup_dir, filename)

                # Copy file to backup directory
                shutil.copy2(source_path, backup_path)

                backup_results.append(
                    {
                        "filename": filename,
                        "source": source_path,
                        "backup": backup_path,
                        "status": "backed_up",
                    }
                )
                successful_backups += 1

            except Exception as e:
                backup_results.append(
                    {"filename": filename, "error": str(e), "status": "failed"}
                )
                failed_backups += 1

        return {
            "status": "success",
            "message": f"Backup completed to {backup_dir}",
            "summary": {
                "total_files": len(pdf_files),
                "successful_backups": successful_backups,
                "failed_backups": failed_backups,
                "backup_directory": backup_dir,
            },
            "backup_results": backup_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.post("/sync-database-to-physical-files")
async def sync_database_to_physical_files(
    storage_path: str = CERTIFICATE_STORAGE_PATH,
    db: Session = Depends(get_db),
    dry_run: bool = True,
):
    """Sync database filenames back to match actual physical files"""
    try:
        user = get_or_create_default_user(db)

        if not os.path.exists(storage_path):
            raise HTTPException(
                status_code=404, detail=f"Storage path not found: {storage_path}"
            )

        # Get actual files
        actual_files = os.listdir(storage_path)
        pdf_files = [f for f in actual_files if f.lower().endswith(".pdf")]

        # Get certificates from database
        certificates = db.query(CPERecord).filter(CPERecord.user_id == user.id).all()

        # Try to match files to certificates based on course codes or other identifiers
        sync_results = []
        matched_count = 0
        unmatched_files = []

        for cert in certificates:
            course_code = cert.course_code
            best_match = None

            # Try to find matching file by course code
            if course_code:
                for filename in pdf_files:
                    if course_code in filename:
                        best_match = filename
                        break

            # If no course code match, try to match by certificate hash in filename
            if not best_match and cert.certificate_filename:
                # Look for files with similar hash patterns
                for filename in pdf_files:
                    if (
                        "Certificate_" in filename
                        and cert.certificate_filename
                        and "Certificate_" in cert.certificate_filename
                    ):
                        # Extract the hash part
                        if (
                            cert.certificate_filename.replace(
                                "Certificate_", ""
                            ).replace(".pdf", "")
                            in filename
                        ):
                            best_match = filename
                            break

            sync_info = {
                "certificate_id": cert.id,
                "course_name": cert.course_name,
                "course_code": course_code,
                "current_db_filename": cert.certificate_filename,
                "matched_physical_file": best_match,
                "status": "pending",
            }

            if best_match:
                if not dry_run:
                    # Update database to match physical file
                    cert.certificate_filename = best_match
                    cert.updated_at = datetime.utcnow()
                    sync_info["status"] = "synced"
                    matched_count += 1
                else:
                    sync_info["status"] = "would_sync"
                    matched_count += 1

                # Remove from unmatched list
                if best_match in pdf_files:
                    pdf_files.remove(best_match)
            else:
                sync_info["status"] = "no_match_found"

            sync_results.append(sync_info)

        # Remaining unmatched files
        unmatched_files = pdf_files

        if not dry_run and matched_count > 0:
            db.commit()

        return {
            "status": "success" if not dry_run else "dry_run",
            "message": f"Database sync {'completed' if not dry_run else 'preview'}",
            "storage_path": storage_path,
            "summary": {
                "total_certificates": len(certificates),
                "matched_and_synced": matched_count,
                "no_match_found": len(
                    [r for r in sync_results if r["status"] in ["no_match_found"]]
                ),
                "unmatched_physical_files": len(unmatched_files),
                "dry_run_mode": dry_run,
            },
            "sync_results": sync_results,
            "unmatched_files": unmatched_files,
            "instructions": {
                "next_steps": [
                    "Review the sync results above",
                    "Set dry_run=false to actually update the database",
                    "Then you can use the rename endpoints to rename physical files",
                ]
            },
        }

    except Exception as e:
        if not dry_run:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Database sync failed: {str(e)}")


@router.post("/manual-file-mapping")
async def manual_file_mapping(
    mappings: List[dict],  # List of {"certificate_id": int, "filename": str}
    db: Session = Depends(get_db),
    dry_run: bool = True,
):
    """Manually map certificate records to physical files"""
    try:
        user = get_or_create_default_user(db)

        mapping_results = []
        successful_mappings = 0

        for mapping in mappings:
            cert_id = mapping.get("certificate_id")
            filename = mapping.get("filename")

            if not cert_id or not filename:
                mapping_results.append(
                    {
                        "error": "Missing certificate_id or filename",
                        "provided_mapping": mapping,
                        "status": "invalid",
                    }
                )
                continue

            # Find certificate
            cert = (
                db.query(CPERecord)
                .filter(CPERecord.id == cert_id, CPERecord.user_id == user.id)
                .first()
            )

            if not cert:
                mapping_results.append(
                    {
                        "certificate_id": cert_id,
                        "filename": filename,
                        "error": "Certificate not found",
                        "status": "not_found",
                    }
                )
                continue

            mapping_info = {
                "certificate_id": cert_id,
                "course_name": cert.course_name,
                "old_filename": cert.certificate_filename,
                "new_filename": filename,
                "status": "pending",
            }

            if not dry_run:
                cert.certificate_filename = filename
                cert.updated_at = datetime.utcnow()
                mapping_info["status"] = "mapped"
                successful_mappings += 1
            else:
                mapping_info["status"] = "would_map"

            mapping_results.append(mapping_info)

        if not dry_run and successful_mappings > 0:
            db.commit()

        return {
            "status": "success" if not dry_run else "dry_run",
            "message": f"Manual mapping {'completed' if not dry_run else 'preview'}",
            "summary": {
                "total_mappings": len(mappings),
                "successful_mappings": successful_mappings,
                "dry_run_mode": dry_run,
            },
            "mapping_results": mapping_results,
        }

    except Exception as e:
        if not dry_run:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Manual mapping failed: {str(e)}")
