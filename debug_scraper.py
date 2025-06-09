import asyncio
import aiohttp
import ssl
from bs4 import BeautifulSoup

async def debug_nh_site():
    print("🔍 Debugging NH CPE website access...")
    
    url = "https://www.oplc.nh.gov/accountancy-continuing-professional-education"
    
    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    timeout = aiohttp.ClientTimeout(total=30)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
            print(f"📡 Fetching: {url}")
            
            async with session.get(url) as response:
                print(f"📊 Status Code: {response.status}")
                print(f"📋 Headers: {dict(response.headers)}")
                
                if response.status == 200:
                    content = await response.text()
                    print(f"📄 Content Length: {len(content)} characters")
                    
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    text = soup.get_text().lower()
                    
                    print(f"📝 Text Length: {len(text)} characters")
                    
                    # Check for key terms
                    key_terms = ["120", "cpe", "continuing", "education", "hours", "ethics", "renewal"]
                    found_terms = []
                    
                    for term in key_terms:
                        if term in text:
                            found_terms.append(term)
                    
                    print(f"🔍 Found terms: {found_terms}")
                    
                    # Show first 500 characters of actual content
                    print(f"\n📄 First 500 characters of content:")
                    print(text[:500])
                    
                    # Search for specific requirements
                    if "120" in text:
                        print("✅ Found '120' in content")
                    if "continuing professional education" in text:
                        print("✅ Found 'continuing professional education' in content")
                    if "ce broker" in text:
                        print("✅ Found 'ce broker' in content")
                        
                else:
                    print(f"❌ Failed to fetch page: Status {response.status}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_nh_site())
