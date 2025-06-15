from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    Boolean,
    Float,
    ForeignKey,
    func,
)
from sqlalchemy.types import DECIMAL
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, date
from uuid import uuid4

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    license_number = Column(String)
    primary_jurisdiction = Column(String(2), default="NH")
    secondary_jurisdictions = Column(String)
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String, nullable=True)

    # CPA-specific fields
    license_issue_date = Column(Date)
    next_renewal_date = Column(Date)

    # Contact Information for Marketing
    phone_number = Column(String(20))  # Professional phone number
    linkedin_url = Column(String(500))  # LinkedIn profile URL
    twitter_handle = Column(String(100))  # Twitter handle (without @)
    facebook_url = Column(String(500))  # Facebook profile/page URL
    instagram_handle = Column(String(100))  # Instagram handle (without @)
    website_url = Column(String(500))  # Personal/professional website

    # Firm Information
    firm_name = Column(String(200))  # Name of accounting firm/company
    firm_website = Column(String(500))  # Firm's website URL
    firm_phone = Column(String(20))  # Firm's main phone number
    firm_address_line1 = Column(String(200))  # Firm street address
    firm_address_line2 = Column(String(200))  # Firm address line 2 (suite, etc.)
    firm_city = Column(String(100))  # Firm city
    firm_state = Column(String(2))  # Firm state code
    firm_zip_code = Column(String(10))  # Firm ZIP code
    job_title = Column(
        String(100)
    )  # Job title at firm (Partner, Senior Associate, etc.)

    # Professional Details
    years_experience = Column(Integer)  # Years of CPA experience
    specializations = Column(
        String(500)
    )  # Comma-separated specialties (Tax, Audit, etc.)
    professional_certifications = Column(String(500))  # Other certs (CFA, CIA, etc.)

    # CE Broker integration
    ce_broker_id = Column(String)
    ce_broker_auto_sync = Column(Boolean, default=False)

    # Onboarding tracking
    onboarding_step = Column(String, default="registration")

    # User preferences
    email_reminders = Column(Boolean, default=True)
    newsletter_subscription = Column(Boolean, default=False)
    marketing_emails = Column(
        Boolean, default=False
    )  # Marketing communications consent
    public_profile = Column(Boolean, default=False)  # Allow public profile visibility

    # Authentication
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cpe_records = relationship("CPERecord", back_populates="user")
    compliance_records = relationship("ComplianceRecord", back_populates="user")


# =================
# CPE TRACKING MODELS
# =================


class CPERecord(Base):
    __tablename__ = "cpe_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    # Course Information
    course_name = Column(String, nullable=False)
    course_code = Column(String)
    provider_name = Column(String, nullable=False)
    field_of_study = Column(String)  # Accounting, Auditing, Taxation, etc.

    # CPE Details
    cpe_credits = Column(DECIMAL(5, 2), nullable=False)
    is_ethics = Column(Boolean, default=False)
    delivery_method = Column(String)  # QAS Self-Study, Group Live, Group Internet, etc.

    # NASBA Integration
    nasba_sponsor_id = Column(String)  # TX Sponsor #009930, etc.
    nasba_registry_verified = Column(Boolean, default=False)

    # Dates
    completion_date = Column(Date, nullable=False)
    reporting_period_start = Column(Date)  # Which reporting period this applies to
    reporting_period_end = Column(Date)

    # Original filename (for user reference)
    original_filename = Column(String)  # User's original PDF name
    # Organized storage filename (when they upgrade to paid)
    certificate_filename = Column(String)  # Smart filename for storage
    certificate_url = Column(String)  # Digital Ocean URL (paid feature)
    certificate_hash = Column(String)  # Duplicate detection
    # Business model support
    is_stored = Column(Boolean, default=False)  # Has user paid for storage?
    storage_tier = Column(String)  # "free", "premium", "enterprise"

    # Processing Metadata
    extracted_at = Column(DateTime, default=datetime.utcnow)
    extraction_confidence = Column(Float)  # AI confidence score
    manually_verified = Column(Boolean, default=False)

    # CE Broker Integration
    ce_broker_submitted = Column(Boolean, default=False)
    ce_broker_submission_date = Column(DateTime)
    ce_broker_response = Column(JSONB)  # Store CE Broker API response

    # Relationships
    user = relationship("User", back_populates="cpe_records")


class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    jurisdiction_code = Column(String(2), ForeignKey("cpa_jurisdictions.code"))

    # Reporting Period
    reporting_period_start = Column(Date, nullable=False)
    reporting_period_end = Column(Date, nullable=False)

    # Hours Tracking
    total_hours_completed = Column(DECIMAL(5, 2), default=0)
    ethics_hours_completed = Column(DECIMAL(5, 2), default=0)
    live_hours_completed = Column(DECIMAL(5, 2), default=0)
    carry_forward_hours = Column(DECIMAL(5, 2), default=0)

    # Compliance Status
    is_compliant = Column(Boolean, default=False)
    hours_needed = Column(DECIMAL(5, 2), default=0)
    ethics_hours_needed = Column(DECIMAL(5, 2), default=0)

    # Dates
    last_calculated = Column(DateTime, default=datetime.utcnow)
    next_renewal_date = Column(Date)

    # Relationships
    user = relationship("User", back_populates="compliance_records")
    jurisdiction = relationship("CPAJurisdiction")


