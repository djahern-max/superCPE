"""
CPA Utilities and Helper Functions
Provides common operations for CPA compliance tracking
"""

from sqlalchemy.orm import Session
from ..models import User, CPERecord, CPAJurisdiction, ComplianceRecord, NASBAProvider
from ..schemas import ComplianceStatusData, CPEAnalytics
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import re


class CPAComplianceCalculator:
    """Calculate CPA compliance status for users"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_compliance(
        self, user_id: int, jurisdiction_code: str = None
    ) -> ComplianceStatusData:
        """Calculate compliance status for a user in a specific jurisdiction"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Use primary jurisdiction if none specified
        if not jurisdiction_code:
            jurisdiction_code = user.primary_jurisdiction

        jurisdiction = (
            self.db.query(CPAJurisdiction)
            .filter(CPAJurisdiction.code == jurisdiction_code)
            .first()
        )

        if not jurisdiction:
            raise ValueError(f"Jurisdiction {jurisdiction_code} not found")

        # Get current reporting period
        reporting_period = self._get_current_reporting_period(
            jurisdiction, user.next_renewal_date
        )

        # Get CPE records for this period
        cpe_records = (
            self.db.query(CPERecord)
            .filter(
                CPERecord.user_id == user_id,
                CPERecord.completion_date >= reporting_period["start"],
                CPERecord.completion_date <= reporting_period["end"],
            )
            .all()
        )

        # Calculate totals
        total_hours = sum(record.cpe_credits for record in cpe_records)
        ethics_hours = sum(
            record.cpe_credits for record in cpe_records if record.is_ethics
        )

        # Check compliance
        is_compliant = (
            total_hours >= jurisdiction.general_hours_required
            and ethics_hours >= jurisdiction.ethics_hours_required
        )

        hours_needed = max(0, jurisdiction.general_hours_required - total_hours)
        ethics_hours_needed = max(0, jurisdiction.ethics_hours_required - ethics_hours)

        # Calculate days until renewal
        days_until_renewal = None
        if user.next_renewal_date:
            days_until_renewal = (user.next_renewal_date - date.today()).days

        return ComplianceStatusData(
            is_compliant=is_compliant,
            total_hours_completed=total_hours,
            total_hours_required=jurisdiction.general_hours_required,
            hours_needed=hours_needed,
            ethics_hours_completed=ethics_hours,
            ethics_hours_required=jurisdiction.ethics_hours_required,
            ethics_hours_needed=ethics_hours_needed,
            next_renewal_date=user.next_renewal_date,
            days_until_renewal=days_until_renewal,
            compliance_percentage=min(
                100.0, float(total_hours / jurisdiction.general_hours_required * 100)
            ),
        )

    def _get_current_reporting_period(
        self, jurisdiction: CPAJurisdiction, renewal_date: date
    ) -> Dict[str, date]:
        """Calculate the current reporting period for a jurisdiction"""

        if not renewal_date:
            # Default to current year if no renewal date
            if jurisdiction.reporting_period_type == "annual":
                return {
                    "start": date(date.today().year, 1, 1),
                    "end": date(date.today().year, 12, 31),
                }

        # Calculate based on renewal date and period type
        if jurisdiction.reporting_period_type == "annual":
            period_start = date(renewal_date.year, 1, 1)
            period_end = date(renewal_date.year, 12, 31)
        elif jurisdiction.reporting_period_type == "biennial":
            # 2-year period ending on renewal date
            period_end = renewal_date
            period_start = date(renewal_date.year - 1, 1, 1)
        elif jurisdiction.reporting_period_type == "triennial":
            # 3-year period ending on renewal date
            period_end = renewal_date
            period_start = date(renewal_date.year - 2, 1, 1)
        else:
            # Default to annual
            period_start = date(renewal_date.year, 1, 1)
            period_end = date(renewal_date.year, 12, 31)

        return {"start": period_start, "end": period_end}

    def get_recommendations(
        self, user_id: int, jurisdiction_code: str = None
    ) -> List[str]:
        """Get compliance recommendations for a user"""

        compliance = self.calculate_compliance(user_id, jurisdiction_code)
        recommendations = []

        if compliance.hours_needed > 0:
            recommendations.append(f"Complete {compliance.hours_needed} more CPE hours")

        if compliance.ethics_hours_needed > 0:
            recommendations.append(
                f"Complete {compliance.ethics_hours_needed} more ethics hours"
            )

        if compliance.days_until_renewal and compliance.days_until_renewal < 90:
            recommendations.append(
                "Renewal deadline approaching - prioritize remaining requirements"
            )

        if (
            compliance.compliance_percentage < 50
            and compliance.days_until_renewal
            and compliance.days_until_renewal < 180
        ):
            recommendations.append(
                "Consider accelerating CPE completion to avoid last-minute rush"
            )

        return recommendations


