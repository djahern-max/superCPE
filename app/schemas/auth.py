# app/schemas/auth.py

from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
from typing import Optional, List, Dict
from enum import Enum


class OnboardingStep(str, Enum):
    REGISTRATION = "registration"
    BASIC_INFO = "basic_info"
    LICENSE_INFO = "license_info"
    PREFERENCES = "preferences"
    COMPLETE = "complete"


class USState(str, Enum):
    """US States and territories where CPAs can be licensed"""

    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    DC = "DC"
    FL = "FL"
    GA = "GA"
    GU = "GU"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    PR = "PR"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VI = "VI"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"


# =================
# REGISTRATION & LOGIN
# =================


class UserRegistration(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


# =================
# ONBOARDING STEPS
# =================


class OnboardingBasicInfo(BaseModel):
    """Step 2: Basic professional information (optional)"""

    primary_jurisdiction: Optional[USState] = Field(
        None, description="Primary state where you hold your CPA license"
    )
    license_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Your CPA license number (optional - helps with compliance tracking)",
    )


class OnboardingLicenseInfo(BaseModel):
    """Step 3: License details (all optional)"""

    license_issue_date: Optional[date] = Field(
        None, description="When was your license first issued?"
    )
    next_renewal_date: Optional[date] = Field(
        None, description="When is your next renewal deadline?"
    )
    secondary_jurisdictions: Optional[List[USState]] = Field(
        None, description="Other states where you hold licenses"
    )

    @validator("license_issue_date")
    def validate_license_issue_date(cls, v):
        if v and v > date.today():
            raise ValueError("License issue date cannot be in the future")
        if v and v < date(1950, 1, 1):
            raise ValueError("License issue date seems too old")
        return v

    @validator("next_renewal_date")
    def validate_next_renewal_date(cls, v):
        if v and v < date.today():
            raise ValueError("Next renewal date should be in the future")
        return v


class OnboardingPreferences(BaseModel):
    """Step 4: User preferences (all optional)"""

    ce_broker_auto_sync: Optional[bool] = Field(
        False, description="Automatically sync CPE credits to CE Broker"
    )
    email_reminders: Optional[bool] = Field(
        True, description="Send email reminders for renewal deadlines"
    )
    newsletter_subscription: Optional[bool] = Field(
        False, description="Subscribe to CPE tips and industry updates"
    )


class OnboardingComplete(BaseModel):
    """Final onboarding completion"""

    completed_at: datetime
    onboarding_step: OnboardingStep = OnboardingStep.COMPLETE


# =================
# USER PROFILE
# =================


class UserProfile(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    primary_jurisdiction: Optional[str]
    license_number: Optional[str]
    license_issue_date: Optional[date]
    next_renewal_date: Optional[date]
    secondary_jurisdictions: Optional[List[str]]
    ce_broker_auto_sync: bool
    onboarding_step: OnboardingStep
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    primary_jurisdiction: Optional[USState] = None
    license_number: Optional[str] = Field(None, max_length=50)
    license_issue_date: Optional[date] = None
    next_renewal_date: Optional[date] = None
    secondary_jurisdictions: Optional[List[USState]] = None
    ce_broker_auto_sync: Optional[bool] = None


# =================
# ONBOARDING FLOW
# =================


class OnboardingStatus(BaseModel):
    current_step: OnboardingStep
    completed_steps: List[OnboardingStep]
    next_step: Optional[OnboardingStep]
    progress_percentage: int
    is_complete: bool
    can_skip_to_dashboard: bool  # After basic info, they can skip to dashboard


class OnboardingWelcome(BaseModel):
    """Welcome message with jurisdiction-specific info"""

    user_name: str
    primary_jurisdiction: Optional[str]
    jurisdiction_info: Optional[Dict] = None  # CPE requirements for their state
    quick_tips: List[str]
    estimated_completion_time: str = "2-3 minutes"


# =================
# PASSWORD MANAGEMENT
# =================


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @validator("new_password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @validator("new_password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


# =================
# API RESPONSES
# =================


class RegistrationResponse(BaseModel):
    message: str
    user_id: int
    next_step: OnboardingStep
    token: Token


class LoginResponse(BaseModel):
    message: str
    token: Token
    user: UserProfile
    onboarding_required: bool


class OnboardingStepResponse(BaseModel):
    message: str
    current_step: OnboardingStep
    next_step: Optional[OnboardingStep]
    progress_percentage: int
    can_skip: bool = True
    jurisdiction_updated: bool = False
