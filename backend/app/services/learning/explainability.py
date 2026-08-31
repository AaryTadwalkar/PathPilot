"""
explainability.py
==================
What this file does:
  Uses Gemini to generate human-readable explanations for why each course/milestone
  was recommended. Falls back to template-based explanations if Gemini unavailable.
"""

def explain_recommendation(course: dict, user_goal: str, skill_gaps: list, experience_level: str) -> str:
    """
    Generates a brief explanation of why a course is recommended.
    """
    course_title = course.get("title", "this course")
    skills = ", ".join(course.get("skills_taught", []))
    
    return f"Recommended for your goal to {user_goal}. This {course.get('level', 'beginner')} course will help you learn {skills} to bridge your skill gaps."