class CPEAnalyticsCalculator:
    """Calculate analytics and insights for CPE data"""

    def __init__(self, db: Session):
        self.db = db

    def get_user_analytics(
        self, user_id: int, start_date: date = None, end_date: date = None
    ) -> CPEAnalytics:
        """Get comprehensive analytics for a user's CPE records"""

        if not start_date:
            start_date = date.today() - timedelta(days=365)
        if not end_date:
            end_date = date.today()

        records = (
            self.db.query(CPERecord)
            .filter(
                CPERecord.user_id == user_id,
                CPERecord.completion_date >= start_date,
                CPERecord.completion_date <= end_date,
            )
            .all()
        )

        if not records:
            return CPEAnalytics(
                total_courses=0,
                total_hours=Decimal("0"),
                ethics_hours=Decimal("0"),
                hours_by_field={},
                hours_by_provider={},
                hours_by_month={},
                average_course_length=Decimal("0"),
                compliance_rate=0.0,
            )

        # Calculate basic metrics
        total_courses = len(records)
        total_hours = sum(record.cpe_credits for record in records)
        ethics_hours = sum(record.cpe_credits for record in records if record.is_ethics)

        # Hours by field of study
        hours_by_field = {}
        for record in records:
            field = record.field_of_study or "Unknown"
            hours_by_field[field] = (
                hours_by_field.get(field, Decimal("0")) + record.cpe_credits
            )

        # Hours by provider
        hours_by_provider = {}
        for record in records:
            provider = record.provider_name or "Unknown"
            hours_by_provider[provider] = (
                hours_by_provider.get(provider, Decimal("0")) + record.cpe_credits
            )

        # Hours by month
        hours_by_month = {}
        for record in records:
            month_key = record.completion_date.strftime("%Y-%m")
            hours_by_month[month_key] = (
                hours_by_month.get(month_key, Decimal("0")) + record.cpe_credits
            )

        # Average course length
        average_course_length = (
            total_hours / total_courses if total_courses > 0 else Decimal("0")
        )

        # Calculate compliance rate (simplified)
        user = self.db.query(User).filter(User.id == user_id).first()
        compliance_rate = 0.0
        if user:
            try:
                calculator = CPAComplianceCalculator(self.db)
                compliance = calculator.calculate_compliance(user_id)
                compliance_rate = compliance.compliance_percentage / 100.0
            except:
                compliance_rate = 0.0

        return CPEAnalytics(
            total_courses=total_courses,
            total_hours=total_hours,
            ethics_hours=ethics_hours,
            hours_by_field=hours_by_field,
            hours_by_provider=hours_by_provider,
            hours_by_month=hours_by_month,
            average_course_length=average_course_length,
            compliance_rate=compliance_rate,
        )


