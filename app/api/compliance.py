# app/api/compliance.py - Enhanced UX version

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from app.core.database import get_db
from app.models import CPAJurisdiction, User, CPERecord, ComplianceRecord
from app.api.auth import get_current_user

router = APIRouter(
    prefix="/api/compliance",
    tags=["Compliance Checker"],
)


# Request Models
class SetupLicenseInfo(BaseModel):
    """One-time license setup for new users"""

    jurisdiction_code: str = Field(
        ..., description="2-letter state code (e.g., NH, CA)"
    )
    license_issue_date: date = Field(
        ..., description="Date when license was first issued"
    )
    license_number: Optional[str] = Field(
        None, description="License number (optional for privacy)"
    )


class ManualComplianceCheck(BaseModel):
    """For advanced users who want to check different scenarios"""

    jurisdiction_code: Optional[str] = None
    license_issue_date: Optional[date] = None
    check_date: Optional[date] = None


# Response Models
class UserSetupStatus(BaseModel):
    """Shows what user has configured"""

    has_license_info: bool
    primary_jurisdiction: Optional[str]
    license_issue_date: Optional[date]
    license_number: Optional[str]
    has_cpe_records: bool
    total_cpe_records: int
    compliance_ready: bool


class QuickComplianceStatus(BaseModel):
    """Lightweight compliance status for dashboard"""

    is_compliant: bool
    status: str  # "Compliant", "At Risk", "Non-Compliant", "Setup Required"
    total_hours_required: int
    total_hours_completed: float
    compliance_percentage: float
    days_until_renewal: Optional[int]
    next_action: str


class ReportingPeriod(BaseModel):
    period_start: date
    period_end: date
    period_type: str
    renewal_date: date
    days_remaining: int


class DetailedComplianceReport(BaseModel):
    user_info: Dict[str, Any]
    jurisdiction: Dict[str, Any]
    current_period: ReportingPeriod
    requirements: List[Dict[str, Any]]
    overall_status: QuickComplianceStatus
    recommendations: List[str]
    cpe_breakdown: Dict[str, float]


