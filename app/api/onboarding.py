from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models import User, OnboardingProgress, OnboardingStep
from ..schemas.onboarding import (
    OnboardingProgressResponse,
    OnboardingStepCreate,
    OnboardingStepResponse,
    OnboardingCompleteRequest,
)
from ..auth import get_current_user

router = APIRouter(
    prefix="/onboarding", tags=["onboarding"], dependencies=[Depends(get_current_user)]
)


@router.get("/progress", response_model=OnboardingProgressResponse)
async def get_user_onboarding_progress(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get user's current onboarding progress"""
    progress = (
        db.query(OnboardingProgress)
        .filter(OnboardingProgress.user_id == current_user.id)
        .first()
    )

    if not progress:
        # Create initial progress record
        progress = OnboardingProgress(
            user_id=current_user.id,
            current_step="certificate_setup",
            completed_steps=[],
            step_data={},
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    return progress


@router.post("/steps/{step_id}/complete")
async def complete_onboarding_step(
    step_id: str,
    step_data: OnboardingStepCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Complete an onboarding step"""
    progress = (
        db.query(OnboardingProgress)
        .filter(OnboardingProgress.user_id == current_user.id)
        .first()
    )

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding progress not found",
        )

    # Update progress
    if step_id not in progress.completed_steps:
        progress.completed_steps.append(step_id)

    progress.step_data[step_id] = step_data.data
    progress.current_step = step_data.next_step
    progress.updated_at = datetime.utcnow()

    # Check if onboarding is complete
    required_steps = ["certificate_setup", "nh_configuration", "verification"]
    if all(step in progress.completed_steps for step in required_steps):
        progress.completed_at = datetime.utcnow()
        current_user.onboarding_completed = True

    db.commit()
    return {"status": "completed", "next_step": progress.current_step}


@router.get("/steps", response_model=List[OnboardingStepResponse])
async def get_onboarding_steps(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get available onboarding steps"""
    steps = [
        {
            "id": "certificate_setup",
            "title": "Certificate Setup",
            "description": "Upload and configure your NH certificates",
            "order": 1,
            "required": True,
        },
        {
            "id": "nh_configuration",
            "title": "NH Configuration",
            "description": "Configure your NH settings and preferences",
            "order": 2,
            "required": True,
        },
        {
            "id": "verification",
            "title": "Verification",
            "description": "Verify your NH setup is working correctly",
            "order": 3,
            "required": True,
        },
    ]
    return steps


@router.post("/complete")
async def complete_onboarding(
    request: OnboardingCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark onboarding as complete"""
    progress = (
        db.query(OnboardingProgress)
        .filter(OnboardingProgress.user_id == current_user.id)
        .first()
    )

    if progress:
        progress.completed_at = datetime.utcnow()
        current_user.onboarding_completed = True
        db.commit()

    return {"status": "onboarding_complete"}
