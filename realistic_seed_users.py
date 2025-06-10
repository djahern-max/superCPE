#!/usr/bin/env python3
"""
Realistic Test Users Seed Script for SuperCPE
Uses real data where available, minimal fictional data elsewhere
Based on actual NH CPA license screenshots and web research

Usage:
  Create users: python realistic_seed_users.py
  Delete users: python realistic_seed_users.py --delete
  Show users:   python realistic_seed_users.py --show
"""

import os
import sys
from datetime import date, datetime
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# Add the app directory to the path so we can import our models
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.core.database import engine, SessionLocal
from app.models import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_realistic_test_users():
    """
    Create 7 test CPA users based on NH licensing screenshots
    Uses real business data where found through web research
    """
    
    test_users = [
        # REAL DATA - A. Anthony Grizzaffi (Complete business profile found)
        {
            "email": "anthony.grizzaffi@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "A. Anthony Grizzaffi",
            "license_number": "01142",                # REAL from BBB records
            "primary_jurisdiction": "NH",
            "license_issue_date": date(1982, 8, 16),  # From NH license screenshot
            "next_renewal_date": date(2026, 6, 30),   # From NH license screenshot
            
            # REAL contact & business info from web research
            "phone_number": "(603) 298-7742",        # REAL from Yellow Pages
            "linkedin_url": "https://linkedin.com/in/a-anthony-grizzaffi-61678918/",  # REAL LinkedIn
            
            # REAL firm information
            "firm_name": "A. Anthony Grizzaffi, CPA", # REAL business name
            "firm_address_line1": "1 Glen Rd",       # REAL address from directories
            "firm_address_line2": "Suite 202",       # REAL suite number
            "firm_city": "West Lebanon",             # REAL city
            "firm_state": "NH",
            "firm_zip_code": "03784",                # REAL zip code
            "job_title": "Owner",                    # REAL from LinkedIn
            
            # Calculated from license data
            "years_experience": 42,                  # 2024 - 1982
            "specializations": "Tax Preparation, Accounting Services",  # From business listings
            
            # Test settings
            "onboarding_step": "complete",
            "is_active": True,
            "is_verified": True,
            "email_reminders": True,
            "newsletter_subscription": True,
            "marketing_emails": False,
            "public_profile": True
        },
        
        # REAL DATA - Daniel J. Ahern (Business profile found)
        {
            "email": "daniel.ahern@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "Daniel Joesph Ahern",      # From screenshot (keeping original spelling)
            "license_number": "07308",               # From NH license screenshot
            "primary_jurisdiction": "NH",
            "license_issue_date": date(2014, 6, 13), # From NH license screenshot
            "next_renewal_date": date(2027, 6, 30),  # From NH license screenshot
            
            # REAL contact & business info from web research
            "phone_number": "(603) 812-5654",       # REAL from tax preparer directory
            
            # REAL firm information
            "firm_name": "Daniel J. Ahern, CPA",     # REAL business name
            "firm_address_line1": "8 Squire Way",    # REAL address from tax directory
            "firm_city": "Exeter",                   # REAL city (not Manchester as guessed)
            "firm_state": "NH",
            "firm_zip_code": "03833",                # REAL zip code
            "job_title": "Owner",                    # CPA practice owner
            
            # Calculated from license data
            "years_experience": 11,                  # 2025 - 2014
            "specializations": "Tax Preparation, Planning, Bookkeeping, Accounting",  # REAL from directory
            
            # Test settings
            "onboarding_step": "complete",
            "is_active": True,
            "is_verified": True,
            "email_reminders": True,
            "newsletter_subscription": True,
            "marketing_emails": True,
            "public_profile": True
        },
        
        # MINIMAL DATA - Aaron Cheung (No business info found)
        {
            "email": "aaron.cheung@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "Aaron Cheung",
            "license_number": "07676",               # From NH license screenshot
            "primary_jurisdiction": "NH",
            "license_issue_date": date(2014, 10, 7), # From NH license screenshot
            "next_renewal_date": date(2027, 6, 30),  # From NH license screenshot
            
            # Calculated only
            "years_experience": 10,                  # 2024 - 2014
            
            # Test settings - incomplete onboarding
            "onboarding_step": "license_info",
            "is_active": True,
            "is_verified": True,
            "email_reminders": True,
            "newsletter_subscription": False,
            "marketing_emails": True,
            "public_profile": False
        },
        
        # MINIMAL DATA - Aaron Dennis Howell (No business info found)
        {
            "email": "aaron.howell@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "Aaron Dennis Howell",
            "license_number": "10028-R",             # From NH license screenshot
            "primary_jurisdiction": "NH",
            "license_issue_date": date(2025, 1, 27), # From NH license screenshot - very new!
            "next_renewal_date": date(2027, 1, 27),  # From NH license screenshot
            
            # Calculated only
            "years_experience": 0,                   # Brand new CPA (licensed in 2025)
            
            # Test settings - early onboarding stage
            "onboarding_step": "basic_info",
            "is_active": True,
            "is_verified": True,
            "email_reminders": True,
            "newsletter_subscription": True,
            "marketing_emails": True,
            "public_profile": False
        },
        
        # MINIMAL DATA - Aaron R Jones (No business info found)
        {
            "email": "aaron.jones@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "Aaron R Jones",
            "license_number": "05118",               # From NH license screenshot
            "primary_jurisdiction": "NH",
            "license_issue_date": date(2009, 12, 21), # From NH license screenshot
            "next_renewal_date": date(2026, 6, 30),   # From NH license screenshot
            
            # Calculated only
            "years_experience": 15,                   # 2024 - 2009
            
            # Test settings - mid onboarding
            "onboarding_step": "contact_info",
            "is_active": True,
            "is_verified": True,
            "email_reminders": True,
            "newsletter_subscription": True,
            "marketing_emails": True,
            "public_profile": True
        },
        
        # MINIMAL DATA - Aaron Stonecash (No business info found)
        {
            "email": "aaron.stonecash@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "Aaron Stonecash",
            "license_number": "06696",               # From NH license screenshot
            "primary_jurisdiction": "NH",
            "license_issue_date": date(2013, 7, 26), # From NH license screenshot
            "next_renewal_date": date(2027, 6, 30),  # From NH license screenshot
            
            # Calculated only
            "years_experience": 11,                  # 2024 - 2013
            
            # Test settings - late onboarding
            "onboarding_step": "preferences",
            "is_active": True,
            "is_verified": True,
            "email_reminders": True,
            "newsletter_subscription": False,
            "marketing_emails": False,
            "public_profile": True
        },
        
        # MINIMAL DATA - Aaron Telage (No business info found)
        {
            "email": "aaron.telage@testmail.com",
            "password_hash": hash_password("TestPassword123!"),
            "full_name": "Aaron Telage",
            "license_number": "07900",               # From NH license screenshot
            "primary_jurisdiction": "NH",
            "license_issue_date": date(2015, 7, 20), # From NH license screenshot
            "next_renewal_date": date(2025, 6, 30),  # From NH license screenshot - expires soon!
            
            # Calculated only
            "years_experience": 9,                   # 2024 - 2015
            
            # Test settings - just registered
            "onboarding_step": "registration",
            "is_active": True,
            "is_verified": False,                    # Not yet verified for testing
            "email_reminders": True,
            "newsletter_subscription": True,
            "marketing_emails": True,
            "public_profile": False
        }
    ]
    
    return test_users

