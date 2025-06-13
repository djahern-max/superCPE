from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime


class OnboardingStepCreate(BaseModel):
    data: Dict[str, Any]
    next_step: Optional[str] = None


class OnboardingStepResponse(BaseModel):
    id: str
    title: str
    description: str
    order: int
    required: bool


class OnboardingProgressResponse(BaseModel):
    id: str
    user_id: str
    current_step: Optional[str]
    completed_steps: List[str]
    step_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class OnboardingCompleteRequest(BaseModel):
    feedback: Optional[str] = None
