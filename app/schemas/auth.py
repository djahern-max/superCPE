# app/schemas/auth.py

from typing import Dict
from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl
from datetime import date, datetime
from typing import Optional, List
import re
from enum import Enum


class OnboardingStep(str, Enum):
    REGISTRATION = "registration"
    BASIC_INFO = "basic_info"
    LICENSE_INFO = "license_info"
    CONTACT_INFO = "contact_info"  # NEW: Add contact info step
    FIRM_INFO = "firm_info"  # NEW: Add firm info step
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
# ONBOARDING COMPONENT SCHEMAS (Reusable)
# =================


class OnboardingBasicInfo(BaseModel):
    """Step 2: Basic professional information"""

    primary_jurisdiction: Optional[USState] = Field(
        None, description="Primary state where you hold your CPA license"
    )
    license_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Your CPA license number (optional - helps with compliance tracking)",
    )


class OnboardingLicenseInfo(BaseModel):
    """Step 3: License details"""

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


class OnboardingContactInfo(BaseModel):
    """Step 4: Contact information for networking"""

    phone_number: Optional[str] = Field(None, max_length=20)
    linkedin_url: Optional[HttpUrl] = None
    twitter_handle: Optional[str] = Field(None, max_length=100)
    facebook_url: Optional[HttpUrl] = None
    instagram_handle: Optional[str] = Field(None, max_length=100)
    website_url: Optional[HttpUrl] = None

    @validator("phone_number")
    def validate_phone(cls, v):
        if v is None:
            return v
        digits_only = re.sub(r"\D", "", v)
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise ValueError("Phone number must be between 10-15 digits")
        return v

    @validator("twitter_handle", "instagram_handle")
    def validate_social_handle(cls, v):
        if v is None:
            return v
        handle = v.lstrip("@")
        if not re.match(r"^[A-Za-z0-9_]{1,50}$", handle):
            raise ValueError("Invalid social media handle format")
        return handle


class OnboardingFirmInfo(BaseModel):
    """Step 5: Firm/company information"""

    firm_name: Optional[str] = Field(None, max_length=200)
    firm_website: Optional[HttpUrl] = None
    firm_phone: Optional[str] = Field(None, max_length=20)
    firm_address_line1: Optional[str] = Field(None, max_length=200)
    firm_address_line2: Optional[str] = Field(None, max_length=200)
    firm_city: Optional[str] = Field(None, max_length=100)
    firm_state: Optional[USState] = None
    firm_zip_code: Optional[str] = Field(None, max_length=10)
    job_title: Optional[str] = Field(None, max_length=100)
    years_experience: Optional[int] = Field(None, ge=0, le=70)
    specializations: Optional[str] = Field(None, max_length=500)
    professional_certifications: Optional[str] = Field(None, max_length=500)

    @validator("firm_phone")
    def validate_firm_phone(cls, v):
        if v is None:
            return v
        digits_only = re.sub(r"\D", "", v)
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise ValueError("Firm phone number must be between 10-15 digits")
        return v

    @validator("firm_zip_code")
    def validate_zip_code(cls, v):
        if v is None:
            return v
        if not re.match(r"^\d{5}(-\d{4})?$", v):
            raise ValueError("Invalid ZIP code format")
        return v


class OnboardingPreferences(BaseModel):
    """Step 6: User preferences"""

    ce_broker_auto_sync: Optional[bool] = Field(
        False, description="Automatically sync CPE credits to CE Broker"
    )
    email_reminders: Optional[bool] = Field(
        True, description="Send email reminders for renewal deadlines"
    )
    newsletter_subscription: Optional[bool] = Field(
        False, description="Subscribe to CPE tips and industry updates"
    )
    marketing_emails: Optional[bool] = Field(
        False, description="Receive marketing communications"
    )
    public_profile: Optional[bool] = Field(
        False, description="Allow public profile visibility"
    )


class OnboardingComplete(BaseModel):
    """Final onboarding completion"""

    completed_at: datetime
    onboarding_step: OnboardingStep = OnboardingStep.COMPLETE


# =================
# UNIFIED USER SCHEMAS
# =================


