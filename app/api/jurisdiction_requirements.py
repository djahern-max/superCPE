# app/api/jurisdiction_requirements.py - State Requirements Endpoint

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import date, datetime

from app.core.database import get_db
from app.models import CPAJurisdiction, User
from app.api.auth import get_current_user

router = APIRouter(
    prefix="/api/jurisdictions",
    tags=["Jurisdiction Requirements"],
)


# Response Models
class JurisdictionRequirements(BaseModel):
    # Basic Information
    code: str
    name: str
    board_name: Optional[str]
    board_website: Optional[str]
    licensing_website: Optional[str]

    # CPE Requirements
    general_hours_required: int
    ethics_hours_required: Optional[int]
    live_hours_required: Optional[int]
    minimum_hours_per_year: Optional[int]

    # Reporting Details
    reporting_period_type: Optional[str]
    reporting_period_months: Optional[int]
    reporting_period_description: Optional[str]
    renewal_date_pattern: Optional[str]

    # Special Rules
    self_study_max_hours: Optional[int]
    carry_forward_max_hours: Optional[int]

    # CE Broker Information
    ce_broker_required: Optional[bool]
    ce_broker_mandatory_date: Optional[date]

    # Data Quality
    data_confidence: Optional[float]
    nasba_last_updated: Optional[date]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class JurisdictionSummary(BaseModel):
    code: str
    name: str
    general_hours_required: int
    ethics_hours_required: Optional[int]
    reporting_period_type: Optional[str]
    ce_broker_required: Optional[bool]


class JurisdictionComparison(BaseModel):
    jurisdiction_1: JurisdictionRequirements
    jurisdiction_2: JurisdictionRequirements
    differences: Dict[str, Dict[str, Any]]


@router.get("/list", response_model=List[JurisdictionSummary])
async def get_all_jurisdictions_summary(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get a summary list of all available jurisdictions"""

    jurisdictions = db.query(CPAJurisdiction).order_by(CPAJurisdiction.name).all()

    return [
        JurisdictionSummary(
            code=j.code,
            name=j.name,
            general_hours_required=j.general_hours_required,
            ethics_hours_required=j.ethics_hours_required,
            reporting_period_type=j.reporting_period_type,
            ce_broker_required=j.ce_broker_required or False,
        )
        for j in jurisdictions
    ]


@router.get("/{state_code}", response_model=JurisdictionRequirements)
async def get_jurisdiction_requirements(
    state_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed CPE requirements for a specific state/jurisdiction

    Args:
        state_code: Two-letter state code (e.g., NH, CA, TX, FL, NY)

    Returns:
        Complete jurisdiction requirements including CPE hours, reporting periods, etc.
    """

    # Convert to uppercase for consistency
    state_code = state_code.upper()

    # Validate state code format
    if len(state_code) != 2 or not state_code.isalpha():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State code must be a 2-letter abbreviation (e.g., NH, CA, TX)",
        )

    # Get jurisdiction from database
    jurisdiction = (
        db.query(CPAJurisdiction).filter(CPAJurisdiction.code == state_code).first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirements for {state_code} not found. This state may not be monitored yet.",
        )

    return JurisdictionRequirements.from_orm(jurisdiction)


