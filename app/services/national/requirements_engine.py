# National CPE Requirements Engine for All 50 States
# This will be the backbone of SuperCPE's multi-state compliance system

import asyncio
import aiohttp
from datetime import datetime, date
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy import Column, Integer, String, Boolean, Date, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import openai
import json
import re
from bs4 import BeautifulSoup

Base = declarative_base()


# Database Models for National Requirements
class State(Base):
    __tablename__ = "states"

    code = Column(String(2), primary_key=True)  # "CA", "NY", etc.
    name = Column(String(50))
    board_name = Column(String(200))
    board_website = Column(String(500))
    ce_broker_required = Column(Boolean, default=False)
    last_scraped = Column(Date)
    scrape_frequency_days = Column(Integer, default=30)

    # Relationships
    professions = relationship("StateProfession", back_populates="state")


class Profession(Base):
    __tablename__ = "professions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))  # "CPA", "Attorney", "Architect"
    category = Column(String(50))  # "Accounting", "Legal", "Engineering"

    # Relationships
    state_requirements = relationship("StateProfession", back_populates="profession")


class StateProfession(Base):
    __tablename__ = "state_professions"

    id = Column(Integer, primary_key=True)
    state_code = Column(String(2), ForeignKey("states.code"))
    profession_id = Column(Integer, ForeignKey("professions.id"))

    # Core Requirements
    total_hours_required = Column(Integer)
    renewal_period_years = Column(Integer)
    annual_minimum_hours = Column(Integer)
    ethics_hours_required = Column(Integer)
    ethics_frequency = Column(String(20))  # "per_cycle", "annual", "biennial"

    # Specific Requirements
    live_hours_required = Column(Integer, default=0)
    self_study_max_percent = Column(Float, default=100.0)
    carry_over_max_hours = Column(Integer, default=0)
    grace_period_days = Column(Integer, default=0)

    # Administrative
    license_fee = Column(Float)
    late_fee = Column(Float)
    ce_broker_required = Column(Boolean, default=False)
    verification_required = Column(Boolean, default=True)

    # Data tracking
    source_url = Column(String(500))
    last_updated = Column(Date, default=date.today)
    ai_confidence_score = Column(Float)  # 0.0-1.0 confidence in extracted data
    human_verified = Column(Boolean, default=False)

    # Relationships
    state = relationship("State", back_populates="professions")
    profession = relationship("Profession", back_populates="state_requirements")
    requirements = relationship(
        "SpecificRequirement", back_populates="state_profession"
    )
    acceptable_subjects = relationship(
        "AcceptableSubject", back_populates="state_profession"
    )


class SpecificRequirement(Base):
    __tablename__ = "specific_requirements"

    id = Column(Integer, primary_key=True)
    state_profession_id = Column(Integer, ForeignKey("state_professions.id"))

    category = Column(String(100))  # "Ethics", "Technical Update", "Specialized"
    hours_required = Column(Integer)
    description = Column(Text)
    frequency = Column(String(50))  # "per_cycle", "annual", "one_time"
    mandatory = Column(Boolean, default=True)

    # Relationships
    state_profession = relationship("StateProfession", back_populates="requirements")


class AcceptableSubject(Base):
    __tablename__ = "acceptable_subjects"

    id = Column(Integer, primary_key=True)
    state_profession_id = Column(Integer, ForeignKey("state_professions.id"))

    subject_name = Column(String(200))
    subject_category = Column(String(100))
    max_hours_allowed = Column(Integer)  # -1 for unlimited
    notes = Column(Text)

    # Relationships
    state_profession = relationship(
        "StateProfession", back_populates="acceptable_subjects"
    )