class UserProfileUpdate(BaseModel):
    """SINGLE comprehensive user update schema - combines all previous update schemas"""

    # Basic info
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    primary_jurisdiction: Optional[USState] = None
    license_number: Optional[str] = Field(None, max_length=50)

    # License info
    license_issue_date: Optional[date] = None
    next_renewal_date: Optional[date] = None
    secondary_jurisdictions: Optional[List[USState]] = None

    # Contact info
    phone_number: Optional[str] = Field(None, max_length=20)
    linkedin_url: Optional[HttpUrl] = None
    twitter_handle: Optional[str] = Field(None, max_length=100)
    facebook_url: Optional[HttpUrl] = None
    instagram_handle: Optional[str] = Field(None, max_length=100)
    website_url: Optional[HttpUrl] = None

    # Firm info
    firm_name: Optional[str] = Field(None, max_length=200)
    firm_website: Optional[HttpUrl] = None
    firm_phone: Optional[str] = Field(None, max_length=20)
    firm_address_line1: Optional[str] = Field(None, max_length=200)
    firm_address_line2: Optional[str] = Field(None, max_length=200)
    firm_city: Optional[str] = Field(None, max_length=100)
    firm_state: Optional[USState] = None
    firm_zip_code: Optional[str] = Field(None, max_length=10)
    job_title: Optional[str] = Field(None, max_length=100)
    years_experience: Optional[int] = Field(None, ge=0, le=70)
    specializations: Optional[str] = Field(None, max_length=500)
    professional_certifications: Optional[str] = Field(None, max_length=500)

    # Preferences
    ce_broker_auto_sync: Optional[bool] = None
    email_reminders: Optional[bool] = None
    newsletter_subscription: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    public_profile: Optional[bool] = None


class UserProfile(BaseModel):
    """SINGLE comprehensive user profile response"""

    id: int
    email: EmailStr
    full_name: str

    # License info
    primary_jurisdiction: Optional[str]
    license_number: Optional[str]
    license_issue_date: Optional[date]
    next_renewal_date: Optional[date]
    secondary_jurisdictions: Optional[List[str]]

    # Contact info
    phone_number: Optional[str]
    linkedin_url: Optional[str]
    twitter_handle: Optional[str]
    facebook_url: Optional[str]
    instagram_handle: Optional[str]
    website_url: Optional[str]

    # Firm info
    firm_name: Optional[str]
    firm_website: Optional[str]
    firm_phone: Optional[str]
    firm_address_line1: Optional[str]
    firm_address_line2: Optional[str]
    firm_city: Optional[str]
    firm_state: Optional[str]
    firm_zip_code: Optional[str]
    job_title: Optional[str]
    years_experience: Optional[int]
    specializations: Optional[str]
    professional_certifications: Optional[str]

    # Preferences
    ce_broker_auto_sync: bool
    email_reminders: bool
    newsletter_subscription: bool
    marketing_emails: bool
    public_profile: bool

    # System fields
    onboarding_step: OnboardingStep
    created_at: datetime

    class Config:
        from_attributes = True


# =================
# ONBOARDING FLOW
# =================


class OnboardingStatus(BaseModel):
    current_step: OnboardingStep
    completed_steps: List[OnboardingStep]
    next_step: Optional[OnboardingStep]
    progress_percentage: int
    is_complete: bool
    can_skip_to_dashboard: bool


class OnboardingWelcome(BaseModel):
    user_name: str
    primary_jurisdiction: Optional[str]
    jurisdiction_info: Optional[Dict] = None
    quick_tips: List[str]
    estimated_completion_time: str = "3-5 minutes"  # Updated for more steps


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


# =================
# MARKETING & ANALYTICS
# =================


class UserProfileSummary(BaseModel):
    """Lightweight user profile for marketing lists"""

    id: int
    full_name: str
    email: EmailStr
    firm_name: Optional[str]
    primary_jurisdiction: str
    linkedin_url: Optional[str]
    marketing_emails: bool
    public_profile: bool
    created_at: datetime


class FirmDirectory(BaseModel):
    """Public firm directory entry"""

    firm_name: str
    firm_website: Optional[str]
    firm_city: Optional[str]
    firm_state: Optional[str]
    employee_count: int
    primary_services: List[str]