@router.get("/{state_code}/summary")
async def get_jurisdiction_summary(
    state_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a quick summary of key requirements for a state"""

    state_code = state_code.upper()
    jurisdiction = (
        db.query(CPAJurisdiction).filter(CPAJurisdiction.code == state_code).first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirements for {state_code} not found",
        )

    # Calculate next renewal based on reporting period
    next_renewal_info = calculate_next_renewal(jurisdiction)

    return {
        "jurisdiction": {
            "code": jurisdiction.code,
            "name": jurisdiction.name,
            "board_website": jurisdiction.board_website,
        },
        "requirements": {
            "total_hours": jurisdiction.general_hours_required,
            "ethics_hours": jurisdiction.ethics_hours_required or 0,
            "reporting_period": jurisdiction.reporting_period_type,
            "period_length": (
                f"{jurisdiction.reporting_period_months} months"
                if jurisdiction.reporting_period_months
                else "Unknown"
            ),
            "minimum_per_year": jurisdiction.minimum_hours_per_year,
            "carry_forward_max": jurisdiction.carry_forward_max_hours,
        },
        "renewal_info": next_renewal_info,
        "ce_broker": {
            "required": jurisdiction.ce_broker_required or False,
            "mandatory_date": jurisdiction.ce_broker_mandatory_date,
            "status": "Required" if jurisdiction.ce_broker_required else "Not Required",
        },
        "data_quality": {
            "confidence": jurisdiction.data_confidence,
            "last_updated": jurisdiction.updated_at,
            "data_freshness": calculate_data_freshness(jurisdiction.updated_at),
        },
    }


@router.get("/compare/{state1}/{state2}", response_model=JurisdictionComparison)
async def compare_jurisdictions(
    state1: str,
    state2: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare requirements between two states"""

    state1 = state1.upper()
    state2 = state2.upper()

    # Get both jurisdictions
    j1 = db.query(CPAJurisdiction).filter(CPAJurisdiction.code == state1).first()
    j2 = db.query(CPAJurisdiction).filter(CPAJurisdiction.code == state2).first()

    if not j1:
        raise HTTPException(status_code=404, detail=f"State {state1} not found")
    if not j2:
        raise HTTPException(status_code=404, detail=f"State {state2} not found")

    # Calculate differences
    differences = {}

    fields_to_compare = [
        "general_hours_required",
        "ethics_hours_required",
        "reporting_period_type",
        "reporting_period_months",
        "minimum_hours_per_year",
        "carry_forward_max_hours",
        "ce_broker_required",
    ]

    for field in fields_to_compare:
        val1 = getattr(j1, field)
        val2 = getattr(j2, field)

        if val1 != val2:
            differences[field] = {
                state1: val1,
                state2: val2,
                "difference": calculate_difference(val1, val2),
            }

    return JurisdictionComparison(
        jurisdiction_1=JurisdictionRequirements.from_orm(j1),
        jurisdiction_2=JurisdictionRequirements.from_orm(j2),
        differences=differences,
    )


@router.get("/search")
async def search_jurisdictions(
    hours: Optional[int] = Query(None, description="Filter by CPE hours required"),
    ethics_hours: Optional[int] = Query(
        None, description="Filter by ethics hours required"
    ),
    reporting_period: Optional[str] = Query(
        None, description="Filter by reporting period (annual, biennial, triennial)"
    ),
    ce_broker: Optional[bool] = Query(
        None, description="Filter by CE Broker requirement"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search jurisdictions by specific criteria"""

    query = db.query(CPAJurisdiction)

    # Apply filters
    if hours is not None:
        query = query.filter(CPAJurisdiction.general_hours_required == hours)

    if ethics_hours is not None:
        query = query.filter(CPAJurisdiction.ethics_hours_required == ethics_hours)

    if reporting_period:
        query = query.filter(
            CPAJurisdiction.reporting_period_type == reporting_period.lower()
        )

    if ce_broker is not None:
        query = query.filter(CPAJurisdiction.ce_broker_required == ce_broker)

    jurisdictions = query.order_by(CPAJurisdiction.name).all()

    return {
        "search_criteria": {
            "hours": hours,
            "ethics_hours": ethics_hours,
            "reporting_period": reporting_period,
            "ce_broker": ce_broker,
        },
        "results_count": len(jurisdictions),
        "jurisdictions": [
            {
                "code": j.code,
                "name": j.name,
                "hours_required": j.general_hours_required,
                "ethics_hours": j.ethics_hours_required,
                "reporting_period": j.reporting_period_type,
                "ce_broker_required": j.ce_broker_required,
            }
            for j in jurisdictions
        ],
    }


# Helper functions
def calculate_next_renewal(jurisdiction: CPAJurisdiction) -> Dict:
    """Calculate next renewal information based on jurisdiction rules"""

    if not jurisdiction.reporting_period_months:
        return {"next_renewal": "Unknown", "days_remaining": "Unknown"}

    # This is simplified - in reality, you'd need more complex logic
    # based on license issue dates, renewal groups, etc.

    if jurisdiction.reporting_period_type == "annual":
        next_renewal = "December 31, 2025"  # Simplified
    elif jurisdiction.reporting_period_type == "biennial":
        next_renewal = "Based on license issue date (2-year cycle)"
    elif jurisdiction.reporting_period_type == "triennial":
        next_renewal = "Based on license issue date (3-year cycle)"
    else:
        next_renewal = "See jurisdiction-specific rules"

    return {
        "next_renewal": next_renewal,
        "renewal_pattern": jurisdiction.renewal_date_pattern,
        "period_description": jurisdiction.reporting_period_description,
    }


def calculate_data_freshness(updated_at: datetime) -> str:
    """Calculate how fresh the data is"""

    if not updated_at:
        return "Unknown"

    days_old = (datetime.now() - updated_at).days

    if days_old == 0:
        return "Updated today"
    elif days_old == 1:
        return "Updated yesterday"
    elif days_old <= 7:
        return f"Updated {days_old} days ago"
    elif days_old <= 30:
        return f"Updated {days_old // 7} weeks ago"
    else:
        return f"Updated {days_old // 30} months ago"


def calculate_difference(val1, val2):
    """Calculate the difference between two values"""

    if val1 is None or val2 is None:
        return "One value is missing"

    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
        diff = abs(val1 - val2)
        return f"Difference of {diff}"

    return "Values differ"