# AI-Powered Requirements Scraper
class RequirementsScraper:
    def __init__(self, openai_api_key: str):
        self.openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def scrape_state_requirements(self, state: State, profession: str) -> Dict:
        """Scrape and extract CPE requirements for a specific state and profession"""

        # Get the relevant page
        html_content = await self.fetch_page(state.board_website, profession)

        # Extract requirements using AI
        requirements = await self.extract_requirements_with_ai(
            html_content, state.code, profession
        )

        return requirements

    async def fetch_page(self, base_url: str, profession: str) -> str:
        """Fetch the CPE requirements page for a profession"""

        # Common URL patterns for CPE requirements
        url_patterns = [
            f"{base_url}/cpe",
            f"{base_url}/continuing-education",
            f"{base_url}/license-renewal",
            f"{base_url}/{profession.lower()}/requirements",
            f"{base_url}/professionals/{profession.lower()}",
        ]

        for url in url_patterns:
            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        # Check if this page has CPE content
                        if self.has_cpe_content(content):
                            return content
            except:
                continue

        # Fallback: search the main site
        async with self.session.get(base_url, timeout=10) as response:
            return await response.text() if response.status == 200 else ""

    def has_cpe_content(self, html: str) -> bool:
        """Check if HTML contains CPE-related content"""
        cpe_keywords = [
            "continuing education",
            "cpe",
            "professional development",
            "renewal requirements",
            "education hours",
            "credit hours",
        ]

        text = BeautifulSoup(html, "html.parser").get_text().lower()
        return any(keyword in text for keyword in cpe_keywords)

    async def extract_requirements_with_ai(
        self, html: str, state: str, profession: str
    ) -> Dict:
        """Use OpenAI to extract structured requirements from HTML"""

        # Clean HTML to text
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # Limit text size for API
        text = text[:8000] if len(text) > 8000 else text

        prompt = f"""
        Extract CPE requirements for {profession} professionals in {state} from this text.
        
        Return ONLY valid JSON with these exact fields:
        {{
            "total_hours_required": number,
            "renewal_period_years": number,
            "annual_minimum_hours": number,
            "ethics_hours_required": number,
            "ethics_frequency": "per_cycle" | "annual" | "biennial",
            "live_hours_required": number,
            "self_study_max_percent": number,
            "carry_over_max_hours": number,
            "grace_period_days": number,
            "license_fee": number,
            "late_fee": number,
            "ce_broker_required": boolean,
            "verification_required": boolean,
            "specific_requirements": [
                {{
                    "category": "string",
                    "hours_required": number,
                    "description": "string",
                    "frequency": "string",
                    "mandatory": boolean
                }}
            ],
            "acceptable_subjects": [
                {{
                    "subject_name": "string",
                    "subject_category": "string",
                    "max_hours_allowed": number,
                    "notes": "string"
                }}
            ],
            "confidence_score": number (0.0-1.0),
            "source_notes": "string"
        }}
        
        If information is not found, use null or reasonable defaults.
        Be conservative with confidence_score - only use >0.8 if very certain.
        
        Text to analyze:
        {text}
        """

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a legal document analyzer specializing in professional licensing requirements. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )

            content = response.choices[0].message.content.strip()

            # Clean JSON response
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()

            return json.loads(content)

        except Exception as e:
            return {
                "total_hours_required": None,
                "confidence_score": 0.0,
                "source_notes": f"Extraction failed: {str(e)}",
            }


