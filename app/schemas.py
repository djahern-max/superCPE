from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from enum import Enum

# =================
# ENUMS
# =================

class DeliveryMethod(str, Enum):
    QAS_SELF_STUDY = "QAS Self-Study"
    GROUP_LIVE = "Group Live"
    GROUP_INTERNET = "Group Internet"
    NANO_LEARNING = "Nano Learning"

class FieldOfStudy(str, Enum):
    ACCOUNTING = "Accounting"
    AUDITING = "Auditing"
    TAXATION = "Taxes"
    ECONOMICS = "Economics"
    FRAUD = "Auditing - Fraud"
    PERSONNEL_HR = "Personnel / Human Resources"
    COMMUNICATIONS = "Communications and Marketing"

class ReportingPeriodType(str, Enum):
    ANNUAL = "annual"
    BIENNIAL = "biennial"
    TRIENNIAL = "triennial"

class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    DEFICIENT = "deficient"
    APPROACHING_DEADLINE = "approaching_deadline"
    UNKNOWN = "unknown"

# =================
# CPE CERTIFICATE EXTRACTION
# =================

class CPECertificateData(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=500)
    course_code: Optional[str] = Field(None, max_length=100)
    provider_name: str = Field(..., min_length=1, max_length=200)
    field_of_study: Optional[FieldOfStudy] = None
    cpe_credits: Decimal = Field(..., gt=0, le=50)  # Reasonable limits
    completion_date: date
    delivery_method: Optional[DeliveryMethod] = None
    nasba_sponsor_id: Optional[str] = Field(None, max_length=20)
    is_ethics: bool = False
    
    @validator('completion_date')
    def validate_completion_date(cls, v):
        if v > date.today():
            raise ValueError('Completion date cannot be in the future')
        if v < date(1990, 1, 1):
            raise ValueError('Completion date seems too old')
        return v

class CPERecordCreate(BaseModel):
    course_name: str
    course_code: Optional[str] = None
    provider_name: str
    field_of_study: Optional[str] = None
    cpe_credits: Decimal
    completion_date: date
    delivery_method: Optional[str] = None
    nasba_sponsor_id: Optional[str] = None
    is_ethics: bool = False
    certificate_filename: Optional[str] = None

class CPERecordResponse(BaseModel):
    id: int
    user_id: int
    course_name: str
    course_code: Optional[str]
    provider_name: str
    field_of_study: Optional[str]
    cpe_credits: Decimal
    completion_date: date
    is_ethics: bool
    delivery_method: Optional[str]
    nasba_sponsor_id: Optional[str]
    nasba_registry_verified: bool
    extracted_at: datetime
    extraction_confidence: Optional[float]
    ce_broker_submitted: bool
    
    class Config:
        from_attributes = True

class CPEProcessingResult(BaseModel):
    id: Optional[int] = None
    extracted_data: CPECertificateData
    status: str
    message: Optional[str] = None
    confidence_score: Optional[float] = None
    validation_errors: Optional[List[str]] = None

# =================
# COMPLIANCE TRACKING
# =================

class ComplianceCheck(BaseModel):
    jurisdiction_code: str = Field(..., min_length=2, max_length=2)
    reporting_period_start: date
    reporting_period_end: date
    
class ComplianceStatusData(BaseModel):
    is_compliant: bool
    total_hours_completed: Decimal
    total_hours_required: int
    hours_needed: Decimal
    ethics_hours_completed: Decimal
    ethics_hours_required: int
    ethics_hours_needed: Decimal
    next_renewal_date: Optional[date]
    days_until_renewal: Optional[int]
    compliance_percentage: float
    
class ComplianceSummary(BaseModel):
    user_id: int
    primary_jurisdiction: str
    compliance_status: ComplianceStatusData
    secondary_jurisdictions: Optional[List[ComplianceStatusData]] = []
    recent_courses: List[CPERecordResponse]
    recommendations: List[str]
    
# =================
# JURISDICTION MANAGEMENT
# =================

class CPAJurisdictionBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=2)
    name: str
    general_hours_required: int = Field(..., ge=0, le=200)
    ethics_hours_required: int = Field(default=0, ge=0, le=50)
    reporting_period_type: ReportingPeriodType
    reporting_period_months: int = Field(..., gt=0, le=36)

class CPAJurisdictionCreate(CPAJurisdictionBase):
    board_name: Optional[str] = None
    board_website: Optional[str] = None
    renewal_date_pattern: Optional[str] = None
    reporting_period_description: Optional[str] = None
    ce_broker_required: bool = False

