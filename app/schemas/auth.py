# app/schemas/auth.py - Updated with jurisdiction support

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
    CONTACT_INFO = "contact_info"
    FIRM_INFO = "firm_info"
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
# CORE AUTH SCHEMAS
# =================


class UserRegistration(BaseModel):
    """User registration with configurable jurisdiction"""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    primary_jurisdiction: str = Field(
        default="NH",
        description="Primary state where you hold your CPA license (defaults to NH)",
    )

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v

    @validator("primary_jurisdiction")
    def validate_jurisdiction(cls, v):
        # Convert to uppercase and validate
        v = v.upper()
        if v not in [state.value for state in USState]:
            raise ValueError(f"Invalid jurisdiction. Must be a valid US state code.")
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
# USER PROFILE SCHEMAS
# =================


class UserProfile(BaseModel):
    """Complete user profile response"""

    # Core info
    id: int
    email: EmailStr
    full_name: str

    # License info
    primary_jurisdiction: Optional[str]
    license_number: Optional[str]
    license_issue_date: Optional[date] = None
    next_renewal_date: Optional[date] = None
    secondary_jurisdictions: Optional[List[str]] = None

    # Contact info
    phone_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    website_url: Optional[str] = None

    # Firm info
    firm_name: Optional[str] = None
    firm_website: Optional[str] = None
    firm_phone: Optional[str] = None
    firm_address_line1: Optional[str] = None
    firm_address_line2: Optional[str] = None
    firm_city: Optional[str] = None
    firm_state: Optional[str] = None
    firm_zip_code: Optional[str] = None
    job_title: Optional[str] = None
    years_experience: Optional[int] = None
    specializations: Optional[str] = None
    professional_certifications: Optional[str] = None

    # Preferences
    ce_broker_auto_sync: bool = False
    email_reminders: bool = True
    newsletter_subscription: bool = False
    marketing_emails: bool = False
    public_profile: bool = False

    # System fields
    onboarding_step: str = "registration"
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """User profile update schema"""

    # Basic info
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    primary_jurisdiction: Optional[str] = None
    license_number: Optional[str] = Field(None, max_length=50)

    # License info
    license_issue_date: Optional[date] = None
    next_renewal_date: Optional[date] = None
    secondary_jurisdictions: Optional[List[str]] = None

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
    firm_state: Optional[str] = None
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

    @validator("primary_jurisdiction")
    def validate_jurisdiction(cls, v):
        if v is None:
            return v
        v = v.upper()
        if v not in [state.value for state in USState]:
            raise ValueError(f"Invalid jurisdiction. Must be a valid US state code.")
        return v


# =================
# API RESPONSE SCHEMAS
# =================


class RegistrationResponse(BaseModel):
    message: str
    user_id: int
    next_step: str
    token: Token


class LoginResponse(BaseModel):
    message: str
    token: Token
    user: UserProfile
    onboarding_required: bool


# =================
# ONBOARDING SCHEMAS
# =================


class OnboardingBasicInfo(BaseModel):
    """Step 2: Basic professional information"""

    primary_jurisdiction: Optional[str] = Field(
        None, description="Primary state where you hold your CPA license"
    )
    license_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Your CPA license number (optional)",
    )

    @validator("primary_jurisdiction")
    def validate_jurisdiction(cls, v):
        if v is None:
            return v
        v = v.upper()
        if v not in [state.value for state in USState]:
            raise ValueError(f"Invalid jurisdiction. Must be a valid US state code.")
        return v


class OnboardingStatus(BaseModel):
    current_step: str
    completed_steps: List[str]
    next_step: Optional[str]
    progress_percentage: int
    is_complete: bool
    can_skip_to_dashboard: bool


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