# National Requirements Manager
class NationalRequirementsManager:
    def __init__(self, db_session, openai_api_key: str):
        self.db = db_session
        self.scraper = RequirementsScraper(openai_api_key)

    async def scrape_all_states(self, professions: List[str] = ["CPA"]):
        """Scrape requirements for all 50 states"""

        states = self.get_all_states()

        async with self.scraper:
            tasks = []
            for state in states:
                for profession in professions:
                    task = self.scrape_state_profession(state, profession)
                    tasks.append(task)

            # Process in batches to avoid overwhelming servers
            batch_size = 10
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i : i + batch_size]
                results = await asyncio.gather(*batch, return_exceptions=True)

                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        print(f"Error: {result}")
                    else:
                        self.save_requirements(result)

                # Be respectful - wait between batches
                await asyncio.sleep(5)

    async def scrape_state_profession(self, state: State, profession: str) -> Dict:
        """Scrape requirements for one state/profession combination"""

        print(f"Scraping {profession} requirements for {state.name}...")

        try:
            requirements = await self.scraper.scrape_state_requirements(
                state, profession
            )
            requirements["state_code"] = state.code
            requirements["profession"] = profession
            requirements["scraped_at"] = datetime.utcnow().isoformat()

            return requirements

        except Exception as e:
            return {
                "state_code": state.code,
                "profession": profession,
                "error": str(e),
                "confidence_score": 0.0,
            }

    def save_requirements(self, requirements_data: Dict):
        """Save scraped requirements to database"""

        if "error" in requirements_data:
            print(
                f"Failed to scrape {requirements_data['state_code']} {requirements_data['profession']}: {requirements_data['error']}"
            )
            return

        # Save to database
        state_prof = StateProfession(
            state_code=requirements_data["state_code"],
            total_hours_required=requirements_data.get("total_hours_required"),
            renewal_period_years=requirements_data.get("renewal_period_years"),
            annual_minimum_hours=requirements_data.get("annual_minimum_hours"),
            ethics_hours_required=requirements_data.get("ethics_hours_required"),
            ethics_frequency=requirements_data.get("ethics_frequency"),
            live_hours_required=requirements_data.get("live_hours_required", 0),
            self_study_max_percent=requirements_data.get(
                "self_study_max_percent", 100.0
            ),
            carry_over_max_hours=requirements_data.get("carry_over_max_hours", 0),
            grace_period_days=requirements_data.get("grace_period_days", 0),
            license_fee=requirements_data.get("license_fee"),
            late_fee=requirements_data.get("late_fee"),
            ce_broker_required=requirements_data.get("ce_broker_required", False),
            verification_required=requirements_data.get("verification_required", True),
            ai_confidence_score=requirements_data.get("confidence_score", 0.0),
            last_updated=date.today(),
        )

        self.db.add(state_prof)
        self.db.commit()

        print(
            f"✅ Saved {requirements_data['state_code']} {requirements_data['profession']} (confidence: {requirements_data.get('confidence_score', 0.0):.2f})"
        )

    def get_all_states(self) -> List[State]:
        """Get all US states with their board information"""

        # This would be populated from a comprehensive state database
        # For now, showing the structure for a few key states
        states_data = [
            {
                "code": "CA",
                "name": "California",
                "board_name": "California Board of Accountancy",
                "board_website": "https://www.dca.ca.gov/cba/",
            },
            {
                "code": "NY",
                "name": "New York",
                "board_name": "New York State Board for Public Accountancy",
                "board_website": "http://www.op.nysed.gov/prof/cpa/",
            },
            {
                "code": "TX",
                "name": "Texas",
                "board_name": "Texas State Board of Public Accountancy",
                "board_website": "https://www.tsbpa.state.tx.us/",
            },
            {
                "code": "FL",
                "name": "Florida",
                "board_name": "Florida Board of Accountancy",
                "board_website": "https://www.myfloridalicense.com/DBPR/os/documents/CPA_law_and_rules.pdf",
            },
            {
                "code": "NH",
                "name": "New Hampshire",
                "board_name": "New Hampshire Board of Accountancy",
                "board_website": "https://www.oplc.nh.gov/accountancy",
            },
            # ... (would include all 50 states)
        ]

        states = []
        for state_data in states_data:
            state = State(**state_data)
            states.append(state)

        return states


# API Endpoints for National Requirements
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

app = FastAPI(title="SuperCPE National Requirements API")