class CPAJurisdictionResponse(CPAJurisdictionBase):
    board_name: Optional[str]
    board_website: Optional[str]
    renewal_date_pattern: Optional[str]
    reporting_period_description: Optional[str]
    live_hours_required: Optional[int]
    carry_forward_max_hours: Optional[int]
    ce_broker_required: bool
    nasba_last_updated: Optional[date]
    
    class Config:
        from_attributes = True

class CPAJurisdictionUpdate(BaseModel):
    name: Optional[str] = None
    general_hours_required: Optional[int] = Field(None, ge=0, le=200)
    ethics_hours_required: Optional[int] = Field(None, ge=0, le=50)
    reporting_period_type: Optional[ReportingPeriodType] = None
    board_website: Optional[str] = None
    ce_broker_required: Optional[bool] = None

# =================
# USER MANAGEMENT
# =================

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    primary_jurisdiction: str = Field(default="NH", min_length=2, max_length=2)

class UserCreate(UserBase):
    secondary_jurisdictions: Optional[List[str]] = None
    license_issue_date: Optional[date] = None
    next_renewal_date: Optional[date] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    primary_jurisdiction: Optional[str] = Field(None, min_length=2, max_length=2)
    secondary_jurisdictions: Optional[List[str]] = None
    next_renewal_date: Optional[date] = None
    ce_broker_auto_sync: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    secondary_jurisdictions: Optional[str]
    license_issue_date: Optional[date]
    next_renewal_date: Optional[date]
    ce_broker_auto_sync: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# =================
# NASBA PROVIDER SCHEMAS
# =================

class NASBAProviderBase(BaseModel):
    sponsor_id: str = Field(..., max_length=20)
    sponsor_name: str = Field(..., min_length=1, max_length=200)

class NASBAProviderCreate(NASBAProviderBase):
    registry_status: Optional[str] = "Active"
    website: Optional[str] = None
    group_live: bool = False
    group_internet: bool = False
    self_study: bool = False

class NASBAProviderResponse(NASBAProviderBase):
    id: int
    registry_status: Optional[str]
    website: Optional[str]
    group_live: bool
    group_internet: bool
    self_study: bool
    last_verified: Optional[date]
    
    class Config:
        from_attributes = True

# =================
# CE BROKER INTEGRATION
# =================

class CEBrokerSubmission(BaseModel):
    course_name: str
    provider_name: str
    hours: Decimal
    completion_date: date
    subject_area: Optional[str] = None
    certificate_url: Optional[str] = None

class CEBrokerResponse(BaseModel):
    submission_id: Optional[str]
    status: str  # "success", "pending", "failed"
    message: Optional[str]
    submitted_at: datetime

# =================
# ANALYTICS & REPORTING
# =================

class CPEAnalytics(BaseModel):
    total_courses: int
    total_hours: Decimal
    ethics_hours: Decimal
    hours_by_field: Dict[str, Decimal]
    hours_by_provider: Dict[str, Decimal]
    hours_by_month: Dict[str, Decimal]
    average_course_length: Decimal
    compliance_rate: float

class JurisdictionStats(BaseModel):
    jurisdiction_code: str
    jurisdiction_name: str
    total_users: int
    compliant_users: int
    average_completion_rate: float
    most_popular_providers: List[Dict[str, Any]]

# =================
# DASHBOARD SCHEMAS
# =================

class DashboardData(BaseModel):
    user: UserResponse
    compliance_summary: ComplianceSummary
    recent_activity: List[CPERecordResponse]
    upcoming_deadlines: List[Dict[str, Any]]
    quick_stats: CPEAnalytics
    recommendations: List[str]

class CPEPlanningData(BaseModel):
    hours_needed: Decimal
    ethics_hours_needed: Decimal
    days_remaining: int
    recommended_pace: str
    suggested_courses: List[Dict[str, Any]]
    deadline_alerts: List[str]

# =================
# API RESPONSES
# =================

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database_status: str = "connected"
    nasba_sync_status: str = "unknown"

class BulkOperationResponse(BaseModel):
    total_processed: int
    successful: int
    failed: int
    errors: List[str]
    
class DataSyncResponse(BaseModel):
    sync_id: int
    status: str
    records_processed: int
    records_updated: int
    started_at: datetime
    completed_at: Optional[datetime] = None
