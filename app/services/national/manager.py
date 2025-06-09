import asyncio
from datetime import datetime, date
from typing import List, Dict
from .scraper import RequirementsScraper
from .state_data import get_all_states
from app.models import State, StateProfession, ProfessionNational  # Updated import
from sqlalchemy.orm import Session

class NationalRequirementsManager:
    def __init__(self, db_session: Session, openai_api_key: str):
        self.db = db_session
        self.openai_api_key = openai_api_key
    
    async def scrape_all_states_for_profession(self, profession: str = "CPA"):
        """Scrape requirements for all 50 states for a specific profession"""
        
        print(f"🚀 Starting national scrape for {profession} across all 50 states...")
        
        all_states = get_all_states()
        
        async with RequirementsScraper(self.openai_api_key) as scraper:
            successful = 0
            failed = 0
            
            for state_code, state_info in all_states.items():
                try:
                    print(f"📄 Scraping {state_info['name']} ({state_code})...")
                    
                    requirements = await scraper.scrape_state_requirements(
                        state_code=state_code,
                        board_url=state_info['cpa_board'],
                        profession=profession
                    )
                    
                    # Save to database
                    self.save_requirements(state_code, profession, requirements)
                    
                    if requirements.get('confidence_score', 0) > 0.5:
                        successful += 1
                        print(f"✅ {state_info['name']}: Confidence {requirements.get('confidence_score', 0):.2f}")
                    else:
                        failed += 1
                        print(f"⚠️ {state_info['name']}: Low confidence {requirements.get('confidence_score', 0):.2f}")
                    
                    # Be respectful to servers
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    failed += 1
                    print(f"❌ {state_info['name']}: Error - {str(e)}")
            
            print(f"\n🎯 Scraping complete!")
            print(f"✅ Successful: {successful}")
            print(f"❌ Failed/Low confidence: {failed}")
            print(f"📊 Total states processed: {len(all_states)}")
    
    def save_requirements(self, state_code: str, profession: str, requirements_data: Dict):
        """Save scraped requirements to database"""
        
        # Check if record already exists
        existing = self.db.query(StateProfession).filter(
            StateProfession.state_code == state_code
        ).first()
        
        if existing:
            # Update existing record
            for key, value in requirements_data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.last_updated = date.today()
        else:
            # Create new record
            state_prof = StateProfession(
                state_code=state_code,
                total_hours_required=requirements_data.get('total_hours_required'),
                renewal_period_years=requirements_data.get('renewal_period_years'),
                annual_minimum_hours=requirements_data.get('annual_minimum_hours'),
                ethics_hours_required=requirements_data.get('ethics_hours_required'),
                ethics_frequency=requirements_data.get('ethics_frequency'),
                live_hours_required=requirements_data.get('live_hours_required', 0),
                carry_over_max_hours=requirements_data.get('carry_over_max_hours', 0),
                ce_broker_required=requirements_data.get('ce_broker_required', False),
                ai_confidence_score=requirements_data.get('confidence_score', 0.0),
                last_updated=date.today(),
                human_verified=False
            )
            self.db.add(state_prof)
        
        self.db.commit()