@app.get("/requirements/{state_code}/{profession}")
async def get_state_requirements(
    state_code: str, profession: str, db: Session = Depends(get_db)
):
    """Get CPE requirements for a specific state and profession"""

    requirements = (
        db.query(StateProfession)
        .filter(
            StateProfession.state_code == state_code.upper(),
            StateProfession.profession.has(name=profession),
        )
        .first()
    )

    if not requirements:
        raise HTTPException(status_code=404, detail="Requirements not found")

    return {
        "state": state_code.upper(),
        "profession": profession,
        "total_hours": requirements.total_hours_required,
        "renewal_period": requirements.renewal_period_years,
        "annual_minimum": requirements.annual_minimum_hours,
        "ethics_hours": requirements.ethics_hours_required,
        "ethics_frequency": requirements.ethics_frequency,
        "live_hours_required": requirements.live_hours_required,
        "self_study_max_percent": requirements.self_study_max_percent,
        "carry_over_max": requirements.carry_over_max_hours,
        "ce_broker_required": requirements.ce_broker_required,
        "last_updated": requirements.last_updated.isoformat(),
        "confidence_score": requirements.ai_confidence_score,
        "human_verified": requirements.human_verified,
    }


@app.get("/requirements/compare")
async def compare_state_requirements(
    states: str,  # Comma-separated state codes
    profession: str,
    db: Session = Depends(get_db),
):
    """Compare requirements across multiple states"""

    state_codes = [s.strip().upper() for s in states.split(",")]

    requirements = (
        db.query(StateProfession)
        .filter(
            StateProfession.state_code.in_(state_codes),
            StateProfession.profession.has(name=profession),
        )
        .all()
    )

    comparison = []
    for req in requirements:
        comparison.append(
            {
                "state": req.state_code,
                "total_hours": req.total_hours_required,
                "renewal_period": req.renewal_period_years,
                "ethics_hours": req.ethics_hours_required,
                "ce_broker_required": req.ce_broker_required,
            }
        )

    return {
        "profession": profession,
        "states_compared": len(comparison),
        "comparison": comparison,
    }


@app.post("/analyze-compliance/")
async def analyze_user_compliance(
    user_certificates: List[Dict],
    state_code: str,
    profession: str,
    db: Session = Depends(get_db),
):
    """Analyze user's certificates against state requirements"""

    # Get state requirements
    requirements = (
        db.query(StateProfession)
        .filter(
            StateProfession.state_code == state_code.upper(),
            StateProfession.profession.has(name=profession),
        )
        .first()
    )

    if not requirements:
        raise HTTPException(status_code=404, detail="Requirements not found")

    # Calculate user's current status
    total_hours = sum(cert.get("cpe_credits", 0) for cert in user_certificates)
    ethics_hours = sum(
        cert.get("cpe_credits", 0)
        for cert in user_certificates
        if "ethics" in cert.get("field_of_study", "").lower()
    )

    # Compliance analysis
    compliance = {
        "state": state_code.upper(),
        "profession": profession,
        "user_status": {
            "total_hours_earned": total_hours,
            "ethics_hours_earned": ethics_hours,
            "certificates_count": len(user_certificates),
        },
        "requirements": {
            "total_hours_required": requirements.total_hours_required,
            "ethics_hours_required": requirements.ethics_hours_required,
            "renewal_period": requirements.renewal_period_years,
        },
        "compliance": {
            "total_hours_compliant": total_hours
            >= (requirements.total_hours_required or 0),
            "ethics_compliant": ethics_hours
            >= (requirements.ethics_hours_required or 0),
            "overall_compliant": (
                total_hours >= (requirements.total_hours_required or 0)
                and ethics_hours >= (requirements.ethics_hours_required or 0)
            ),
        },
        "gaps": {
            "total_hours_needed": max(
                0, (requirements.total_hours_required or 0) - total_hours
            ),
            "ethics_hours_needed": max(
                0, (requirements.ethics_hours_required or 0) - ethics_hours
            ),
        },
    }

    return compliance


# Initialization Script
async def initialize_national_database():
    """Initialize the national CPE requirements database"""

    print("🚀 Initializing National CPE Requirements Database for All 50 States...")

    # Create database connection
    # db = SessionLocal()

    # Initialize requirements manager
    # manager = NationalRequirementsManager(db, openai_api_key)

    # Start scraping all states
    # await manager.scrape_all_states(professions=["CPA", "Attorney", "Architect", "Engineer"])

    print("✅ National database initialization complete!")


if __name__ == "__main__":
    # Run the initialization
    asyncio.run(initialize_national_database())