# =================
# CPA JURISDICTION MODELS (NASBA Data)
# =================


class CPAJurisdiction(Base):
    __tablename__ = "cpa_jurisdictions"

    code = Column(String(2), primary_key=True)  # State code: CA, NY, TX, etc.
    name = Column(String(100), nullable=False)

    # Board Information
    board_name = Column(String(200))
    board_website = Column(String(500))
    licensing_website = Column(String(500))

    # CPE Requirements (from NASBA)
    general_hours_required = Column(Integer, nullable=False)
    ethics_hours_required = Column(Integer, default=0)
    live_hours_required = Column(Integer, default=0)

    # Reporting Period
    reporting_period_type = Column(String(20))  # annual, biennial, triennial
    reporting_period_months = Column(Integer)  # 12, 24, 36
    renewal_date_pattern = Column(String(100))  # "6/30 annually", "12/31 biennially"
    reporting_period_description = Column(String(200))  # "1/1 to 12/31 annually"

    # Special Rules
    self_study_max_hours = Column(Integer)
    carry_forward_max_hours = Column(Integer, default=0)
    minimum_hours_per_year = Column(Integer)

    # CE Broker
    ce_broker_required = Column(Boolean, default=False)
    ce_broker_mandatory_date = Column(Date)

    # NASBA Data Tracking
    nasba_last_updated = Column(Date)
    data_source = Column(String(50), default="NASBA")
    data_confidence = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NASBAProvider(Base):
    __tablename__ = "nasba_providers"

    id = Column(Integer, primary_key=True, index=True)
    sponsor_id = Column(String(20), unique=True, index=True)  # "112530", "009930"
    sponsor_name = Column(String(200), nullable=False)

    # Registration Details
    registry_status = Column(String(20))  # "Active", "Inactive"
    registration_date = Column(Date)
    expiration_date = Column(Date)

    # Contact Information
    website = Column(String(500))
    contact_email = Column(String(100))
    phone = Column(String(20))

    # Delivery Methods
    group_live = Column(Boolean, default=False)
    group_internet = Column(Boolean, default=False)
    self_study = Column(Boolean, default=False)
    nano_learning = Column(Boolean, default=False)

    # Data Tracking
    last_verified = Column(Date)
    verification_source = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =================
# DATA SOURCE TRACKING
# =================


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # "NASBA", "CE_BROKER", "STATE_API"
    type = Column(String(50))  # "API", "SCRAPING", "MANUAL", "PARTNERSHIP"

    # Connection Details
    endpoint_url = Column(String(500))
    api_key_required = Column(Boolean, default=False)
    authentication_method = Column(String(50))

    # Update Configuration
    update_frequency = Column(String(50))  # "daily", "weekly", "monthly"
    last_successful_update = Column(DateTime)
    last_attempted_update = Column(DateTime)
    update_status = Column(String(20))  # "success", "failed", "in_progress"

    # Reliability Metrics
    success_rate = Column(Float, default=1.0)
    average_response_time = Column(Float)

    # Configuration
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # Higher number = higher priority

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataSyncLog(Base):
    __tablename__ = "data_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"))

    # Sync Details
    sync_type = Column(String(50))  # "full", "incremental", "verification"
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    status = Column(String(20))  # "success", "failed", "in_progress"

    # Results
    records_processed = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_added = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)

    # Error Handling
    error_message = Column(Text)
    error_details = Column(JSONB)

    # Relationships
    data_source = relationship("DataSource")


# =================
# AUDIT AND HISTORY
# =================


class RequirementChange(Base):
    __tablename__ = "requirement_changes"

    id = Column(Integer, primary_key=True, index=True)
    jurisdiction_code = Column(String(2), ForeignKey("cpa_jurisdictions.code"))

    # Change Details
    field_name = Column(String(50), nullable=False)
    old_value = Column(String(200))
    new_value = Column(String(200))
    change_reason = Column(String(200))

    # Source Information
    change_source = Column(String(50))  # "NASBA", "STATE_NOTIFICATION", "MANUAL"
    effective_date = Column(Date)
    detected_at = Column(DateTime, default=datetime.utcnow)

    # Verification
    verified_by = Column(String(100))
    verified_at = Column(DateTime)

    # Relationships
    jurisdiction = relationship("CPAJurisdiction")


# =================
# ONBOARDING PROGRESS
# =================


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_step = Column(String, nullable=True)  # This line is missing
    completed_steps = Column(JSON, default=list)
    step_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)
