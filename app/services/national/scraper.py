import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List
import openai
import json
from bs4 import BeautifulSoup
import ssl

class RequirementsScraper:
    def __init__(self, openai_api_key: str):
        self.openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
        self.session = None
    
    async def __aenter__(self):
        # Create SSL context that's more permissive for government sites
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=30)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def scrape_state_requirements(self, state_code: str, board_url: str, profession: str) -> Dict:
        """Scrape and extract CPE requirements for a specific state and profession"""
        
        print(f"🔍 Searching for {profession} requirements at {board_url}")
        
        # Try multiple approaches to find CPE content
        html_content = await self.comprehensive_page_search(board_url, profession)
        
        if not html_content:
            return {
                "confidence_score": 0.0,
                "error": "No CPE content found on any searched pages"
            }
        
        # Extract requirements using AI
        requirements = await self.extract_requirements_with_ai(html_content, state_code, profession)
        
        return requirements
    
    async def comprehensive_page_search(self, base_url: str, profession: str) -> str:
        """Comprehensive search for CPE content across multiple URL patterns"""
        
        # More specific URL patterns for NH and other government sites
        url_patterns = [
            f"{base_url}",
            f"{base_url}/",
            f"{base_url}/continuing-education",
            f"{base_url}/cpe",
            f"{base_url}/license-renewal",
            f"{base_url}/renewal-requirements",
            f"{base_url}/accountancy-continuing-professional-education",
            f"{base_url}/cpa-requirements",
            f"{base_url}/professional-development",
            # NH specific patterns
            "https://www.oplc.nh.gov/accountancy-continuing-professional-education",
            "https://www.oplc.nh.gov/accountancy-license-renewal",
            # Try the main OPLC site
            "https://www.oplc.nh.gov/accountancy",
        ]
        
        best_content = ""
        best_score = 0
        
        for url in url_patterns:
            try:
                print(f"  🔍 Trying: {url}")
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        score = self.score_cpe_content(content)
                        
                        print(f"    📊 CPE content score: {score}")
                        
                        if score > best_score:
                            best_content = content
                            best_score = score
                        
                        # If we find good content, we can stop searching
                        if score > 5:
                            print(f"    ✅ Found good CPE content!")
                            break
                            
            except Exception as e:
                print(f"    ❌ Failed to fetch {url}: {str(e)[:100]}")
                continue
        
        print(f"🎯 Best content score: {best_score}")
        return best_content if best_score > 0 else ""
    
    def score_cpe_content(self, html: str) -> int:
        """Score how likely the HTML contains CPE requirements (0-10)"""
        
        if not html:
            return 0
            
        text = BeautifulSoup(html, 'html.parser').get_text().lower()
        
        # CPE-specific scoring
        score = 0
        
        # High-value terms
        high_value_terms = [
            "continuing professional education", "cpe credits", "cpe hours",
            "120 hours", "20 hours", "ethics hours", "renewal requirements"
        ]
        
        for term in high_value_terms:
            if term in text:
                score += 2
                
        # Medium-value terms
        medium_value_terms = [
            "continuing education", "professional development", "license renewal",
            "education hours", "credit hours", "cpe", "nasba"
        ]
        
        for term in medium_value_terms:
            if term in text:
                score += 1
        
        # Bonus for specific numbers that match NH requirements
        if "120" in text and "hours" in text:
            score += 2
        if "20" in text and ("annual" in text or "year" in text):
            score += 2
        if "4" in text and "ethics" in text:
            score += 2
            
        return min(score, 10)  # Cap at 10
    
    async def extract_requirements_with_ai(self, html: str, state: str, profession: str) -> Dict:
        """Use OpenAI to extract structured requirements from HTML"""
        
        if not html:
            return {"confidence_score": 0.0, "error": "No HTML content provided"}
        
        # Clean HTML to text
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        
        # Limit text size for API (keep most relevant parts)
        if len(text) > 6000:
            # Try to find the most relevant section
            text_lower = text.lower()
            
            # Look for sections with CPE content
            cpe_keywords = ["continuing professional education", "cpe", "renewal", "education hours"]
            
            best_section = ""
            for keyword in cpe_keywords:
                if keyword in text_lower:
                    start_idx = max(0, text_lower.find(keyword) - 1000)
                    end_idx = min(len(text), text_lower.find(keyword) + 3000)
                    section = text[start_idx:end_idx]
                    if len(section) > len(best_section):
                        best_section = section
            
            text = best_section if best_section else text[:6000]
        
        prompt = f"""
        Extract CPE requirements for {profession} professionals in {state} from this government website text.
        
        Look specifically for:
        - Total CPE hours required for renewal
        - How often renewal occurs (years)
        - Annual minimum hours required
        - Ethics/professional responsibility hours required
        - Whether CE Broker is mentioned or required
        
        Return ONLY valid JSON with these exact fields:
        {{
            "total_hours_required": number or null,
            "renewal_period_years": number or null,
            "annual_minimum_hours": number or null,
            "ethics_hours_required": number or null,
            "ethics_frequency": "per_cycle" or "annual" or "biennial" or null,
            "ce_broker_required": boolean or null,
            "confidence_score": number (0.0-1.0),
            "source_notes": "brief summary of what was found or why confidence is low"
        }}
        
        Be conservative with confidence_score:
        - 0.9-1.0: Very clear, specific requirements stated
        - 0.7-0.8: Good information but some ambiguity
        - 0.5-0.6: Some relevant info but incomplete
        - 0.0-0.4: Little to no relevant information found
        
        Text to analyze:
        {text}
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting professional licensing requirements from government websites. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean JSON response
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            
            result = json.loads(content)
            
            # Validate the result
            if not isinstance(result.get('confidence_score'), (int, float)):
                result['confidence_score'] = 0.0
                
            return result
            
        except Exception as e:
            return {
                "confidence_score": 0.0,
                "error": f"AI extraction failed: {str(e)}",
                "source_notes": "Error during AI processing"
            }
