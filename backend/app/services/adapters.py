import httpx
import time
from abc import ABC, abstractmethod
from typing import List
import app.services.taxonomy as taxonomy

class BaseJobAdapter(ABC):
    """
    The blueprint for all external job API connections. 
    """
    @abstractmethod
    def fetch_and_normalize(self) -> List[dict]:
        pass

class JSearchAdapter(BaseJobAdapter):
    """
    Connects to the real JSearch API via RapidAPI to fetch live job postings
    from LinkedIn, Indeed, and Glassdoor, and normalizes them to our database schema.
    """
    def __init__(self, api_key: str, search_query: str = "software engineering intern india"):
        self.api_key = api_key
        self.search_query = search_query
        self.url = "https://jsearch.p.rapidapi.com/search"

    def fetch_and_normalize(self) -> List[dict]:
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        
        querystring = {
            "query": self.search_query,
            "page": "1",
            "num_pages": "1"
        }

        raw_data = []
        max_retries = 3
        
        # --- NEW ROBUST RETRY ENGINE ---
        for attempt in range(max_retries):
            try:
                # Pre-flight pause to guarantee we don't spam the API
                time.sleep(2) 
                
                response = httpx.get(self.url, headers=headers, params=querystring, timeout=15.0)
                
                # If RapidAPI says we are going too fast, catch it and wait
                if response.status_code == 429:
                    wait_time = 5 * (attempt + 1)
                    print(f"⚠️ Rate limited by RapidAPI! Sleeping for {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue 
                    
                response.raise_for_status()
                raw_data = response.json().get("data", [])
                
                # If we made it here, the request was successful! Break out of the retry loop.
                break 
                
            except Exception as e:
                print(f"JSearch API Error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    print("❌ Max retries reached. Giving up on this query.")
                    return []
        # -------------------------------

        normalized_jobs = []

        # Normalize the messy API data into our strict Opportunity schema
        for job in raw_data:
            if not job.get("job_apply_link"):
                continue

            city = job.get("job_city", "")
            state = job.get("job_state", "")
            country = job.get("job_country", "")
            location = f"{city}, {state}, {country}".strip(", ")

            normalized_job = {
                "source": "JSearch (LinkedIn/Indeed)",
                "opportunity_type": "Internship" if "intern" in job.get("job_title", "").lower() else "Full-Time",
                "title": job.get("job_title", "Unknown Title")[:250],
                "company": job.get("employer_name", "Unknown Company")[:250],
                "location": location if location else "Remote",
                "application_url": job.get("job_apply_link"),
                "description": job.get("job_description", "No description provided."),
                "required_experience": f"Min: {job.get('job_required_experience', {}).get('required_experience_in_months', 0)} months",
                "stipend": None,
                "is_remote": (
                    "remote" in location.lower() or
                    "remote" in job.get("job_title", "").lower() or
                    "remote" in job.get("job_description", "").lower()
                ),
                "deadline_date": None,
                "required_skills": taxonomy.extract_skills_from_text(job.get("job_description", "")),
                "preferred_skills": [],
                "allowed_branches": [], 
                "allowed_batches": [],  
                "min_cgpa": 0.0
            }
            normalized_jobs.append(normalized_job)

        return normalized_jobs
    
import xml.etree.ElementTree as ET

class DevpostHackathonAdapter(BaseJobAdapter):
    """
    Pulls live hackathons from Devpost. 
    Since they lack an open JSON API, this parses their public software feeds or RSS.
    """
    def __init__(self):
        # We target specific tags or feeds
        self.url = "https://devpost.com/hackathons.rss"

    def fetch_and_normalize(self) -> List[dict]:
        normalized_jobs = []
        try:
            # Note: For production, you often need an HTML scraper (like BeautifulSoup) 
            # for Devpost as their RSS can be limited, but the translation logic remains identical.
            # Spoof a standard web browser to bypass basic anti-bot protections
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/rss+xml"
            }
            response = httpx.get(self.url, headers=headers, timeout=15.0)
            response.raise_for_status()
            
            # Simulated parsing logic for hackathon feeds
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:10]: # Process top 10 recent
                title = item.find('title').text
                link = item.find('link').text
                description = item.find('description').text
                
                normalized_job = {
                    "source": "Devpost",
                    "opportunity_type": "Hackathon",
                    "title": title[:250],
                    "company": "Various Sponsors",
                    "location": "Remote / Hybrid", # Hackathons are mostly online
                    "application_url": link,
                    "description": description,
                    "required_experience": "0 years",
                    "stipend": None,
                   
                    # "is_remote": (
                    #     "remote" in location.lower()
                    #     or
                    #     "remote" in job.get(
                    #         "job_title",
                    #         ""
                    #     ).lower()
                    #     or
                    #     "remote" in job.get(
                    #         "job_description",
                    #         ""
                    #     ).lower()
                    # ),
                    "deadline_date": None,
                    "required_skills": [],  
                    "preferred_skills": [],
                    "allowed_branches": [], # Hackathons are typically open to all
                    "allowed_batches": [],  
                    "min_cgpa": 0.0
                }
                normalized_jobs.append(normalized_job)
                
        except Exception as e:
            print(f"Devpost Sync Error: {e}")
            
        return normalized_jobs