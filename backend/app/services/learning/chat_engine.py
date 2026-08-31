"""
chat_engine.py
==============
What this file does:
  Provides AI-powered conversational learner profiling. Accepts user messages
  describing their learning goals, extracts structured learner profile data.

Overall design:
  Uses Google Gemini API via the existing llm_gateway pattern. Takes conversation
  history + latest user message, returns both a human response and extracted
  structured profile data (goals, current skills, experience level).

Elements:
  ChatMessage          dataclass — single message in conversation
  LearnerProfileDraft  dataclass — extracted profile data from conversation
  ChatEngine           class — main conversation handler
  extract_profile()    function — parse Gemini response into structured data

Final output:
  ChatResponse with AI message + LearnerProfileDraft
"""
import os
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from google import genai
from pydantic import BaseModel

@dataclass
class ChatMessage:
    role: str
    content: str

@dataclass
class LearnerProfileDraft:
    goal_statement: str
    current_skills: List[str]
    experience_level: str
    weekly_hours: int
    interests: List[str]

class ChatEngine:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        
    def process_message(self, message: str, history: List[Dict[str, str]]) -> tuple[str, Optional[LearnerProfileDraft], bool]:
        if not self.client:
            return "Please provide your current skills, goals, and weekly study hours to proceed.", None, False
            
        system_prompt = \"\"\"
        You are an AI career and learning advisor. Your goal is to profile the learner.
        You need to extract:
        1. Their learning goals
        2. Their current skills and experience level (beginner/intermediate/advanced)
        3. Weekly study hours they can commit to
        4. Any specific interests

        If you don't have all this information, ask follow-up questions politely.
        If you have all the information, format your response in JSON with two keys:
        - "response": Your friendly conversational reply to the user.
        - "profile": null if incomplete, OR a JSON object with keys: goal_statement, current_skills (array), experience_level, weekly_hours (int), interests (array).
        
        Always return ONLY valid JSON.
        \"\"\"
        
        contents = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in history]
        contents.append({"role": "user", "parts": [{"text": message}]})
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                )
            )
            
            data = json.loads(response.text)
            reply = data.get("response", "I'm here to help you build a learning path.")
            profile_data = data.get("profile")
            
            draft = None
            is_complete = False
            if profile_data:
                draft = LearnerProfileDraft(
                    goal_statement=profile_data.get("goal_statement", ""),
                    current_skills=profile_data.get("current_skills", []),
                    experience_level=profile_data.get("experience_level", "beginner"),
                    weekly_hours=profile_data.get("weekly_hours", 10),
                    interests=profile_data.get("interests", [])
                )
                is_complete = True
                
            return reply, draft, is_complete
            
        except Exception as e:
            return "Could you tell me more about your skills and goals?", None, False

def extract_profile(response_text: str) -> Optional[LearnerProfileDraft]:
    # Handled inside process_message
    pass