class NASBAValidator:
    """Validate CPE records against NASBA standards"""

    def __init__(self, db: Session):
        self.db = db

    def validate_nasba_provider(
        self, sponsor_id: str
    ) -> Tuple[bool, Optional[NASBAProvider]]:
        """Validate if a sponsor ID is registered with NASBA"""

        if not sponsor_id:
            return False, None

        provider = (
            self.db.query(NASBAProvider)
            .filter(
                NASBAProvider.sponsor_id == sponsor_id,
                NASBAProvider.registry_status == "Active",
            )
            .first()
        )

        return provider is not None, provider

    def validate_cpe_record(self, cpe_record: CPERecord) -> Dict[str, any]:
        """Comprehensive validation of a CPE record"""

        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
        }

        # Validate NASBA provider
        if cpe_record.nasba_sponsor_id:
            is_valid_provider, provider = self.validate_nasba_provider(
                cpe_record.nasba_sponsor_id
            )
            if not is_valid_provider:
                validation_result["warnings"].append(
                    f"NASBA Sponsor ID {cpe_record.nasba_sponsor_id} not found in registry"
                )
            else:
                cpe_record.nasba_registry_verified = True
        else:
            validation_result["warnings"].append("No NASBA Sponsor ID provided")

        # Validate course hours (reasonable limits)
        if cpe_record.cpe_credits > 20:
            validation_result["warnings"].append(
                "Course hours seem unusually high (>20 hours)"
            )
        if cpe_record.cpe_credits < 0.5:
            validation_result["warnings"].append(
                "Course hours seem unusually low (<0.5 hours)"
            )

        # Validate completion date
        if cpe_record.completion_date > date.today():
            validation_result["errors"].append(
                "Completion date cannot be in the future"
            )
            validation_result["is_valid"] = False

        if cpe_record.completion_date < date(1990, 1, 1):
            validation_result["warnings"].append("Completion date seems very old")

        # Validate ethics designation
        if cpe_record.is_ethics and not self._is_ethics_course(cpe_record):
            validation_result["warnings"].append(
                "Course marked as ethics but course name doesn't suggest ethics content"
            )

        # Validate field of study
        valid_fields = [
            "Accounting",
            "Auditing",
            "Taxes",
            "Economics",
            "Auditing - Fraud",
            "Personnel / Human Resources",
            "Communications and Marketing",
        ]
        if cpe_record.field_of_study and cpe_record.field_of_study not in valid_fields:
            validation_result["warnings"].append(
                f"Unusual field of study: {cpe_record.field_of_study}"
            )

        return validation_result

    def _is_ethics_course(self, cpe_record: CPERecord) -> bool:
        """Check if course appears to be an ethics course based on name/content"""
        ethics_keywords = [
            "ethics",
            "professional conduct",
            "professional responsibility",
            "code of conduct",
        ]
        course_name_lower = cpe_record.course_name.lower()
        return any(keyword in course_name_lower for keyword in ethics_keywords)


class CPECertificateExtractor:
    """Extract CPE information from certificate text/data"""

    def __init__(self):
        self.patterns = {
            "course_name": [
                r"for successfully completing\s*(.+)",
                r"course[:\s]+(.+)",
                r"completing\s*(.+?)(?:course|$)",
            ],
            "course_code": [
                r"course code[:\s]+([A-Z0-9\-]+)",
                r"code[:\s]+([A-Z0-9\-]+)",
                r"([A-Z]\d{3}\-\d{4}\-\d{2}\-[A-Z]+)",
            ],
            "provider_name": [
                r"(.+)(?:\n|\r\n)Executive Vice President",
                r"sponsor[:\s]+(.+)",
                r"provider[:\s]+(.+)",
            ],
            "field_of_study": [
                r"field of study[:\s]+(.+)",
                r"subject[:\s]+(.+)",
                r"area[:\s]+(.+)",
            ],
            "cpe_credits": [
                r"cpe credits?[:\s]+(\d+\.?\d*)",
                r"credits?[:\s]+(\d+\.?\d*)",
                r"(\d+\.?\d*)\s+credits?",
            ],
            "completion_date": [
                r"date[:\s]+(.+)",
                r"completed[:\s]+(.+)",
                r"(\w+day,\s+\w+\s+\d{1,2},\s+\d{4})",
            ],
            "nasba_sponsor_id": [
                r"tx sponsor #(\d+)",
                r"ny sponsor #(\d+)",
                r"nasba #(\d+)",
                r"sponsor #(\d+)",
            ],
            "delivery_method": [
                r"instructional method[:\s]+(.+)",
                r"delivery[:\s]+(.+)",
                r"method[:\s]+(.+)",
            ],
        }

    def extract_from_text(self, text: str) -> Dict[str, any]:
        """Extract CPE data from certificate text"""

        extracted_data = {}
        text_clean = text.strip().replace("\n", " ").replace("\r", " ")

        for field, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_clean, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()

                    # Clean up the extracted value
                    if field == "cpe_credits":
                        try:
                            extracted_data[field] = float(value)
                        except ValueError:
                            continue
                    elif field == "completion_date":
                        # Parse date - you might want to use dateutil.parser for more robust parsing
                        try:
                            from datetime import datetime

                            parsed_date = datetime.strptime(
                                value, "%A, %B %d, %Y"
                            ).date()
                            extracted_data[field] = parsed_date
                        except ValueError:
                            # Try other date formats
                            for date_format in ["%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"]:
                                try:
                                    parsed_date = datetime.strptime(
                                        value, date_format
                                    ).date()
                                    extracted_data[field] = parsed_date
                                    break
                                except ValueError:
                                    continue
                    else:
                        extracted_data[field] = value
                    break

        # Post-process and validate
        extracted_data = self._post_process_extraction(extracted_data, text_clean)

        return extracted_data

    def _post_process_extraction(
        self, data: Dict[str, any], original_text: str
    ) -> Dict[str, any]:
        """Post-process extracted data for better accuracy"""

        # Detect ethics courses
        if "course_name" in data:
            ethics_indicators = [
                "ethics",
                "professional conduct",
                "professional responsibility",
            ]
            course_name_lower = data["course_name"].lower()
            data["is_ethics"] = any(
                indicator in course_name_lower for indicator in ethics_indicators
            )

        # Map field of study variations
        field_mappings = {
            "tax": "Taxes",
            "taxation": "Taxes",
            "audit": "Auditing",
            "accounting": "Accounting",
            "fraud": "Auditing - Fraud",
            "economics": "Economics",
            "hr": "Personnel / Human Resources",
            "human resources": "Personnel / Human Resources",
            "communication": "Communications and Marketing",
        }

        if "field_of_study" in data:
            field_lower = data["field_of_study"].lower()
            for key, mapped_value in field_mappings.items():
                if key in field_lower:
                    data["field_of_study"] = mapped_value
                    break

        # Confidence scoring based on how much data was extracted
        required_fields = [
            "course_name",
            "provider_name",
            "cpe_credits",
            "completion_date",
        ]
        extracted_required = sum(
            1 for field in required_fields if field in data and data[field]
        )
        data["confidence_score"] = extracted_required / len(required_fields)

        return data