def create_test_users():
    """Insert test users into database"""
    
    test_users = create_realistic_test_users()
    
    db = SessionLocal()
    try:
        # Check if users already exist
        existing_emails = {user.email for user in db.query(User).all()}
        
        users_created = 0
        users_skipped = 0
        
        print("🏗️  Creating realistic test CPA users...")
        print("📊 Using real business data where available from web research")
        print("")
        
        for user_data in test_users:
            if user_data["email"] in existing_emails:
                print(f"⚠️  User {user_data['email']} already exists, skipping...")
                users_skipped += 1
                continue
            
            # Create user
            user = User(**user_data)
            db.add(user)
            users_created += 1
            
            # Show what type of data we have
            data_type = "🟢 REAL DATA" if user_data.get('firm_name') else "🟡 MINIMAL DATA"
            print(f"✅ {data_type}: {user_data['full_name']} (License #{user_data['license_number']})")
            
            if user_data.get('firm_name'):
                print(f"   📍 {user_data['firm_name']} - {user_data.get('firm_city', 'Unknown')}, NH")
            
            if user_data.get('phone_number'):
                print(f"   📞 {user_data['phone_number']}")
                
            print(f"   👤 {user_data['years_experience']} years experience - Onboarding: {user_data['onboarding_step']}")
            print("")
        
        # Commit all users
        db.commit()
        
        print("🎉 Database seeding complete!")
        print(f"   ✅ Created: {users_created} users")
        print(f"   ⚠️  Skipped: {users_skipped} users (already existed)")
        print(f"   📊 Total users in database: {db.query(User).count()}")
        
        # Show testing scenarios
        if users_created > 0:
            print(f"\n🧪 Test Scenarios Available:")
            print(f"   • Complete profiles: A. Anthony Grizzaffi, Daniel J. Ahern")
            print(f"   • Various onboarding stages: registration → basic_info → license_info → contact_info → preferences → complete")
            print(f"   • Brand new CPA: Aaron Dennis Howell (licensed 2025)")
            print(f"   • Expiring license: Aaron Telage (expires 6/30/2025)")
            print(f"   • Mix of verification statuses and preferences")
            print(f"\n🔑 All test users password: TestPassword123!")
                
    except Exception as e:
        print(f"❌ Error creating users: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def delete_test_users():
    """Delete all test users (useful for testing)"""
    test_emails = [
        "anthony.grizzaffi@testmail.com",
        "daniel.ahern@testmail.com",
        "aaron.cheung@testmail.com", 
        "aaron.howell@testmail.com",
        "aaron.jones@testmail.com",
        "aaron.stonecash@testmail.com",
        "aaron.telage@testmail.com"
    ]
    
    db = SessionLocal()
    try:
        deleted_count = db.query(User).filter(User.email.in_(test_emails)).delete(synchronize_session=False)
        db.commit()
        print(f"🗑️  Deleted {deleted_count} test users")
        print(f"📊 Remaining users in database: {db.query(User).count()}")
    except Exception as e:
        print(f"❌ Error deleting users: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def show_test_users():
    """Display current test users in database"""
    test_emails = [
        "anthony.grizzaffi@testmail.com",
        "daniel.ahern@testmail.com",
        "aaron.cheung@testmail.com", 
        "aaron.howell@testmail.com",
        "aaron.jones@testmail.com",
        "aaron.stonecash@testmail.com",
        "aaron.telage@testmail.com"
    ]
    
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.email.in_(test_emails)).all()
        
        if not users:
            print("👥 No test users found in database")
            return
            
        print(f"👥 Found {len(users)} test users:")
        print("")
        
        for user in users:
            data_type = "🟢 REAL" if user.firm_name else "🟡 MINIMAL"
            print(f"{data_type} {user.full_name} (#{user.license_number})")
            print(f"   📧 {user.email}")
            print(f"   👤 {user.years_experience or 0} years exp - {user.onboarding_step}")
            
            if user.firm_name:
                location = f"{user.firm_city}, {user.firm_state}" if user.firm_city else "NH"
                print(f"   🏢 {user.firm_name} - {location}")
                
            if user.phone_number:
                print(f"   📞 {user.phone_number}")
                
            print("")
            
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage realistic test CPA users")
    parser.add_argument("--delete", action="store_true", help="Delete test users instead of creating them")
    parser.add_argument("--show", action="store_true", help="Show existing test users")
    
    args = parser.parse_args()
    
    if args.delete:
        print("🗑️  Deleting test users...")
        delete_test_users()
    elif args.show:
        print("👥 Showing test users...")
        show_test_users()
    else:
        print("👥 Creating realistic test users...")
        create_test_users()
    
    print("✨ Done!")
