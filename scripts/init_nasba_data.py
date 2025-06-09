"""
NASBA Data Initialization Script
Populates the database with CPA jurisdiction requirements from NASBA data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.models import CPAJurisdiction, NASBAProvider, DataSource, User, CPERecord
from app.core.database import engine, SessionLocal
from datetime import date, datetime
from decimal import Decimal

def initialize_nasba_jurisdictions(db: Session):
    """Initialize CPA jurisdictions with NASBA data"""
    
    # Key CPA jurisdictions with NASBA data
    nasba_jurisdictions = [
        {
            'code': 'AL',
            'name': 'Alabama',
            'board_name': 'Alabama State Board of Public Accountancy',
            'general_hours_required': 40,
            'ethics_hours_required': 2,
            'reporting_period_type': 'annual',
            'reporting_period_months': 12,
            'renewal_date_pattern': '9/30 annually',
            'reporting_period_description': '10/1 to 9/30 annually',
            'ce_broker_required': False
        },
        {
            'code': 'CA',
            'name': 'California',
            'board_name': 'California Board of Accountancy',
            'general_hours_required': 80,
            'ethics_hours_required': 4,
            'reporting_period_type': 'biennial',
            'reporting_period_months': 24,
            'renewal_date_pattern': 'Last day of birth month in odd or even year',
            'reporting_period_description': 'Biennial based on birth year',
            'ce_broker_required': False
        },
        {
            'code': 'NH',
            'name': 'New Hampshire',
            'board_name': 'New Hampshire Board of Accountancy',
            'board_website': 'https://www.oplc.nh.gov/accountancy',
            'general_hours_required': 120,
            'ethics_hours_required': 3,
            'reporting_period_type': 'triennial',
            'reporting_period_months': 36,
            'renewal_date_pattern': '12/31 triennially',
            'reporting_period_description': '1/1 to 12/31 triennially',
            'ce_broker_required': True,
            'ce_broker_mandatory_date': date(2025, 2, 3)
        },
        {
            'code': 'NY',
            'name': 'New York',
            'board_name': 'New York State Board for Public Accountancy',
            'general_hours_required': 40,
            'ethics_hours_required': 4,
            'reporting_period_type': 'triennial',
            'reporting_period_months': 36,
            'renewal_date_pattern': 'Triennial based on issuance date',
            'reporting_period_description': 'Triennial based on issuance date and birth month',
            'ce_broker_required': False
        },
        {
            'code': 'TX',
            'name': 'Texas',
            'board_name': 'Texas State Board of Public Accountancy',
            'general_hours_required': 40,
            'ethics_hours_required': 2,
            'reporting_period_type': 'annual',
            'reporting_period_months': 12,
            'renewal_date_pattern': '6/30 annually',
            'reporting_period_description': '1/1 to 12/31 annually',
            'ce_broker_required': False
        },
        {
            'code': 'FL',
            'name': 'Florida',
            'board_name': 'Florida Board of Accountancy',
            'general_hours_required': 80,
            'ethics_hours_required': 4,
            'reporting_period_type': 'biennial',
            'reporting_period_months': 24,
            'renewal_date_pattern': '6/30 biennially',
            'reporting_period_description': '7/1 to 6/30 biennially',
            'ce_broker_required': False
        }
    ]
    
    for jurisdiction_data in nasba_jurisdictions:
        # Check if jurisdiction already exists
        existing = db.query(CPAJurisdiction).filter(
            CPAJurisdiction.code == jurisdiction_data['code']
        ).first()
        
        if not existing:
            jurisdiction = CPAJurisdiction(
                code=jurisdiction_data['code'],
                name=jurisdiction_data['name'],
                board_name=jurisdiction_data['board_name'],
                board_website=jurisdiction_data.get('board_website'),
                general_hours_required=jurisdiction_data['general_hours_required'],
                ethics_hours_required=jurisdiction_data['ethics_hours_required'],
                reporting_period_type=jurisdiction_data['reporting_period_type'],
                reporting_period_months=jurisdiction_data['reporting_period_months'],
                renewal_date_pattern=jurisdiction_data['renewal_date_pattern'],
                reporting_period_description=jurisdiction_data['reporting_period_description'],
                ce_broker_required=jurisdiction_data['ce_broker_required'],
                ce_broker_mandatory_date=jurisdiction_data.get('ce_broker_mandatory_date'),
                nasba_last_updated=date.today(),
                data_source='NASBA',
                data_confidence=1.0
            )
            db.add(jurisdiction)
    
    db.commit()
    print(f"Initialized {len(nasba_jurisdictions)} CPA jurisdictions")

def initialize_nasba_providers(db: Session):
    """Initialize NASBA provider data"""
    
    nasba_providers = [
        {
            'sponsor_id': '112530',
            'sponsor_name': 'Professional Education Services, LP',
            'registry_status': 'Active',
            'website': 'https://www.mypescpe.com',
            'group_live': True,
            'group_internet': True,
            'self_study': True
        },
        {
            'sponsor_id': '009930',
            'sponsor_name': 'Continuing Professional Education Network',
            'registry_status': 'Active',
            'website': None,
            'group_live': False,
            'group_internet': False,
            'self_study': True
        },
        {
            'sponsor_id': '002547',
            'sponsor_name': 'New York State CPE Provider',
            'registry_status': 'Active',
            'website': None,
            'group_live': True,
            'group_internet': True,
            'self_study': True
        }
    ]
    
    for provider_data in nasba_providers:
        # Check if provider already exists
        existing = db.query(NASBAProvider).filter(
            NASBAProvider.sponsor_id == provider_data['sponsor_id']
        ).first()
        
        if not existing:
            provider = NASBAProvider(
                sponsor_id=provider_data['sponsor_id'],
                sponsor_name=provider_data['sponsor_name'],
                registry_status=provider_data['registry_status'],
                website=provider_data['website'],
                group_live=provider_data['group_live'],
                group_internet=provider_data['group_internet'],
                self_study=provider_data['self_study'],
                last_verified=date.today()
            )
            db.add(provider)
    
    db.commit()
    print(f"Initialized {len(nasba_providers)} NASBA providers")

def initialize_data_sources(db: Session):
    """Initialize data source configurations"""
    
    data_sources = [
        {
            'name': 'NASBA Registry',
            'type': 'PARTNERSHIP',
            'endpoint_url': 'https://www.nasbaregistry.org/cpe-requirements',
            'api_key_required': False,
            'update_frequency': 'monthly',
            'is_active': True,
            'priority': 1
        },
        {
            'name': 'CE Broker API',
            'type': 'API',
            'endpoint_url': 'https://api.cebroker.com',
            'api_key_required': True,
            'update_frequency': 'real-time',
            'is_active': False,  # Enable when API access is obtained
            'priority': 2
        },
        {
            'name': 'Manual Entry',
            'type': 'MANUAL',
            'endpoint_url': None,
            'api_key_required': False,
            'update_frequency': 'as_needed',
            'is_active': True,
            'priority': 10
        }
    ]
    
    for source_data in data_sources:
        # Check if data source already exists
        existing = db.query(DataSource).filter(
            DataSource.name == source_data['name']
        ).first()
        
        if not existing:
            data_source = DataSource(
                name=source_data['name'],
                type=source_data['type'],
                endpoint_url=source_data['endpoint_url'],
                api_key_required=source_data['api_key_required'],
                update_frequency=source_data['update_frequency'],
                is_active=source_data['is_active'],
                priority=source_data['priority'],
                success_rate=1.0
            )
            db.add(data_source)
    
    db.commit()
    print(f"Initialized {len(data_sources)} data sources")

def create_sample_user_data(db: Session):
    """Create sample user based on the certificates provided"""
    
    # Create sample user (Daniel Ahern based on certificates)
    existing_user = db.query(User).filter(User.email == "danielaherniv@gmail.com").first()
    if existing_user:
        print("Sample user already exists")
        return
    
    sample_user = User(
        email="danielaherniv@gmail.com",
        full_name="Daniel Ahern",
        license_number="NH12345",  # You'll need to update with actual license
        primary_jurisdiction="NH",
        secondary_jurisdictions=None,
        next_renewal_date=date(2025, 12, 31),  # Adjust based on NH triennial cycle
        ce_broker_auto_sync=True
    )
    
    db.add(sample_user)
    db.flush()  # Get the user ID
    
    # Add sample CPE records based on the certificates you uploaded
    sample_courses = [
        {
            'course_name': 'Debt: Selected Debt Related Issues',
            'course_code': 'M116-2025-01-SSDL',
            'provider_name': 'Professional Education Services, LP',
            'field_of_study': 'Taxes',
            'cpe_credits': Decimal('2.00'),
            'completion_date': date(2025, 6, 6),
            'delivery_method': 'QAS Self-Study',
            'nasba_sponsor_id': '112530',
            'is_ethics': False
        },
        {
            'course_name': 'The New Lease Standard ASU 2016-02 and Other Amendments',
            'course_code': 'M228-2025-01-SSDL',
            'provider_name': 'Professional Education Services, LP',
            'field_of_study': 'Accounting',
            'cpe_credits': Decimal('4.00'),
            'completion_date': date(2025, 6, 6),
            'delivery_method': 'QAS Self-Study',
            'nasba_sponsor_id': '112530',
            'is_ethics': False
        },
        {
            'course_name': 'Understanding the Economy',
            'course_code': 'M232-2025-01-SSDL',
            'provider_name': 'Professional Education Services, LP',
            'field_of_study': 'Economics',
            'cpe_credits': Decimal('8.00'),
            'completion_date': date(2025, 6, 6),
            'delivery_method': 'QAS Self-Study',
            'nasba_sponsor_id': '112530',
            'is_ethics': False
        },
        {
            'course_name': 'Fraud and Public Corruption: Prevention and Detection',
            'course_code': 'M204-2025-01-SSDL',
            'provider_name': 'Professional Education Services, LP',
            'field_of_study': 'Auditing - Fraud',
            'cpe_credits': Decimal('8.00'),
            'completion_date': date(2025, 6, 6),
            'delivery_method': 'QAS Self-Study',
            'nasba_sponsor_id': '112530',
            'is_ethics': False
        },
        {
            'course_name': 'Guide to Federal Corporate and Individual Taxation',
            'course_code': 'M305-2024-01-SSDL',
            'provider_name': 'Professional Education Services, LP',
            'field_of_study': 'Taxes',
            'cpe_credits': Decimal('33.00'),
            'completion_date': date(2025, 6, 5),
            'delivery_method': 'QAS Self-Study',
            'nasba_sponsor_id': '112530',
            'is_ethics': False
        }
    ]
    
    for course_data in sample_courses:
        cpe_record = CPERecord(
            user_id=sample_user.id,
            course_name=course_data['course_name'],
            course_code=course_data['course_code'],
            provider_name=course_data['provider_name'],
            field_of_study=course_data['field_of_study'],
            cpe_credits=course_data['cpe_credits'],
            completion_date=course_data['completion_date'],
            delivery_method=course_data['delivery_method'],
            nasba_sponsor_id=course_data['nasba_sponsor_id'],
            is_ethics=course_data['is_ethics'],
            nasba_registry_verified=True,
            extraction_confidence=1.0,
            manually_verified=True
        )
        db.add(cpe_record)
    
    db.commit()
    print(f"Created sample user with {len(sample_courses)} CPE records")

def main():
    """Main initialization function"""
    
    db = SessionLocal()
    
    try:
        print("Initializing NASBA data...")
        initialize_nasba_jurisdictions(db)
        initialize_nasba_providers(db)
        initialize_data_sources(db)
        create_sample_user_data(db)
        print("Database initialization complete!")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