class CEBrokerIntegration:
    """Handle CE Broker integration and submissions"""

    def __init__(self, db: Session, api_key: str = None):
        self.db = db
        self.api_key = api_key
        self.base_url = (
            "https://api.cebroker.com"  # Placeholder - update with actual endpoint
        )

    def format_for_ce_broker(self, cpe_record: CPERecord) -> Dict[str, any]:
        """Format CPE record for CE Broker submission"""

        return {
            "course_name": cpe_record.course_name,
            "provider_name": cpe_record.provider_name,
            "hours": float(cpe_record.cpe_credits),
            "completion_date": cpe_record.completion_date.isoformat(),
            "subject_area": cpe_record.field_of_study,
            "delivery_method": cpe_record.delivery_method,
            "sponsor_id": cpe_record.nasba_sponsor_id,
            "certificate_url": cpe_record.certificate_url,
        }

    async def submit_to_ce_broker(self, cpe_record: CPERecord) -> Dict[str, any]:
        """Submit CPE record to CE Broker (placeholder implementation)"""

        # This would be implemented when CE Broker API is available
        submission_data = self.format_for_ce_broker(cpe_record)

        # Placeholder response
        response = {
            "status": "pending",
            "submission_id": f"CB_{cpe_record.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "message": "Submitted to CE Broker successfully",
            "submitted_at": datetime.now(),
        }

        # Update the CPE record
        cpe_record.ce_broker_submitted = True
        cpe_record.ce_broker_submission_date = datetime.now()
        cpe_record.ce_broker_response = response

        self.db.commit()

        return response

    def get_submission_status(self, submission_id: str) -> Dict[str, any]:
        """Check status of CE Broker submission"""
        # Placeholder implementation
        return {
            "submission_id": submission_id,
            "status": "approved",
            "message": "CPE credit approved and recorded",
        }


