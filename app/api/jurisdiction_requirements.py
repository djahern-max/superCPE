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


# Replace your existing JurisdictionRequirements model in jurisdiction_requirements.py


class JurisdictionRequirements(BaseModel):
    # Basic Information
    code: str
    name: str
    board_name: Optional[str] = None
    board_website: Optional[str] = None
    licensing_website: Optional[str] = None

    # Core CPE Requirements
    general_hours_required: int
    ethics_hours_required: Optional[int] = None
    live_hours_required: Optional[int] = None
    minimum_hours_per_year: Optional[int] = None

    # Reporting Details
    reporting_period_type: Optional[str] = None
    reporting_period_months: Optional[int] = None
    reporting_period_description: Optional[str] = None
    renewal_date_pattern: Optional[str] = None

    # Study Options & Flexibility
    self_study_max_hours: Optional[int] = None
    carry_forward_max_hours: Optional[int] = None

    # CE Broker Information
    ce_broker_required: Optional[bool] = None
    ce_broker_mandatory_date: Optional[date] = None

    # Technical & Specialized Requirements
    technical_hours_required: Optional[int] = None
    technical_hours_per_year: Optional[int] = None
    regulatory_review_hours: Optional[int] = None
    regulatory_review_frequency_months: Optional[int] = None
    regulatory_review_passing_score: Optional[int] = None
    government_audit_hours: Optional[int] = None
    accounting_auditing_hours: Optional[int] = None
    preparation_engagement_hours: Optional[int] = None
    fraud_hours_required: Optional[int] = None

    # New Licensee Requirements
    new_licensee_hours_per_six_months: Optional[int] = None
    new_licensee_regulatory_review_required: Optional[bool] = None

    # Course Requirements
    interactive_courses_required: Optional[bool] = None
    minimum_course_length_hours: Optional[int] = None
    ethics_course_minimum_length_hours: Optional[int] = None
    ethics_exam_passing_score: Optional[int] = None

    # Special Requirements & Notes
    special_requirements: Optional[str] = None

    # Data Quality & Metadata
    data_source: Optional[str] = None
    data_confidence: Optional[float] = None
    nasba_last_updated: Optional[date] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    # Custom method to provide user-friendly display of requirements
    def get_requirement_summary(self) -> dict:
        """Generate a user-friendly summary of all requirements"""
        summary = {}

        # Core requirements
        summary["core_requirements"] = {
            "total_hours": self.general_hours_required or "Not specified",
            "ethics_hours": self.ethics_hours_required or "Not required",
            "live_hours": self.live_hours_required or "Not required",
            "minimum_per_year": self.minimum_hours_per_year or "Not specified",
        }

        # Reporting cycle
        summary["reporting_cycle"] = {
            "period_type": self.reporting_period_type or "Not specified",
            "period_length": (
                f"{self.reporting_period_months} months"
                if self.reporting_period_months
                else "Not specified"
            ),
            "renewal_pattern": self.renewal_date_pattern or "Not specified",
        }

        # Flexibility options
        summary["flexibility"] = {
            "self_study_allowed": (
                f"Up to {self.self_study_max_hours} hours"
                if self.self_study_max_hours
                else "Not specified"
            ),
            "carry_forward": (
                f"Up to {self.carry_forward_max_hours} hours"
                if self.carry_forward_max_hours
                else "Not allowed"
            ),
        }

        # CE Broker status
        summary["ce_broker"] = {
            "required": "Yes" if self.ce_broker_required else "No",
            "mandatory_date": (
                self.ce_broker_mandatory_date.strftime("%B %d, %Y")
                if self.ce_broker_mandatory_date
                else "N/A"
            ),
        }

        # Specialized requirements
        specialized = {}
        if self.technical_hours_required:
            specialized["technical_hours"] = (
                f"{self.technical_hours_required} hours required"
            )
        if self.regulatory_review_hours:
            specialized["regulatory_review"] = (
                f"{self.regulatory_review_hours} hours required"
            )
        if self.government_audit_hours:
            specialized["government_audit"] = (
                f"{self.government_audit_hours} hours required"
            )
        if self.fraud_hours_required:
            specialized["fraud_training"] = (
                f"{self.fraud_hours_required} hours required"
            )

        summary["specialized_requirements"] = (
            specialized if specialized else {"status": "None specified"}
        )

        # New licensee requirements
        if (
            self.new_licensee_hours_per_six_months
            or self.new_licensee_regulatory_review_required
        ):
            summary["new_licensee"] = {
                "hours_per_six_months": self.new_licensee_hours_per_six_months
                or "Not specified",
                "regulatory_review_required": (
                    "Yes" if self.new_licensee_regulatory_review_required else "No"
                ),
            }
        else:
            summary["new_licensee"] = {"status": "Same as regular licensees"}

        # Course requirements
        course_reqs = {}
        if self.interactive_courses_required is not None:
            course_reqs["interactive_required"] = (
                "Yes" if self.interactive_courses_required else "No"
            )
        if self.minimum_course_length_hours:
            course_reqs["minimum_course_length"] = (
                f"{self.minimum_course_length_hours} hours"
            )
        if self.ethics_exam_passing_score:
            course_reqs["ethics_exam_score"] = (
                f"{self.ethics_exam_passing_score}% required"
            )

        summary["course_requirements"] = (
            course_reqs
            if course_reqs
            else {"status": "Standard course requirements apply"}
        )

        return summary


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
