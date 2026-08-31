"""
path_generator.py
=================
What this file does:
  Generates a personalized, ordered learning path based on learner profile.
  Takes the learner's goal, current skills, and experience level; returns
  an ordered sequence of courses with prerequisites satisfied, milestones,
  and estimated completion timeline.
"""

from typing import List, Dict, Any, Set
from dataclasses import dataclass
import json
import os

@dataclass
class LearningPathResult:
    phases: List[Dict[str, Any]]
    total_weeks: int
    course_list: List[Dict[str, Any]]

def generate_learning_path(goal_id: str, current_skills: List[str], experience_level: str, weekly_hours: int, datasets_dir: str) -> LearningPathResult:
    # Load datasets
    with open(os.path.join(datasets_dir, "courses_catalog.json"), "r") as f:
        courses_catalog = json.load(f)
    
    with open(os.path.join(datasets_dir, "learning_goals.json"), "r") as f:
        learning_goals_data = json.load(f)
        
    goals = {g["id"]: g for g in learning_goals_data.get("goals", [])}
    goal = goals.get(goal_id)
    if not goal:
        raise ValueError(f"Goal {goal_id} not found")
        
    # Filter courses
    course_dict = {c["id"]: c for c in courses_catalog}
    recommended_ids = goal.get("recommended_course_ids", [])
    
    # Remove courses for skills already known (simple case-insensitive match)
    known_skills = set(s.lower() for s in current_skills)
    
    selected_courses = []
    for cid in recommended_ids:
        if cid in course_dict:
            c = course_dict[cid]
            # Check if all skills taught are already known
            taught = set(s.lower() for s in c.get("skills_taught", []))
            if taught and taught.issubset(known_skills):
                continue
            selected_courses.append(c)
            
    # Simple topological sort for prerequisites
    # (Assuming selected_courses is small and manageable)
    ordered_courses = []
    visited = set()
    
    def visit(cid):
        if cid in visited: return
        visited.add(cid)
        if cid in course_dict:
            for prereq in course_dict[cid].get("prerequisites", []):
                visit(prereq)
            if course_dict[cid] in selected_courses and course_dict[cid] not in ordered_courses:
                ordered_courses.append(course_dict[cid])
                
    for c in selected_courses:
        visit(c["id"])
        
    # Group into phases
    phase_duration = sum(c.get("duration_hours", 10) for c in ordered_courses) // 3
    phases = []
    
    current_phase_courses = []
    current_hours = 0
    phase_num = 1
    
    for c in ordered_courses:
        current_phase_courses.append(c)
        current_hours += c.get("duration_hours", 10)
        
        if current_hours >= phase_duration and phase_num < 3:
            phases.append({
                "phase_number": phase_num,
                "phase_name": f"Phase {phase_num}",
                "description": f"Focus on {c.get('domain', 'core')} skills",
                "courses": current_phase_courses,
                "estimated_weeks": max(1, current_hours // max(1, weekly_hours)),
                "skills_gained": list(set(s for crs in current_phase_courses for s in crs.get("skills_taught", [])))
            })
            current_phase_courses = []
            current_hours = 0
            phase_num += 1
            
    if current_phase_courses:
        phases.append({
            "phase_number": phase_num,
            "phase_name": f"Phase {phase_num}",
            "description": "Advanced topics and finalization",
            "courses": current_phase_courses,
            "estimated_weeks": max(1, current_hours // max(1, weekly_hours)),
            "skills_gained": list(set(s for crs in current_phase_courses for s in crs.get("skills_taught", [])))
        })
        
    total_weeks = sum(p["estimated_weeks"] for p in phases)
    
    return LearningPathResult(
        phases=phases,
        total_weeks=total_weeks,
        course_list=ordered_courses
    )