class ComplianceReportGenerator:
    """Generate compliance reports and summaries"""

    def __init__(self, db: Session):
        self.db = db

    def generate_user_report(
        self, user_id: int, jurisdiction_code: str = None
    ) -> Dict[str, any]:
        """Generate comprehensive compliance report for a user"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        calculator = CPAComplianceCalculator(self.db)
        analytics_calc = CPEAnalyticsCalculator(self.db)

        # Get compliance status
        compliance = calculator.calculate_compliance(user_id, jurisdiction_code)

        # Get analytics
        analytics = analytics_calc.get_user_analytics(user_id)

        # Get recent courses
        recent_courses = (
            self.db.query(CPERecord)
            .filter(CPERecord.user_id == user_id)
            .order_by(CPERecord.completion_date.desc())
            .limit(10)
            .all()
        )

        # Get recommendations
        recommendations = calculator.get_recommendations(user_id, jurisdiction_code)

        report = {
            "user_info": {
                "name": user.full_name,
                "email": user.email,
                "license_number": user.license_number,
                "primary_jurisdiction": user.primary_jurisdiction,
                "next_renewal_date": user.next_renewal_date,
            },
            "compliance_status": compliance,
            "analytics": analytics,
            "recent_courses": [
                {
                    "course_name": course.course_name,
                    "provider_name": course.provider_name,
                    "hours": course.cpe_credits,
                    "completion_date": course.completion_date,
                    "is_ethics": course.is_ethics,
                }
                for course in recent_courses
            ],
            "recommendations": recommendations,
            "generated_at": datetime.now(),
        }

        return report

    def generate_jurisdiction_summary(self, jurisdiction_code: str) -> Dict[str, any]:
        """Generate summary report for a jurisdiction"""

        jurisdiction = (
            self.db.query(CPAJurisdiction)
            .filter(CPAJurisdiction.code == jurisdiction_code)
            .first()
        )

        if not jurisdiction:
            raise ValueError(f"Jurisdiction {jurisdiction_code} not found")

        # Get users in this jurisdiction
        users = (
            self.db.query(User)
            .filter(User.primary_jurisdiction == jurisdiction_code)
            .all()
        )

        calculator = CPAComplianceCalculator(self.db)

        total_users = len(users)
        compliant_users = 0
        total_compliance_percentage = 0

        for user in users:
            try:
                compliance = calculator.calculate_compliance(user.id, jurisdiction_code)
                if compliance.is_compliant:
                    compliant_users += 1
                total_compliance_percentage += compliance.compliance_percentage
            except:
                continue

        average_compliance = (
            total_compliance_percentage / total_users if total_users > 0 else 0
        )
        compliance_rate = compliant_users / total_users if total_users > 0 else 0

        return {
            "jurisdiction": {
                "code": jurisdiction.code,
                "name": jurisdiction.name,
                "requirements": {
                    "total_hours": jurisdiction.general_hours_required,
                    "ethics_hours": jurisdiction.ethics_hours_required,
                    "period_type": jurisdiction.reporting_period_type,
                },
            },
            "statistics": {
                "total_users": total_users,
                "compliant_users": compliant_users,
                "compliance_rate": compliance_rate,
                "average_compliance_percentage": average_compliance,
            },
            "generated_at": datetime.now(),
        }


# Utility functions for common operations
def get_user_compliance_status(
    db: Session, user_id: int, jurisdiction_code: str = None
) -> ComplianceStatusData:
    """Quick function to get user compliance status"""
    calculator = CPAComplianceCalculator(db)
    return calculator.calculate_compliance(user_id, jurisdiction_code)


def validate_cpe_record(db: Session, cpe_record: CPERecord) -> Dict[str, any]:
    """Quick function to validate a CPE record"""
    validator = NASBAValidator(db)
    return validator.validate_cpe_record(cpe_record)


def extract_cpe_from_text(text: str) -> Dict[str, any]:
    """Quick function to extract CPE data from text"""
    extractor = CPECertificateExtractor()
    return extractor.extract_from_text(text)


def calculate_next_renewal_date(
    jurisdiction: CPAJurisdiction, license_issue_date: date
) -> date:
    """Calculate next renewal date based on jurisdiction rules and license issue date"""

    if jurisdiction.reporting_period_type == "annual":
        # Annual renewal - typically December 31st
        next_year = license_issue_date.year + 1
        return date(next_year, 12, 31)

    elif jurisdiction.reporting_period_type == "biennial":
        # Biennial renewal - typically 2 years from issue
        next_renewal_year = license_issue_date.year + 2
        return date(next_renewal_year, license_issue_date.month, license_issue_date.day)

    elif jurisdiction.reporting_period_type == "triennial":
        # Triennial renewal - typically 3 years from issue
        next_renewal_year = license_issue_date.year + 3
        return date(next_renewal_year, license_issue_date.month, license_issue_date.day)

    else:
        # Default to annual
        next_year = license_issue_date.year + 1
        return date(next_year, 12, 31)
