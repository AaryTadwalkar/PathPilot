"""
chat_engine.py
==============
What this file does:
  Provides AI-powered conversational learner profiling. Accepts user messages
  describing their learning goals, extracts structured learner profile data.
  Supports injecting pre-existing user profile (from resume) so the AI skips
  asking for already-known information.

Overall design:
  Uses Google Gemini API (gemini-3.6-flash) with JSON structured output.
  System prompt is dynamically built to include existing profile context.
  Falls back to a deterministic question sequence when no API key is set.
  Supports Ollama local LLM as an alternative backend via OLLAMA_BASE_URL env var.

Elements:
  ChatMessage          dataclass -- single message in conversation
  LearnerProfileDraft  dataclass -- extracted profile data from conversation
  ChatEngine           class -- main conversation handler
  build_system_prompt()  -- builds context-aware system prompt
  extract_profile()    function -- parse response into structured data

Final output:
  Tuple (reply_str, LearnerProfileDraft_or_None, is_complete_bool)
"""
import os
import json
import requests
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


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


def build_system_prompt(user_profile: Optional[Dict[str, Any]] = None) -> str:
    """
    Use: Builds the system prompt for the chat AI, injecting known user profile data.
    How: If user_profile is provided (from resume extraction), the prompt tells
         Gemini to skip asking for already-known info and focus on missing fields.
    Concepts: Few-shot context injection, structured output prompting.
    Used by: ChatEngine.process_message()
    Final output: A complete system prompt string.
    """
    base = (
        "You are PathPilot, a friendly AI learning advisor. Your job is to understand "
        "the learner's goal and generate a personalized learning path.\n\n"
        "You need to know 4 things:\n"
        "1. Their specific learning goal (e.g. 'become an ML engineer')\n"
        "2. Their current skills (programming languages, tools, frameworks they know)\n"
        "3. Their experience level: beginner, intermediate, or advanced\n"
        "4. How many hours per week they can study\n\n"
    )

    if user_profile and any(user_profile.values()):
        # Inject what we already know so AI doesn't ask redundant questions
        known_parts = []
        if user_profile.get("name"):
            known_parts.append(f"- Name: {user_profile['name']}")
        if user_profile.get("skills"):
            skills_str = ", ".join(user_profile["skills"][:15])
            known_parts.append(f"- Known skills (from resume): {skills_str}")
        if user_profile.get("experience"):
            known_parts.append(f"- Work/project experience: {', '.join(user_profile['experience'][:3])}")
        if user_profile.get("career_interests"):
            known_parts.append(f"- Career interests: {user_profile['career_interests']}")

        if known_parts:
            base += (
                "IMPORTANT — You already have this profile data from the user's resume:\n"
                + "\n".join(known_parts)
                + "\n\nDo NOT ask again for information you already know. "
                "Greet the user by name if available, confirm their profile briefly, "
                "and only ask for what is missing (typically: their specific goal and weekly study hours). "
                "Be conversational and brief.\n\n"
            )
    else:
        base += (
            "Start by asking about their learning goal. Then gather missing details naturally. "
            "Be friendly, brief, and encouraging.\n\n"
        )

    base += (
        "ALWAYS respond with valid JSON in this exact format:\n"
        '{"response": "Your friendly reply here", "profile": null}\n'
        "OR when you have all 4 pieces of information:\n"
        '{"response": "Perfect! I have everything to build your path.", '
        '"profile": {"goal_statement": "become a machine learning engineer", '
        '"current_skills": ["Python", "Statistics"], '
        '"experience_level": "intermediate", "weekly_hours": 10, "interests": ["AI", "data"]}}'
    )
    return base


