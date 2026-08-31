# PathPilot 🎯 — AI-Powered Personalized Learning Path Recommender

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Gemini AI](https://img.shields.io/badge/Google%20Gemini-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)

---

## 📖 Problem Statement
Online learning platforms offer thousands of courses, but learners struggle to identify the **right sequence** of resources needed to reach a specific goal. A one-size-fits-all approach is ineffective given different skill levels, interests, and learning preferences.

**PathPilot** bridges this gap with an AI-powered Personalized Learning Path Recommender that understands a learner's profile, identifies skill gaps, and generates a structured, ordered learning roadmap tailored to the individual.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **AI Conversational Interface** | Chat with an AI assistant that understands your goals in natural language |
| 🧠 **Learner Profiling Engine** | Captures interests, experience level, current skills, and learning objectives |
| 🗺️ **Learning Path Generator** | Generates prerequisite-aware, phased learning roadmaps |
| 📚 **Course Recommendation Engine** | Semantically matches courses from a curated catalog to your skill gaps |
| 💬 **AI Explainability** | Every recommendation comes with a "why this?" explanation |
| 📊 **Progress Dashboard** | Visual skill development tracking, milestone completion, and next actions |
| 🔍 **Course Explorer** | Browse and search 60+ curated courses across all tech domains |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PathPilot Frontend                       │
│              Next.js 16 (App Router) + TypeScript           │
│  /chat  /learning-path  /dashboard  /courses  /profile      │
└─────────────────┬────────────────────────────────────────────┘
                  │ HTTP (REST API)
┌─────────────────▼────────────────────────────────────────────┐
│                    PathPilot Backend                        │
│                FastAPI + Python 3.11                        │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Chat Engine │  │ Path Generator│  │ Skill Gap Engine  │  │
│  │  (Gemini)   │  │(Prereq Graph)│  │ (Knowledge Gaps)  │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │Recommender  │  │ Explainability│  │  LLM Gateway     │  │
│  │  Engine     │  │   Engine     │  │(Gemini+Fallback)  │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
└─────────────────┬────────────────────────────────────────────┘
                  │
┌─────────────────▼────────────────────────────────────────────┐
│              Data Layer                                     │
│  PostgreSQL + pgvector | JSON Datasets (60+ courses)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI/ML Techniques Used

| Technique | Application |
|---|---|
| **Google Gemini API** | Conversational profiling, natural language goal extraction, explainability |
| **Sentence Transformers (BGE-small-en-v1.5)** | Semantic similarity between user goals and course descriptions |
| **pgvector** | Vector similarity search for course matching |
| **Prerequisite Graph (Topological Sort)** | Orders courses by dependency chain |
| **Gap Analysis Engine** | Identifies skill gaps between current and target state |
| **Deterministic Fallback** | All LLM calls have rule-based fallbacks for 100% uptime |

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16, React, TypeScript, Tailwind CSS v4, shadcn/ui |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2 |
| **AI/ML** | Google Gemini API, Sentence-Transformers (BGE-small-en-v1.5) |
| **Database** | PostgreSQL 15 + pgvector extension |
| **Auth** | JWT (PyJWT) + OTP email verification |
| **Embeddings** | 384-dimensional BGE embeddings for semantic search |

---

## 📂 Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # All API route handlers (FastAPI)
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   └── services/
│   │       ├── learning/        # NEW: Core PathPilot engines
│   │       │   ├── chat_engine.py       # Gemini conversational profiler
│   │       │   ├── path_generator.py    # Learning path generation
│   │       │   └── explainability.py    # AI recommendation explanations
│   │       ├── prs/             # Skill gap analysis engines
│   │       │   ├── skill_engine.py      # Skill gap detection
│   │       │   └── recommendation_engine.py  # Course recommendations
│   │       └── career/          # Milestone & timeline engines
│   │           ├── milestone_engine.py  # Learning milestone sequencing
│   │           └── eta_engine.py        # Study timeline estimation
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── chat/            # NEW: Conversational AI interface
│       │   ├── learning-path/   # NEW: Visual learning roadmap
│       │   ├── dashboard/       # NEW: Progress dashboard
│       │   ├── courses/         # NEW: Course catalog browser
│       │   ├── auth/            # Authentication (login/signup)
│       │   └── profile-setup/   # Learner profile creation
│       └── services/
│           └── learning.service.ts  # NEW: PathPilot API calls
├── datasets/
│   ├── courses_catalog.json     # NEW: 60+ curated courses
│   ├── learning_goals.json      # NEW: 20 learning goals with skill maps
│   ├── role_skill_mapping.json  # Skill requirements per goal
│   └── ...
└── memory-bank/                 # Project documentation
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with `pgvector` extension installed
- Google Gemini API key ([Get one free](https://ai.google.dev/))

### 1. Clone the Repository
```bash
git clone https://github.com/AaryTadwalkar/pathpilot
cd pathpilot
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database URL and Gemini API key
```

### 3. Configure `.env`
```env
DATABASE_URL=postgresql://user:password@localhost:5432/pathpilot
GEMINI_API_KEY=your_google_gemini_api_key
SECRET_KEY=your_jwt_signing_secret_min_32_chars
SMTP_USERNAME=your_gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password
PRS_DETERMINISTIC_MODE=true
```

### 4. Initialize Database
```bash
# Make sure PostgreSQL is running with pgvector extension
psql -U postgres -c "CREATE DATABASE pathpilot;"
psql -U postgres -d pathpilot -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Start the backend (auto-creates all tables)
uvicorn app.main:app --reload
```

### 5. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 6. Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs

---

## 🐳 Docker Setup (Quick Start)
```bash
cd backend
docker-compose up -d
# Then run frontend separately: npm run dev
```

---

## 🔌 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/signup` | Register new learner |
| `POST` | `/auth/login` | Authenticate and get JWT |
| `GET` | `/learning/goals` | List all available learning goals |
| `POST` | `/learning/chat` | Send message to AI learning assistant |
| `POST` | `/learning/path/generate` | Generate personalized learning path |
| `GET` | `/learning/path/{id}` | Retrieve a saved learning path |
| `POST` | `/learning/path/{id}/progress` | Mark course as complete |
| `GET` | `/learning/courses/search` | Search course catalog |
| `GET` | `/learning/profile` | Get learner profile summary |

---

## 📊 User Journey

```
1. Sign Up → Create Account (email + OTP verification)
       ↓
2. Profile Setup → Describe background, skills, learning goals
       ↓
3. Chat with AI → "I want to become a machine learning engineer"
       ↓
4. Path Generated → AI creates phased roadmap:
       Phase 1: Python Foundations (3 weeks)
       Phase 2: Data Science Core (6 weeks)
       Phase 3: Machine Learning (8 weeks)
       ↓
5. Track Progress → Mark courses complete, view skill development
       ↓
6. Get Explanations → AI explains "Why this course?" for each recommendation
```

---

## 🤝 Team / Contributors
- AI-Powered Personalized Learning Path Recommender
- Built for [Hackathon Name] — 2026

---

## 📄 License
MIT License