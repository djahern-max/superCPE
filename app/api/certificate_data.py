# app/api/certificate_data.py

"""
Certificate database operations and CRUD endpoints.
Handles data retrieval, updates, and management of certificate records.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
from typing import Optional, List
from datetime import datetime

from ..core.database import get_db
from ..models import CPERecord, User


router = APIRouter(
    prefix="/api/certificates",
    tags=["Certificate Data"],
    responses={404: {"description": "Not found"}},
)


def get_or_create_default_user(db: Session) -> User:
    """Get or create a default user for testing"""
    # Try to get any existing user first
    user = db.query(User).first()

    if user:
        return user

    # Only create if no users exist at all
    try:
        user = User(
            email="default@test.com",
            full_name="Default Test User",
            password_hash="$2b$12$defaulthash",  # Placeholder
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
    except Exception as e:
        db.rollback()
        # If creation fails, try to get any existing user
        existing_user = db.query(User).first()
        if existing_user:
            return existing_user
        raise e


@router.get("/summary")
async def get_certificates_summary(db: Session = Depends(get_db)):
    """Get summary of saved certificates from database"""
    try:
        # Get existing user
        user = get_or_create_default_user(db)

        # Get total counts and credits for this user
        user_records = db.query(CPERecord).filter(CPERecord.user_id == user.id)

        total_count = user_records.count()
        total_credits = (
            db.query(func.sum(CPERecord.cpe_credits))
            .filter(CPERecord.user_id == user.id)
            .scalar()
            or 0
        )

        # Group by field of study
        field_summary = (
            db.query(
                CPERecord.field_of_study,
                func.count(CPERecord.id).label("course_count"),
                func.sum(CPERecord.cpe_credits).label("total_credits"),
            )
            .filter(CPERecord.user_id == user.id)
            .group_by(CPERecord.field_of_study)
            .all()
        )

        # Recent certificates
        recent_certs = (
            user_records.order_by(CPERecord.extracted_at.desc()).limit(5).all()
        )

        return {
            "user_info": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "jurisdiction": user.primary_jurisdiction,
                "license_number": user.license_number,
            },
            "totals": {
                "total_certificates": total_count,
                "total_credits": float(total_credits),
            },
            "by_field_of_study": {
                item.field_of_study: {
                    "course_count": item.course_count,
                    "total_credits": float(item.total_credits),
                }
                for item in field_summary
            },
            "recent_certificates": [
                {
                    "id": cert.id,
                    "course_name": cert.course_name,
                    "credits": float(cert.cpe_credits),
                    "completion_date": (
                        cert.completion_date.isoformat()
                        if cert.completion_date
                        else None
                    ),
                    "field_of_study": cert.field_of_study,
                }
                for cert in recent_certs
            ],
            "note": f"Using existing default user (ID: {user.id})",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@router.get("/list")
async def list_certificates(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    field_of_study: Optional[str] = Query(None, description="Filter by field of study"),
    sort_by: str = Query("completion_date", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
):
    """List certificates with filtering, sorting, and pagination"""
    try:
        user = get_or_create_default_user(db)

        # Build query
        query = db.query(CPERecord).filter(CPERecord.user_id == user.id)

        # Apply filters
        if field_of_study:
            query = query.filter(CPERecord.field_of_study == field_of_study)

        # Apply sorting
        valid_sort_fields = [
            "completion_date",
            "extracted_at",
            "course_name",
            "cpe_credits",
            "field_of_study",
        ]
        if sort_by not in valid_sort_fields:
            sort_by = "completion_date"

        sort_column = getattr(CPERecord, sort_by)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # Get total count before pagination
        total_count = query.count()

        # Apply pagination
        certificates = query.offset(skip).limit(limit).all()

        # Format response
        certificate_list = [
            {
                "id": cert.id,
                "course_name": cert.course_name,
                "course_code": cert.course_code,
                "provider_name": cert.provider_name,
                "field_of_study": cert.field_of_study,
                "cpe_credits": float(cert.cpe_credits),
                "completion_date": (
                    cert.completion_date.isoformat() if cert.completion_date else None
                ),
                "certificate_filename": cert.certificate_filename,
                "extracted_at": (
                    cert.extracted_at.isoformat() if cert.extracted_at else None
                ),
                "delivery_method": cert.delivery_method,
                "nasba_sponsor_id": cert.nasba_sponsor_id,
            }
            for cert in certificates
        ]

        return {
            "status": "success",
            "pagination": {
                "total_count": total_count,
                "skip": skip,
                "limit": limit,
                "has_more": (skip + limit) < total_count,
            },
            "filters": {
                "field_of_study": field_of_study,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
            "certificates": certificate_list,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list certificates: {str(e)}"
        )


@router.get("/{certificate_id}")
async def get_certificate_detail(
    certificate_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information for a specific certificate"""
    try:
        user = get_or_create_default_user(db)

        certificate = (
            db.query(CPERecord)
            .filter(CPERecord.id == certificate_id, CPERecord.user_id == user.id)
            .first()
        )

        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")

        return {
            "status": "success",
            "certificate": {
                "id": certificate.id,
                "course_name": certificate.course_name,
                "course_code": certificate.course_code,
                "provider_name": certificate.provider_name,
                "field_of_study": certificate.field_of_study,
                "cpe_credits": float(certificate.cpe_credits),
                "completion_date": (
                    certificate.completion_date.isoformat()
                    if certificate.completion_date
                    else None
                ),
                "certificate_filename": certificate.certificate_filename,
                "certificate_hash": certificate.certificate_hash,
                "delivery_method": certificate.delivery_method,
                "nasba_sponsor_id": certificate.nasba_sponsor_id,
                "extraction_confidence": certificate.extraction_confidence,
                "extracted_at": (
                    certificate.extracted_at.isoformat()
                    if certificate.extracted_at
                    else None
                ),
                "created_at": (
                    certificate.created_at.isoformat()
                    if hasattr(certificate, "created_at") and certificate.created_at
                    else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get certificate: {str(e)}"
        )


@router.put("/{certificate_id}")
async def update_certificate(
    certificate_id: int,
    updates: dict,
    db: Session = Depends(get_db),
):
    """Update certificate details"""
    try:
        user = get_or_create_default_user(db)

        certificate = (
            db.query(CPERecord)
            .filter(CPERecord.id == certificate_id, CPERecord.user_id == user.id)
            .first()
        )

        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")

        # Define updatable fields
        updatable_fields = {
            "course_name",
            "course_code",
            "provider_name",
            "field_of_study",
            "cpe_credits",
            "completion_date",
            "delivery_method",
            "certificate_filename",
        }

        # Apply updates
        updated_fields = []
        for field, value in updates.items():
            if field in updatable_fields and hasattr(certificate, field):
                # Handle special field types
                if field == "cpe_credits" and value is not None:
                    value = float(value)
                elif field == "completion_date" and value is not None:
                    if isinstance(value, str):
                        from .shared.certificate_processing import parse_date

                        value = parse_date(value)

                setattr(certificate, field, value)
                updated_fields.append(field)

        if updated_fields:
            certificate.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(certificate)

        return {
            "status": "success",
            "message": (
                f"Updated fields: {', '.join(updated_fields)}"
                if updated_fields
                else "No fields updated"
            ),
            "updated_fields": updated_fields,
            "certificate": {
                "id": certificate.id,
                "course_name": certificate.course_name,
                "cpe_credits": float(certificate.cpe_credits),
                "field_of_study": certificate.field_of_study,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update certificate: {str(e)}"
        )


@router.delete("/{certificate_id}")
async def delete_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
):
    """Delete a certificate record"""
    try:
        user = get_or_create_default_user(db)

        certificate = (
            db.query(CPERecord)
            .filter(CPERecord.id == certificate_id, CPERecord.user_id == user.id)
            .first()
        )

        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")

        # Store info for response
        course_name = certificate.course_name
        credits = float(certificate.cpe_credits)

        # Delete the record
        db.delete(certificate)
        db.commit()

        return {
            "status": "success",
            "message": f"Certificate deleted: {course_name}",
            "deleted_certificate": {
                "id": certificate_id,
                "course_name": course_name,
                "credits": credits,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete certificate: {str(e)}"
        )


@router.get("/fields/available")
async def get_available_fields(db: Session = Depends(get_db)):
    """Get list of available field values for filtering"""
    try:
        user = get_or_create_default_user(db)

        # Get unique field of study values
        fields_of_study = (
            db.query(CPERecord.field_of_study)
            .filter(CPERecord.user_id == user.id)
            .distinct()
            .all()
        )

        # Get unique providers
        providers = (
            db.query(CPERecord.provider_name)
            .filter(CPERecord.user_id == user.id)
            .distinct()
            .all()
        )

        # Get delivery methods
        delivery_methods = (
            db.query(CPERecord.delivery_method)
            .filter(CPERecord.user_id == user.id)
            .distinct()
            .all()
        )

        return {
            "status": "success",
            "available_filters": {
                "fields_of_study": [item[0] for item in fields_of_study if item[0]],
                "providers": [item[0] for item in providers if item[0]],
                "delivery_methods": [item[0] for item in delivery_methods if item[0]],
            },
            "sortable_fields": [
                "completion_date",
                "extracted_at",
                "course_name",
                "cpe_credits",
                "field_of_study",
            ],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get available fields: {str(e)}"
        )