class ChatEngine:
    """
    Use: Main conversational AI engine for learner profiling.
    Contains: Gemini API client OR Ollama local LLM client, message processing logic.
    Technologies:
      - Primary: Google Gemini API (gemini-3.6-flash) — cloud, fast
      - Alternative: Ollama REST API (localhost:11434) — local, free, no token cost
      Set OLLAMA_BASE_URL env var to switch to local LLM (e.g. http://localhost:11434)
      Set OLLAMA_MODEL env var to choose model (default: mistral)
    Key design:
      - Context-aware: injects resume profile so AI doesn't re-ask known info
      - Falls back to deterministic responses when no AI backend available
    """

    def __init__(self):
        """Initialize AI backend: Ollama if configured, otherwise Gemini."""
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip()
        self.ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        self.backend = "none"
        if self.ollama_url:
            self.backend = "ollama"
        elif self.gemini_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                self.backend = "gemini"
            except Exception:
                self.backend = "none"

    def process_message(
        self,
        message: str,
        history: List[Dict[str, str]],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """
        Use: Process one user message in the conversation.
        How: Routes to Ollama (local), Gemini (cloud), or deterministic fallback.
             Injects user_profile into system prompt to avoid re-asking known info.
        Concepts: Context injection, structured JSON output, LLM routing.
        Used by: /learning/chat endpoint in main.py.
        Returns: (reply_str, LearnerProfileDraft_or_None, is_complete_bool)
        """
        system_prompt = build_system_prompt(user_profile)

        if self.backend == "ollama":
            return self._call_ollama(message, history, system_prompt)
        elif self.backend == "gemini":
            return self._call_gemini(message, history, system_prompt)
        else:
            return self._fallback_response(message, history, user_profile), None, False

    def _call_gemini(
        self,
        message: str,
        history: List[Dict[str, str]],
        system_prompt: str,
    ) -> tuple:
        """
        Use: Call Google Gemini API with conversation history.
        How: Builds contents array from history + new message, uses JSON output mode.
             CRITICAL: Gemini uses 'model' role (not 'assistant') for AI turns.
             Maps stored 'assistant' → 'model' before sending to API.
        Concepts: Gemini GenerateContentConfig, structured output via response_mime_type.
        Returns: (reply_str, LearnerProfileDraft_or_None, is_complete_bool)
        """
        from google import genai

        def _to_gemini_role(role: str) -> str:
            # Gemini requires 'model' not 'assistant'.
            # Seed messages are stored as 'model', legacy as 'assistant' — both → 'model'
            return "model" if role in ("assistant", "model") else "user"

        contents = [
            {
                "role": _to_gemini_role(m.get("role", "user")),
                "parts": [{"text": m.get("content", "")}]
            }
            for m in history
        ]
        contents.append({"role": "user", "parts": [{"text": message}]})

        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            return "Tell me your specific learning goal and I'll build your path!", None, False


    def _call_ollama(
        self,
        message: str,
        history: List[Dict[str, str]],
        system_prompt: str,
    ) -> tuple:
        """
        Use: Call a local Ollama LLM as a free, no-API-cost alternative to Gemini.
        How: Uses Ollama's OpenAI-compatible /api/chat endpoint.
             Set OLLAMA_BASE_URL=http://localhost:11434 and OLLAMA_MODEL=mistral in .env
        Concepts: REST API call, OpenAI-compatible message format, local LLM inference.
        Returns: (reply_str, LearnerProfileDraft_or_None, is_complete_bool)
        """
        messages = [{"role": "system", "content": system_prompt}]
        for m in history:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        messages.append({"role": "user", "content": message})

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={"model": self.ollama_model, "messages": messages, "stream": False,
                      "format": "json"},
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return self._parse_response(content)
        except Exception:
            return "Tell me your learning goals and I'll create your path!", None, False

    def _parse_response(self, text: str) -> tuple:
        """
        Use: Parse JSON response from any LLM backend into structured output.
        How: Loads JSON, extracts 'response' and 'profile' keys.
        Returns: (reply_str, LearnerProfileDraft_or_None, is_complete_bool)
        """
        try:
            data = json.loads(text)
            reply = data.get("response", "Tell me more about your goals!")
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
            return text or "Could you tell me more about your goals?", None, False

    def _fallback_response(
        self,
        message: str,
        history: List[Dict[str, str]],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Use: Returns a deterministic follow-up when no AI backend is configured.
        How: Uses conversation length as a proxy for which question to ask next.
             If user_profile is known, skips the skills question.
        Returns: A plain string question.
        """
        msg_count = len(history)
        has_skills = bool(user_profile and user_profile.get("skills"))

        if msg_count == 0:
            name = user_profile.get("name", "") if user_profile else ""
            greeting = f"Hi {name}! " if name else "Hi! "
            if has_skills:
                skills_preview = ", ".join((user_profile.get("skills") or [])[:4])
                return (
                    f"{greeting}I can see from your resume that you know "
                    f"{skills_preview} and more. What's your specific learning goal? "
                    "For example: 'I want to become a machine learning engineer'."
                )
            return (
                f"{greeting}I'm PathPilot. What do you want to achieve? "
                "For example: 'I want to become a machine learning engineer' or "
                "'I want to learn web development from scratch'."
            )
        elif msg_count == 2 and not has_skills:
            return (
                "What's your current experience level — beginner, intermediate, or advanced? "
                "And what skills do you already have? (e.g. Python, JavaScript, SQL)"
            )
        elif msg_count in (2, 4):
            return "How many hours per week can you dedicate to learning? (e.g. 5, 10, 20 hours)"
        else:
            return (
                "Thanks! I have everything I need. "
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
