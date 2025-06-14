"""
CE Broker Automated Reporting Service
Handles the complete 11-step submission process
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, date
import json
import asyncio
from enum import Enum
from sqlalchemy.orm import Session

class CEBrokerCategory(str, Enum):
    GENERAL_CPE = "General CPE"
    PROFESSIONAL_ETHICS = "Professional Ethics CPE"
    UNIVERSITY_COLLEGE = "University or college courses"
    AUTHORING = "Authoring articles, books, or other publications"
    PRESENTING = "Presenting, lecturing, or instructing"

class CEBrokerCourseType(str, Enum):
    LIVE = "Live (Involves live interaction with presenter/host)"
    COMPUTER_BASED = "Computer-Based Training (ie: online courses)"
    CORRESPONDENCE = "Correspondence"
    PRERECORDED = "Prerecorded Broadcast"

class CEBrokerSubject(str, Enum):
    PUBLIC_ACCOUNTING = "Public accounting"
    GOVERNMENTAL_ACCOUNTING = "Governmental accounting"
    PUBLIC_AUDITING = "Public auditing"
    GOVERNMENTAL_AUDITING = "Governmental auditing"
    ADMINISTRATIVE_PRACTICES = "Administrative practices"
    SOCIAL_ENVIRONMENT = "Social environment of business"
    BUSINESS_LAW = "Business law"
    BUSINESS_MANAGEMENT = "Business management and organization"
    FINANCE = "Finance"
    MANAGEMENT_ADVISORY = "Management advisory services"
    MARKETING = "Marketing"
    COMMUNICATIONS = "Communications"
    PERSONAL_DEVELOPMENT = "Personal development"
    PERSONNEL_HR = "Personnel and human resources"
    COMPUTER_SCIENCE = "Computer science"
    ECONOMICS = "Economics"
    MATHEMATICS = "Mathematics"
    PRODUCTION = "Production"
    SPECIALIZED_KNOWLEDGE = "Specialized knowledge and its application"
    STATISTICS = "Statistics"
    TAXES = "Taxes"

@dataclass
class CEBrokerSubmission:
    """Complete CE Broker submission data"""
    # Step 1: Category Selection
    category: CEBrokerCategory
    
    # Step 2: Course Details
    completion_date: date
    course_type: CEBrokerCourseType
    hours: float
    
    # Step 3: Course Information
    course_name: str
    provider_name: str
    subjects: List[CEBrokerSubject]
    
    # Step 4: File Attachment
    certificate_file_path: Optional[str] = None
    certificate_file_url: Optional[str] = None
    
    # Metadata
    cpe_record_id: Optional[int] = None
    submission_id: Optional[str] = None
    submitted_at: Optional[datetime] = None

class CEBrokerMappingService:
    """Maps SuperCPE data to CE Broker format"""
    
    # Mapping from SuperCPE field_of_study to CE Broker subjects
    FIELD_TO_SUBJECT_MAPPING = {
        "Taxes": [CEBrokerSubject.TAXES],
        "Tax": [CEBrokerSubject.TAXES],
        "Accounting": [CEBrokerSubject.PUBLIC_ACCOUNTING],
        "Auditing": [CEBrokerSubject.PUBLIC_AUDITING],
        "Auditing - Fraud": [CEBrokerSubject.PUBLIC_AUDITING, CEBrokerSubject.ADMINISTRATIVE_PRACTICES],
        "Economics": [CEBrokerSubject.ECONOMICS],
        "Personnel / Human Resources": [CEBrokerSubject.PERSONNEL_HR],
        "Communications and Marketing": [CEBrokerSubject.COMMUNICATIONS, CEBrokerSubject.MARKETING],
        "General": [CEBrokerSubject.PUBLIC_ACCOUNTING],  # Default
    }
    
    # Mapping from SuperCPE delivery_method to CE Broker course_type
    DELIVERY_TO_TYPE_MAPPING = {
        "QAS Self-Study": CEBrokerCourseType.COMPUTER_BASED,
        "Self-Study": CEBrokerCourseType.COMPUTER_BASED,
        "Online": CEBrokerCourseType.COMPUTER_BASED,
        "Webinar": CEBrokerCourseType.LIVE,
        "Live": CEBrokerCourseType.LIVE,
        "Correspondence": CEBrokerCourseType.CORRESPONDENCE,
    }
    
    @classmethod
    def map_cpe_record_to_submission(cls, cpe_record, certificate_url: str = None) -> CEBrokerSubmission:
        """Convert a CPE record to CE Broker submission format"""
        
        # Determine category based on ethics flag
        category = (
            CEBrokerCategory.PROFESSIONAL_ETHICS 
            if cpe_record.is_ethics 
            else CEBrokerCategory.GENERAL_CPE
        )
        
        # Map delivery method to course type
        course_type = cls.DELIVERY_TO_TYPE_MAPPING.get(
            cpe_record.delivery_method or "QAS Self-Study",
            CEBrokerCourseType.COMPUTER_BASED
        )
        
        # Map field of study to subjects
        subjects = cls.FIELD_TO_SUBJECT_MAPPING.get(
            cpe_record.field_of_study or "General",
            [CEBrokerSubject.PUBLIC_ACCOUNTING]
        )
        
        return CEBrokerSubmission(
            category=category,
            completion_date=cpe_record.completion_date or date.today(),
            course_type=course_type,
            hours=float(cpe_record.cpe_credits),
            course_name=cpe_record.course_name or "Unknown Course",
            provider_name=cpe_record.provider_name or "Professional Education Services",
            subjects=subjects,
            certificate_file_url=certificate_url or cpe_record.certificate_url,
            cpe_record_id=cpe_record.id
        )

class CEBrokerReportGenerator:
    """Generates detailed reports for CE Broker submission"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def generate_submission_report(self, submissions: List[CEBrokerSubmission]) -> Dict:
        """Generate a comprehensive CE Broker submission report"""
        
        if not submissions:
            return {
                "status": "no_data",
                "message": "No certificates available for CE Broker submission"
            }
        
        # Calculate totals
        total_hours = sum(sub.hours for sub in submissions)
        ethics_hours = sum(
            sub.hours for sub in submissions 
            if sub.category == CEBrokerCategory.PROFESSIONAL_ETHICS
        )
        
        # Group by category
        by_category = {}
        for submission in submissions:
            cat = submission.category.value
            if cat not in by_category:
                by_category[cat] = {"count": 0, "hours": 0, "submissions": []}
            by_category[cat]["count"] += 1
            by_category[cat]["hours"] += submission.hours
            by_category[cat]["submissions"].append(submission)
        
        # Group by subject
        subject_summary = {}
        for submission in submissions:
            for subject in submission.subjects:
                subject_name = subject.value
                if subject_name not in subject_summary:
                    subject_summary[subject_name] = {"count": 0, "hours": 0}
                subject_summary[subject_name]["count"] += 1
                subject_summary[subject_name]["hours"] += submission.hours
        
        return {
            "status": "success",
            "summary": {
                "total_submissions": len(submissions),
                "total_hours": total_hours,
                "ethics_hours": ethics_hours,
                "general_hours": total_hours - ethics_hours,
                "report_generated": datetime.now().isoformat()
            },
            "by_category": by_category,
            "subject_summary": subject_summary,
            "submissions": [self._format_submission_for_report(sub) for sub in submissions],
            "ce_broker_instructions": self._get_submission_instructions()
        }
    
    def _format_submission_for_report(self, submission: CEBrokerSubmission) -> Dict:
        """Format a single submission for the report"""
        return {
            "cpe_record_id": submission.cpe_record_id,
            "category": submission.category.value,
            "course_name": submission.course_name,
            "provider_name": submission.provider_name,
            "completion_date": submission.completion_date.strftime("%m/%d/%Y"),
            "hours": submission.hours,
            "course_type": submission.course_type.value,
            "subjects": [subject.value for subject in submission.subjects],
            "has_certificate": bool(submission.certificate_file_url),
            "certificate_url": submission.certificate_file_url
        }
    
    def _get_submission_instructions(self) -> Dict:
        """Get step-by-step CE Broker submission instructions"""
        return {
            "overview": "11-step process to submit CPE credits to CE Broker",
            "steps": [
                {
                    "step": 1,
                    "title": "Sign In",
                    "description": "Log into your CE Broker account",
                    "action": "Navigate to cebroker.com and sign in"
                },
                {
                    "step": 2,
                    "title": "Select Report CE",
                    "description": "Click the 'Report CE' button",
                    "action": "Look for the Report CE button in your dashboard"
                },
                {
                    "step": 3,
                    "title": "Choose Category",
                    "description": "Select the appropriate CE category",
                    "action": "Choose from: General CPE, Professional Ethics CPE, etc.",
                    "automation_note": "SuperCPE automatically determines category based on course content"
                },
                {
                    "step": 4,
                    "title": "Click Report",
                    "description": "Click the REPORT button for your selected category",
                    "action": "Click the blue REPORT button"
                },
                {
                    "step": 5,
                    "title": "Course Details",
                    "description": "Enter completion date, course type, and hours",
                    "action": "Fill in the course detail form",
                    "automation_note": "SuperCPE provides pre-filled data"
                },
                {
                    "step": 6,
                    "title": "Enter Course Name",
                    "description": "Question 1 of 3: What is the name of the CE course?",
                    "action": "Enter the complete course name",
                    "automation_note": "Extracted from your certificate"
                },
                {
                    "step": 7,
                    "title": "Enter Provider Name",
                    "description": "Question 2 of 3: What is the name of the educational provider?",
                    "action": "Enter provider name (usually Professional Education Services)",
                    "automation_note": "Extracted from your certificate"
                },
                {
                    "step": 8,
                    "title": "Choose Subjects",
                    "description": "Question 3 of 3: Which subject(s) did this course deal with?",
                    "action": "Select appropriate checkboxes",
                    "automation_note": "SuperCPE automatically maps course content to CE Broker subjects"
                },
                {
                    "step": 9,
                    "title": "Attach Certificate",
                    "description": "Upload your certificate of completion",
                    "action": "Click ATTACH DOCUMENT and upload your PDF",
                    "automation_note": "SuperCPE provides direct download links"
                },
                {
                    "step": 10,
                    "title": "Review and Certify",
                    "description": "Review all information and certify accuracy",
                    "action": "Check 'I hereby certify the answers are true and correct'"
                },
                {
                    "step": 11,
                    "title": "Submit CPE",
                    "description": "Final submission",
                    "action": "Click SUBMIT CE to complete the process"
                }
            ],
            "tips": [
                "Use SuperCPE's auto-generated data to speed up the process",
                "Double-check course names and provider information",
                "Ensure certificate files are under 16 MB",
                "Keep records of submission confirmations"
            ]
        }
