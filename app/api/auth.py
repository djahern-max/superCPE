# app/api/auth.py - Fixed version with proper imports

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

# Fixed imports - use absolute imports
from app.core.database import get_db
from app.models import User
from app.schemas.auth import (
    UserRegistration,
    UserLogin,
    Token,
    UserProfile,
    RegistrationResponse,
    LoginResponse,
)

# Security setup
SECRET_KEY = (
    "your-secret-key-change-in-production"  # In production, use environment variable
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


# Endpoints
@router.get("/test")
async def test_auth():
    return {"message": "Auth router is working with JWT!", "version": "2.0"}


@router.post("/register", response_model=RegistrationResponse)
async def register(user_data: UserRegistration, db: Session = Depends(get_db)):
    """Register a new user with configurable jurisdiction"""

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Hash the password
    hashed_password = get_password_hash(user_data.password)

    # Create new user - use jurisdiction from request or default to NH
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        primary_jurisdiction=user_data.primary_jurisdiction,
        onboarding_step="registration",
        is_active=True,
        email_reminders=True,
        newsletter_subscription=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}, expires_delta=access_token_expires
    )

    token = Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
    )

    return RegistrationResponse(
        message=f"Welcome to SuperCPE, {user.full_name}!",
        user_id=user.id,
        next_step="basic_info",
        token=token,
    )


@router.post("/login", response_model=LoginResponse)
async def login_json(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login with JSON data"""

    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}, expires_delta=access_token_expires
    )

    token = Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
    )

    # Build user profile - only use fields that exist in your User model
    user_profile = UserProfile(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        primary_jurisdiction=getattr(user, "primary_jurisdiction", None),
        license_number=getattr(user, "license_number", None),
        # Safe defaults for fields that might not exist in User model
        license_issue_date=getattr(user, "license_issue_date", None),
        next_renewal_date=getattr(user, "next_renewal_date", None),
        secondary_jurisdictions=getattr(user, "secondary_jurisdictions", None),
        phone_number=getattr(user, "phone_number", None),
        linkedin_url=getattr(user, "linkedin_url", None),
        twitter_handle=getattr(user, "twitter_handle", None),
        facebook_url=getattr(user, "facebook_url", None),
        instagram_handle=getattr(user, "instagram_handle", None),
        website_url=getattr(user, "website_url", None),
        firm_name=getattr(user, "firm_name", None),
        firm_website=getattr(user, "firm_website", None),
        firm_phone=getattr(user, "firm_phone", None),
        firm_address_line1=getattr(user, "firm_address_line1", None),
        firm_address_line2=getattr(user, "firm_address_line2", None),
        firm_city=getattr(user, "firm_city", None),
        firm_state=getattr(user, "firm_state", None),
        firm_zip_code=getattr(user, "firm_zip_code", None),
        job_title=getattr(user, "job_title", None),
        years_experience=getattr(user, "years_experience", None),
        specializations=getattr(user, "specializations", None),
        professional_certifications=getattr(user, "professional_certifications", None),
        ce_broker_auto_sync=getattr(user, "ce_broker_auto_sync", False),
        email_reminders=getattr(user, "email_reminders", True),
        newsletter_subscription=getattr(user, "newsletter_subscription", False),
        marketing_emails=getattr(user, "marketing_emails", False),
        public_profile=getattr(user, "public_profile", False),
        onboarding_step=getattr(user, "onboarding_step", "registration"),
        created_at=user.created_at,
    )

    return LoginResponse(
        message=f"Welcome back, {user.full_name}!",
        token=token,
        user=user_profile,
        onboarding_required=(
            getattr(user, "onboarding_step", "registration") != "complete"
        ),
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile"""

    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        primary_jurisdiction=getattr(current_user, "primary_jurisdiction", None),
        license_number=getattr(current_user, "license_number", None),
        # Safe defaults for fields that might not exist in User model
        license_issue_date=getattr(current_user, "license_issue_date", None),
        next_renewal_date=getattr(current_user, "next_renewal_date", None),
        secondary_jurisdictions=getattr(current_user, "secondary_jurisdictions", None),
        phone_number=getattr(current_user, "phone_number", None),
        linkedin_url=getattr(current_user, "linkedin_url", None),
        twitter_handle=getattr(current_user, "twitter_handle", None),
        facebook_url=getattr(current_user, "facebook_url", None),
        instagram_handle=getattr(current_user, "instagram_handle", None),
        website_url=getattr(current_user, "website_url", None),
        firm_name=getattr(current_user, "firm_name", None),
        firm_website=getattr(current_user, "firm_website", None),
        firm_phone=getattr(current_user, "firm_phone", None),
        firm_address_line1=getattr(current_user, "firm_address_line1", None),
        firm_address_line2=getattr(current_user, "firm_address_line2", None),
        firm_city=getattr(current_user, "firm_city", None),
        firm_state=getattr(current_user, "firm_state", None),
        firm_zip_code=getattr(current_user, "firm_zip_code", None),
        job_title=getattr(current_user, "job_title", None),
        years_experience=getattr(current_user, "years_experience", None),
        specializations=getattr(current_user, "specializations", None),
        professional_certifications=getattr(
            current_user, "professional_certifications", None
        ),
        ce_broker_auto_sync=getattr(current_user, "ce_broker_auto_sync", False),
        email_reminders=getattr(current_user, "email_reminders", True),
        newsletter_subscription=getattr(current_user, "newsletter_subscription", False),
        marketing_emails=getattr(current_user, "marketing_emails", False),
        public_profile=getattr(current_user, "public_profile", False),
        onboarding_step=getattr(current_user, "onboarding_step", "registration"),
        created_at=current_user.created_at,
    )


@router.get("/test-protected")
async def test_protected_endpoint(current_user: User = Depends(get_current_user)):
    """Test protected endpoint that requires authentication"""

    return {
        "message": f"Hello {current_user.full_name}! This is a protected endpoint.",
        "user_id": current_user.id,
        "email": current_user.email,
        "access_time": datetime.utcnow().isoformat(),
    }
