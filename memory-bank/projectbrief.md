# Project Brief — PathPilot AI Learning Path Recommender

## Project Name
**PathPilot — AI-Powered Personalized Learning Path Recommender**

## Core Mission
Build an AI-powered learning assistant that recommends personalized learning paths based on a learner's interests, goals, current skills, and experience level. The solution generates a structured learning roadmap, explains recommendations, and adapts based on user progress.

## Key Deliverables (Hackathon)
1. **Conversational Interface** — learners describe goals in natural language via AI chat
2. **Learner Profiling Engine** — captures interests, experience level, current skills, learning objectives
3. **Recommendation Engine** — suggests relevant courses, projects, and learning resources
4. **Learning Path Generator** — generates prerequisite-aware, phased roadmap with milestones
5. **AI Explainability** — explains WHY each recommendation was made
6. **Progress Dashboard** — visualizes progress, skill development, milestones, next actions

## Tech Stack
- FastAPI backend (Python 3.11+)
- Next.js 16 frontend (TypeScript + Tailwind + shadcn/ui)
- PostgreSQL + pgvector for storage and semantic search
- Google Gemini API for conversational AI + explainability
- BGE-small-en-v1.5 embeddings (384-dim) for semantic matching

## Key Constraints
- Deterministic fallback for ALL LLM calls (100% uptime guarantee)
- JWT auth with OTP email verification
- New DB: `pathpilot` (not `imperium`)
- Never drop existing tables (migrations additive only)

## Datasets
- `courses_catalog.json` — 60+ curated courses
- `learning_goals.json` — 20 learning goals with skill maps
- `role_skill_mapping.json` — skills per goal
