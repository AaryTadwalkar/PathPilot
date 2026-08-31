"""
chat_engine.py
==============
What this file does:
  Provides AI-powered conversational learner profiling. Accepts user messages
  describing their learning goals, extracts structured learner profile data.

Overall design:
  Uses Google Gemini API. Takes conversation history + latest user message,
  returns both a human response and extracted structured profile data
  (goals, current skills, experience level, weekly hours).

Elements:
  ChatMessage          dataclass -- single message in conversation
  LearnerProfileDraft  dataclass -- extracted profile data from conversation
  ChatEngine           class -- main conversation handler
  extract_profile()    function -- parse Gemini response into structured data

Final output:
  Tuple (reply_text, LearnerProfileDraft_or_None, is_complete_bool)
"""
import os
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from google import genai

SYSTEM_PROMPT = (
    "You are PathPilot, a friendly AI learning advisor. Your job is to profile the learner "
    "so you can generate a personalized learning path for them.\n\n"
    "You need to discover:\n"
    "1. Their learning goal (e.g. 'become a machine learning engineer')\n"
    "2. Their current skills (e.g. Python, JavaScript, SQL)\n"
    "3. Their experience level: beginner, intermediate, or advanced\n"
    "4. How many hours per week they can study\n\n"
    "Ask friendly follow-up questions if information is missing. "
    "Once you have all 4 pieces of information, include a 'profile' key in your JSON.\n\n"
    "ALWAYS respond with valid JSON in this exact format:\n"
    '{"response": "Your friendly reply here", "profile": null}\n'
    "OR when you have all info:\n"
    '{"response": "Great! I have everything I need...", '
    '"profile": {"goal_statement": "...", "current_skills": ["skill1"], '
    '"experience_level": "beginner", "weekly_hours": 10, "interests": []}}'
)


@dataclass
class ChatMessage:
    """
    Use: Single message in a conversation.
    Contains: role (user/assistant) and content string.
    """
    role: str
    content: str


@dataclass
class LearnerProfileDraft:
    """
    Use: Structured learner profile extracted from conversation.
    Contains: goal_statement, current_skills, experience_level, weekly_hours, interests.
    Technologies: Python dataclass for lightweight, typed data container.
    """
    goal_statement: str
    current_skills: List[str]
    experience_level: str
    weekly_hours: int
    interests: List[str]


class ChatEngine:
    """
    Use: Main conversational AI engine for learner profiling.
    Contains: Gemini API client, message processing logic.
    Technologies: Google Gemini API (gemini-2.5-flash) with JSON output mode.
    Key design: Falls back to deterministic responses if Gemini unavailable.
    """

    def __init__(self):
        """Initialize Gemini client from env var."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def process_message(
        self,
        message: str,
        history: List[Dict[str, str]]
    ) -> tuple:
        """
        Use: Process one user message in the conversation.
        How: Sends full conversation history + new message to Gemini.
             Gemini responds in JSON: {"response": str, "profile": null | {...}}.
        Concepts: Structured output via response_mime_type, few-shot via history.
        Used by: /learning/chat endpoint in main.py.
        Returns: (reply_str, LearnerProfileDraft_or_None, is_complete_bool)
        """
        # Deterministic fallback when Gemini not configured
        if not self.client:
            return self._fallback_response(message, history), None, False

        # Build contents for Gemini from conversation history
        contents = [
            {"role": m.get("role", "user"), "parts": [{"text": m.get("content", "")}]}
            for m in history
        ]
        contents.append({"role": "user", "parts": [{"text": message}]})

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )

            data = json.loads(response.text)
            reply = data.get("response", "Tell me more about your learning goals!")
            profile_data = data.get("profile")

            draft = None
            is_complete = False
            if profile_data and isinstance(profile_data, dict):
                draft = LearnerProfileDraft(
                    goal_statement=profile_data.get("goal_statement", ""),
                    current_skills=profile_data.get("current_skills", []),
                    experience_level=profile_data.get("experience_level", "beginner"),
                    weekly_hours=int(profile_data.get("weekly_hours", 10)),
                    interests=profile_data.get("interests", []),
                )
                is_complete = True

            return reply, draft, is_complete

        except Exception:
            return self._fallback_response(message, history), None, False

    def _fallback_response(self, message: str, history: List[Dict[str, str]]) -> str:
        """
        Use: Returns a deterministic follow-up question when Gemini is unavailable.
        How: Checks conversation length to decide which question to ask next.
        Final output: A string question to display to the user.
        """
        msg_count = len(history)
        if msg_count == 0:
            return (
                "Hi! I'm PathPilot. To create your personalized learning path, "
                "tell me what you want to achieve. For example: "
                "'I want to become a machine learning engineer' or "
                "'I want to learn web development'."
            )
        elif msg_count == 2:
            return (
                "Great! What's your current experience level — "
                "beginner, intermediate, or advanced? "
                "And what skills do you already have? (e.g. Python, JavaScript, SQL)"
            )
        elif msg_count == 4:
            return (
                "Almost there! How many hours per week can you dedicate to learning? "
                "(e.g. 5, 10, 20 hours/week)"
            )
        else:
            return (
                "Thanks! I have enough information to generate your personalized learning path. "
                "Click 'Generate My Learning Path' below to get started!"
            )


def extract_profile(response_text: str) -> Optional[LearnerProfileDraft]:
    """
    Use: Utility to parse a profile dict into a LearnerProfileDraft.
    Imported by: main.py if needed for manual extraction.
    """
    try:
        data = json.loads(response_text)
        p = data.get("profile")
        if not p:
            return None
        return LearnerProfileDraft(
            goal_statement=p.get("goal_statement", ""),
            current_skills=p.get("current_skills", []),
            experience_level=p.get("experience_level", "beginner"),
            weekly_hours=int(p.get("weekly_hours", 10)),
            interests=p.get("interests", []),
        )
    except Exception:
        return None