# Helper Functions (simplified versions from previous code)
def calculate_current_period(
    jurisdiction: CPAJurisdiction, license_date: date, check_date: date
) -> ReportingPeriod:
    """Calculate current reporting period - simplified version"""

    period_months = jurisdiction.reporting_period_months or 24

    # Calculate which period we're in
    months_since_license = relativedelta(check_date, license_date).months + (
        relativedelta(check_date, license_date).years * 12
    )

    current_period_num = (months_since_license // period_months) + 1

    # Calculate period boundaries
    period_start = license_date + relativedelta(
        months=(current_period_num - 1) * period_months
    )
    period_end = period_start + relativedelta(months=period_months) - timedelta(days=1)

    # Simple renewal date calculation (can be enhanced per state)
    renewal_date = period_end
    days_remaining = (renewal_date - check_date).days

    return ReportingPeriod(
        period_start=period_start,
        period_end=period_end,
        period_type=jurisdiction.reporting_period_type or "biennial",
        renewal_date=renewal_date,
        days_remaining=max(0, days_remaining),
    )


def calculate_nh_compliance_detailed(
    jurisdiction: CPAJurisdiction,
    cpe_records: List[CPERecord],
    current_period: ReportingPeriod,
    license_date: date,
) -> Dict[str, Any]:
    """
    Detailed NH compliance calculation with annual requirements

    NH Requirements:
    - 120 hours over 3 years (triennial)
    - 4 ethics hours over 3 years
    - 20 hours minimum each year
    - Renewal groups by last name (A-F, G-M, N-Z)
    """

    # Filter records for current triennial period
    period_records = [
        record
        for record in cpe_records
        if current_period.period_start <= record.completion_date <= date.today()
    ]

    # Calculate total hours
    total_hours = sum(record.cpe_credits or 0 for record in period_records)

    # Calculate ethics hours (look for ethics-related fields of study)
    ethics_keywords = [
        "ethics",
        "professional responsibility",
        "professional conduct",
        "conduct",
        "responsibility",
    ]
    ethics_hours = sum(
        record.cpe_credits or 0
        for record in period_records
        if record.field_of_study
        and any(keyword in record.field_of_study.lower() for keyword in ethics_keywords)
    )

    # Check annual requirements (20 hours minimum each year)
    annual_compliance = []
    current_year = current_period.period_start.year
    end_year = min(current_period.period_end.year, date.today().year)

    for year in range(current_year, end_year + 1):
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        # For current year, only count up to today
        if year == date.today().year:
            year_end = date.today()

        year_records = [
            record
            for record in period_records
            if year_start <= record.completion_date <= year_end
        ]

        year_hours = sum(record.cpe_credits or 0 for record in year_records)

        annual_compliance.append(
            {
                "year": year,
                "hours_completed": year_hours,
                "hours_required": 20,
                "is_compliant": year_hours >= 20,
                "deficit": max(0, 20 - year_hours),
                "records_count": len(year_records),
            }
        )

    # Overall compliance checks
    total_compliant = total_hours >= 120
    ethics_compliant = ethics_hours >= 4
    annual_compliant = all(year["is_compliant"] for year in annual_compliance)

    overall_compliant = total_compliant and ethics_compliant and annual_compliant

    # Calculate deficits
    deficits = []
    recommendations = []

    if not total_compliant:
        deficit = 120 - total_hours
        deficits.append(f"Need {deficit:.1f} more total hours")
        recommendations.append(
            f"Upload certificates for {deficit:.1f} additional CPE hours"
        )

    if not ethics_compliant:
        ethics_deficit = 4 - ethics_hours
        deficits.append(f"Need {ethics_deficit:.1f} more ethics hours")
        recommendations.append(
            f"Complete {ethics_deficit:.1f} hours of ethics/professional responsibility training"
        )

    if not annual_compliant:
        for year_data in annual_compliance:
            if not year_data["is_compliant"]:
                deficits.append(
                    f"Need {year_data['deficit']:.1f} more hours for {year_data['year']}"
                )
                recommendations.append(
                    f"Upload certificates from {year_data['year']} to meet 20-hour minimum"
                )

    # Determine status
    if overall_compliant:
        status = "Compliant"
    elif total_hours >= 96:  # 80% of total requirement
        status = "At Risk"
    else:
        status = "Non-Compliant"

    return {
        "overall_compliant": overall_compliant,
        "status": status,
        "total_hours": total_hours,
        "ethics_hours": ethics_hours,
        "annual_compliance": annual_compliance,
        "deficits": deficits,
        "recommendations": recommendations,
        "compliance_breakdown": {
            "total_requirement_met": total_compliant,
            "ethics_requirement_met": ethics_compliant,
            "annual_requirements_met": annual_compliant,
        },
    }


def calculate_compliance_status_enhanced(
    jurisdiction: CPAJurisdiction,
    cpe_records: List[CPERecord],
    current_period: ReportingPeriod,
    license_date: date,
) -> QuickComplianceStatus:
    """Enhanced compliance calculation that handles state-specific rules"""

    if jurisdiction.code == "NH":
        # Use detailed NH logic
        nh_result = calculate_nh_compliance_detailed(
            jurisdiction, cpe_records, current_period, license_date
        )

        # Build next action message
        if nh_result["overall_compliant"]:
            next_action = (
                f"✅ You're compliant! Next renewal: {current_period.renewal_date}"
            )
        else:
            # Prioritize the most critical deficits
            if nh_result["deficits"]:
                next_action = "❌ " + nh_result["deficits"][0]
            else:
                next_action = "Review your CPE records for compliance issues"

        return QuickComplianceStatus(
            is_compliant=nh_result["overall_compliant"],
            status=nh_result["status"],
            total_hours_required=120,
            total_hours_completed=nh_result["total_hours"],
            compliance_percentage=min(100, (nh_result["total_hours"] / 120) * 100),
            days_until_renewal=current_period.days_remaining,
            next_action=next_action,
        )

    else:
        # Fall back to simpler logic for other states
        total_hours = sum(
            record.cpe_credits or 0
            for record in cpe_records
            if current_period.period_start
            <= record.completion_date
            <= current_period.period_end
        )

        hours_required = jurisdiction.general_hours_required or 0
        is_compliant = total_hours >= hours_required
        compliance_percentage = (
            (total_hours / hours_required * 100) if hours_required > 0 else 100
        )

        if is_compliant:
            status = "Compliant"
            next_action = (
                f"You're compliant! Next renewal: {current_period.renewal_date}"
            )
        elif compliance_percentage >= 80:
            status = "At Risk"
            needed = hours_required - total_hours
            next_action = (
                f"Complete {needed:.1f} more hours before {current_period.renewal_date}"
            )
        else:
            status = "Non-Compliant"
            needed = hours_required - total_hours
            next_action = f"Upload {needed:.1f} hours of CPE immediately"

        return QuickComplianceStatus(
            is_compliant=is_compliant,
            status=status,
            total_hours_required=hours_required,
            total_hours_completed=total_hours,
            compliance_percentage=min(100, compliance_percentage),
            days_until_renewal=current_period.days_remaining,
            next_action=next_action,
        )


@router.get("/nh-detailed", response_model=Dict[str, Any])
async def get_nh_detailed_compliance(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Detailed NH compliance report with year-by-year breakdown
    Shows annual requirements, ethics hours, and specific deficits
    """

    if current_user.primary_jurisdiction != "NH":
        raise HTTPException(
            status_code=400,
            detail="This endpoint is specifically for New Hampshire licensees",
        )

    if not current_user.license_issue_date:
        raise HTTPException(
            status_code=400, detail="Please complete license setup first"
        )

    # Get jurisdiction and records
    jurisdiction = (
        db.query(CPAJurisdiction).filter(CPAJurisdiction.code == "NH").first()
    )

    cpe_records = db.query(CPERecord).filter(CPERecord.user_id == current_user.id).all()

    # Calculate current period
    current_period = calculate_current_period(
        jurisdiction, current_user.license_issue_date, date.today()
    )

    # Get detailed NH compliance
    nh_details = calculate_nh_compliance_detailed(
        jurisdiction, cpe_records, current_period, current_user.license_issue_date
    )

    return {
        "user_info": {
            "license_date": current_user.license_issue_date,
            "current_period": {
                "start": current_period.period_start,
                "end": current_period.period_end,
                "days_remaining": current_period.days_remaining,
            },
        },
        "nh_requirements": {
            "total_hours_required": 120,
            "ethics_hours_required": 4,
            "annual_minimum": 20,
        },
        "compliance_status": nh_details,
        "next_steps": nh_details["recommendations"],
    }


@router.get("/setup-status", response_model=UserSetupStatus)
async def get_user_setup_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Check what information the user has provided for compliance tracking
    This helps the frontend decide what to show/prompt for
    """

    # Check if user has license info
    has_license_info = bool(
        current_user.primary_jurisdiction and current_user.license_issue_date
    )

    # Count CPE records
    cpe_count = (
        db.query(func.count(CPERecord.id))
        .filter(CPERecord.user_id == current_user.id)
        .scalar()
        or 0
    )

    return UserSetupStatus(
        has_license_info=has_license_info,
        primary_jurisdiction=current_user.primary_jurisdiction,
        license_issue_date=current_user.license_issue_date,
        license_number=current_user.license_number,
        has_cpe_records=cpe_count > 0,
        total_cpe_records=cpe_count,
        compliance_ready=has_license_info and cpe_count > 0,
    )


@router.post("/setup")
async def setup_license_info(
    setup_data: SetupLicenseInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    One-time license setup for compliance tracking
    Called when user first wants to use compliance features
    """

    # Validate jurisdiction
    jurisdiction = (
        db.query(CPAJurisdiction)
        .filter(CPAJurisdiction.code == setup_data.jurisdiction_code.upper())
        .first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=404,
            detail=f"Jurisdiction {setup_data.jurisdiction_code} not found",
        )

    # Update user profile
    current_user.primary_jurisdiction = setup_data.jurisdiction_code.upper()
    current_user.license_issue_date = setup_data.license_issue_date
    current_user.license_number = setup_data.license_number
    current_user.updated_at = datetime.utcnow()

    db.commit()

    return {
        "message": "License information saved successfully! Compliance tracking is now enabled.",
        "jurisdiction": jurisdiction.name,
        "license_date": setup_data.license_issue_date,
        "next_step": "Your dashboard will now show compliance status",
        "setup_complete": True,
    }


@router.get("/dashboard", response_model=QuickComplianceStatus)
async def get_dashboard_compliance(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Quick compliance status for user dashboard
    Returns lightweight status info without heavy calculations
    """

    # Check if user has setup license info
    if not current_user.primary_jurisdiction or not current_user.license_issue_date:
        return QuickComplianceStatus(
            is_compliant=False,
            status="Setup Required",
            total_hours_required=0,
            total_hours_completed=0,
            compliance_percentage=0,
            days_until_renewal=None,
            next_action="Complete your license setup to enable compliance tracking",
        )

    # Get jurisdiction
    jurisdiction = (
        db.query(CPAJurisdiction)
        .filter(CPAJurisdiction.code == current_user.primary_jurisdiction)
        .first()
    )

    if not jurisdiction:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")

    # Get CPE records
    cpe_records = db.query(CPERecord).filter(CPERecord.user_id == current_user.id).all()

    # Calculate current period and compliance
    current_period = calculate_current_period(
        jurisdiction, current_user.license_issue_date, date.today()
    )

    return calculate_compliance_status(jurisdiction, cpe_records, current_period)


@router.get("/detailed-report", response_model=DetailedComplianceReport)
async def get_detailed_compliance_report(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Detailed compliance report with full breakdown
    Only available after user has completed setup
    """

    # Require setup
    if not current_user.primary_jurisdiction or not current_user.license_issue_date:
        raise HTTPException(
            status_code=400,
            detail="Please complete license setup first using /api/compliance/setup",
        )

    # Get jurisdiction
    jurisdiction = (
        db.query(CPAJurisdiction)
        .filter(CPAJurisdiction.code == current_user.primary_jurisdiction)
        .first()
    )

    # Get CPE records
    cpe_records = db.query(CPERecord).filter(CPERecord.user_id == current_user.id).all()

    # Calculate current period
    current_period = calculate_current_period(
        jurisdiction, current_user.license_issue_date, date.today()
    )

    # Get compliance status
    status = calculate_compliance_status_enhanced(
        jurisdiction, cpe_records, current_period, current_user.license_issue_date
    )

    # Calculate detailed breakdown
    period_records = [
        r
        for r in cpe_records
        if current_period.period_start <= r.completion_date <= current_period.period_end
    ]

    cpe_breakdown = {
        "total_hours": sum(r.cpe_credits or 0 for r in period_records),
        "ethics_hours": sum(
            r.cpe_credits or 0
            for r in period_records
            if r.field_of_study and "ethics" in r.field_of_study.lower()
        ),
        "technical_hours": sum(
            r.cpe_credits or 0
            for r in period_records
            if r.field_of_study
            and any(
                term in r.field_of_study.lower()
                for term in ["tax", "accounting", "audit"]
            )
        ),
        "total_certificates": len(period_records),
    }

    # Generate recommendations
    recommendations = []
    if not status.is_compliant:
        deficit = jurisdiction.general_hours_required - cpe_breakdown["total_hours"]
        recommendations.append(
            f"Upload {deficit:.1f} more CPE hours to become compliant"
        )

        if jurisdiction.ethics_hours_required:
            ethics_deficit = (
                jurisdiction.ethics_hours_required - cpe_breakdown["ethics_hours"]
            )
            if ethics_deficit > 0:
                recommendations.append(
                    f"Complete {ethics_deficit:.1f} more ethics hours"
                )

    return DetailedComplianceReport(
        user_info={
            "jurisdiction": jurisdiction.name,
            "license_date": current_user.license_issue_date,
            "license_number": current_user.license_number,
        },
        jurisdiction={
            "code": jurisdiction.code,
            "name": jurisdiction.name,
            "general_hours_required": jurisdiction.general_hours_required,
            "ethics_hours_required": jurisdiction.ethics_hours_required,
            "reporting_period_type": jurisdiction.reporting_period_type,
        },
        current_period=current_period,
        requirements=[
            {
                "type": "General CPE",
                "required": jurisdiction.general_hours_required,
                "completed": cpe_breakdown["total_hours"],
                "compliant": cpe_breakdown["total_hours"]
                >= (jurisdiction.general_hours_required or 0),
            }
        ],
        overall_status=status,
        recommendations=recommendations,
        cpe_breakdown=cpe_breakdown,
    )


@router.post("/manual-check", response_model=QuickComplianceStatus)
async def manual_compliance_check(
    check_data: ManualComplianceCheck,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manual compliance check for advanced users
    Allows checking different scenarios or past periods
    """

    # Use provided data or fall back to user profile
    jurisdiction_code = (
        check_data.jurisdiction_code or current_user.primary_jurisdiction
    )
    license_date = check_data.license_issue_date or current_user.license_issue_date
    check_date = check_data.check_date or date.today()

    if not jurisdiction_code or not license_date:
        raise HTTPException(
            status_code=400,
            detail="Please provide jurisdiction and license date, or complete your profile setup",
        )

    jurisdiction = (
        db.query(CPAJurisdiction)
        .filter(CPAJurisdiction.code == jurisdiction_code.upper())
        .first()
    )

    if not jurisdiction:
        raise HTTPException(
            status_code=404, detail=f"Jurisdiction {jurisdiction_code} not found"
        )

    # Get CPE records
    cpe_records = db.query(CPERecord).filter(CPERecord.user_id == current_user.id).all()

    # Calculate compliance for specified scenario
    current_period = calculate_current_period(jurisdiction, license_date, check_date)
    return calculate_compliance_status_enhanced(
        jurisdiction, cpe_records, current_period, current_user.license_issue_date
    )


@router.put("/update-license")
async def update_license_info(
    update_data: SetupLicenseInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update existing license information"""

    jurisdiction = (
        db.query(CPAJurisdiction)
        .filter(CPAJurisdiction.code == update_data.jurisdiction_code.upper())
        .first()
    )

    if not jurisdiction:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")

    current_user.primary_jurisdiction = update_data.jurisdiction_code.upper()
    current_user.license_issue_date = update_data.license_issue_date
    current_user.license_number = update_data.license_number
    current_user.updated_at = datetime.utcnow()

    db.commit()

    return {
        "message": "License information updated successfully",
        "jurisdiction": jurisdiction.name,
        "license_date": update_data.license_issue_date,
    }
