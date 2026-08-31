# PathPilot 🎯
### AI-Powered Personalized Learning Path Recommender

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js_15-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_15-316192?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0064a5?style=flat&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Gemini AI](https://img.shields.io/badge/Google_Gemini-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)

> **Hackathon Project** — Built for the AI-Powered Personalized Learning Path Recommender Challenge 2026

---

## 📌 Problem Statement

Online learning platforms offer thousands of courses, but learners face three core problems:

- **No clear sequence** — which course do I take first?
- **No personalization** — recommendations ignore existing skills
- **No goal alignment** — courses aren't mapped to career outcomes

**PathPilot** solves all three. It understands your background from your resume, converses with you to understand your goal, identifies your exact skill gaps, and generates a **structured, phase-by-phase learning roadmap** tailored entirely to you.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 **Resume-Aware Profiling** | Upload your PDF resume — AI extracts your skills automatically. No manual entry. |
| 🤖 **Conversational Goal Detection** | One-message chat: just say your goal, AI knows your profile already |
| 🗺️ **Phased Learning Path Generator** | Prerequisite-aware, ordered roadmap across beginner → advanced |
| 🎯 **Skill Gap Analysis** | Compares your current skills against goal requirements |
| 🔍 **Course Explorer** | Search and filter 50+ curated courses by domain, level, and skill |
| 📊 **Progress Dashboard** | Visual skill radar, completion stats, and active path tracker |
| ✅ **Progress Tracking** | Mark courses complete, track your journey phase by phase |
| 🔐 **Secure Auth** | JWT + OTP email verification |

---

## 🏗 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    PathPilot Frontend                        │
│          Next.js 15 · TypeScript · Tailwind CSS v4           │
│                                                              │
│   /auth   /profile-setup   /chat   /learning-path            │
│   /dashboard   /courses                                      │
└───────────────────────┬──────────────────────────────────────┘
                        │ REST API (HTTP/JSON)
                        │ Authorization: Bearer <JWT>
┌───────────────────────▼──────────────────────────────────────┐
│                    PathPilot Backend                         │
│              FastAPI · Python 3.11 · Uvicorn                 │
│                                                              │
│  ┌──────────────────┐   ┌──────────────────────────────────┐ │
│  │  Resume Extractor │   │       Chat Engine                │ │
│  │  PyMuPDF + Gemini │   │  Gemini 3.6-flash + Keyword      │ │
│  │  (PDF → Skills)  │   │  Bypass (no redundant questions) │ │
│  └──────────────────┘   └──────────────────────────────────┘ │
│  ┌──────────────────┐   ┌──────────────────────────────────┐ │
│  │  Path Generator  │   │     Skill Gap Engine             │ │
│  │  Topological Sort│   │  Current Skills vs Goal Skills   │ │
│  │  Prereq Graphs   │   │  → Ordered Course Sequence       │ │
│  └──────────────────┘   └──────────────────────────────────┘ │
│  ┌──────────────────┐   ┌──────────────────────────────────┐ │
│  │ BGE Embeddings   │   │     Explainability Engine        │ │
│  │ Semantic Search  │   │  "Why this course for you?"      │ │
│  └──────────────────┘   └──────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                     Data Layer                               │
│   PostgreSQL 15 + pgvector   (Docker: pathpilot-db)          │
│   courses_catalog.json (50+ courses)                         │
│   learning_goals.json  (20 career goals)                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI/ML Techniques

| Technique | Where Used |
|---|---|
| **Google Gemini 3.6-flash** | Resume text extraction, conversational profiling, course explanations |
| **Sentence Transformers** `BGE-small-en-v1.5` | 384-dim semantic embeddings for course-goal matching |
| **pgvector** | Vector similarity search in PostgreSQL |
| **Topological Sort (DAG)** | Orders courses respecting prerequisites (Foundations → Advanced) |
| **Keyword Goal Detection** | Deterministic goal matching — skips LLM when profile is loaded |
| **Skill Gap Analysis** | Set difference between user skills and goal-required skills |
| **LLM Fallback Chain** | All Gemini calls have rule-based fallbacks for 100% uptime |

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15, React 18, TypeScript, Tailwind CSS v4, shadcn/ui |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| **AI/ML** | Google Gemini API (3.6-flash), Sentence-Transformers (BGE-small-en-v1.5) |
| **Database** | PostgreSQL 15 + pgvector 0.5.1 (via Docker) |
| **Auth** | JWT (PyJWT) + SMTP OTP email verification |
| **PDF Parsing** | PyMuPDF (fitz) |
| **Containerization** | Docker (`ankane/pgvector` image) |

---

## 📂 Project Structure

```
pathpilot/
├── backend/
│   ├── app/
│   │   ├── main.py                   # All FastAPI route handlers
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── schemas.py                # Pydantic request/response schemas
│   │   ├── database.py               # DB connection & session management
│   │   └── services/
│   │       ├── learning/             # Core PathPilot AI engines
│   │       │   ├── chat_engine.py    # Gemini conversational profiler + bypass
│   │       │   ├── path_generator.py # Topological sort path generation
│   │       │   └── explainability.py # "Why this course?" AI explanations
│   │       ├── prs/                  # Skill recommendation engines
│   │       │   ├── skill_engine.py
│   │       │   └── recommendation_engine.py
│   │       ├── extraction.py         # PDF resume → structured skills (Gemini)
│   │       └── embeddings.py         # BGE sentence embeddings
│   ├── .env                          # Environment variables (not committed)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx              # Home / landing
│       │   ├── auth/                 # Login + OTP signup
│       │   ├── profile-setup/        # Resume upload + profile
│       │   ├── chat/                 # AI conversational interface
│       │   ├── learning-path/        # Phased roadmap viewer
│       │   ├── dashboard/            # Progress & skill radar
│       │   └── courses/              # Course catalog browser
│       ├── services/
│       │   ├── learning.service.ts   # PathPilot API calls
│       │   └── api.ts                # Base API client with auth
│       └── components/ui/            # shadcn/ui components
├── datasets/
│   ├── courses_catalog.json          # 50+ curated real courses
│   └── learning_goals.json          # 20 career goals with skill maps
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** (running)
- **Node.js 18+**
- **Python 3.11+**
- **Google Gemini API key** — [Get free at ai.google.dev](https://ai.google.dev/)

---

### Step 1 — Start the Database

```bash
# Pull and run PostgreSQL with pgvector on port 5433
docker run -d --name pathpilot-db \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=password123 \
  -e POSTGRES_DB=pathpilot \
  -p 5433:5432 \
  ankane/pgvector:latest

# Enable pgvector extension
docker exec pathpilot-db psql -U admin -d pathpilot \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

### Step 2 — Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 3 — Configure Environment

Create `backend/.env`:

```env
DATABASE_URL=postgresql://admin:password123@localhost:5433/pathpilot
GEMINI_API_KEY=your_google_gemini_api_key_here
SECRET_KEY=your_random_64_char_secret_key_here
SMTP_USERNAME=your_gmail@gmail.com
SMTP_PASSWORD=your_gmail_app_password
PRS_DETERMINISTIC_MODE=false
PATHPILOT_DATASET_DIR=../datasets
```

> **Gmail App Password**: Go to Google Account → Security → 2-Step Verification → App Passwords → Generate for "Mail"

---

### Step 4 — Start Backend

```bash
# From the backend/ directory, with venv active
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

✅ You should see:
```
MAIN FILE LOADED
INFO: Application startup complete.
```

---

### Step 5 — Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

### Step 6 — Open the App

| Service | URL |
|---|---|
| **Application** | http://localhost:3000 |
| **API** | http://127.0.0.1:8000 |
| **API Docs (Swagger)** | http://127.0.0.1:8000/docs |

---

## 🎬 Demo Flow (User Journey)

```
1. Sign Up
   └── Enter email → receive OTP → verify → account created

2. Upload Resume
   └── /profile-setup → upload PDF → Gemini extracts skills automatically
       → profile saved (name, 30+ skills, experience)

3. AI Chat
   └── /chat → green badge "Profile loaded · 37 skills"
       → type: "I want to become a machine learning engineer"
       → AI responds instantly (no re-asking for skills!)
       → ✨ Generate My Learning Path button appears

4. Learning Path
   └── /learning-path → 3-phase roadmap
       Phase 1: Foundations  (Python, Math, SQL)
       Phase 2: Core ML      (Scikit-learn, Pandas, Feature Engineering)
       Phase 3: Advanced     (Deep Learning, MLOps, Deployment)
       → Click courses to mark complete

5. Course Explorer
   └── /courses → search "python" → filter Beginner
       → 50+ courses from Coursera, Udemy, fast.ai

6. Dashboard
   └── /dashboard → skill radar chart + progress stats
```

---

## 🔌 API Reference

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/signup` | Register + send OTP |
| `POST` | `/auth/verify-otp` | Verify OTP → create account |
| `POST` | `/auth/login` | Login → JWT token |

### Learning (PathPilot Core)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/learning/chat` | Send message to AI assistant |
| `POST` | `/learning/path/generate` | Generate personalized path |
| `GET` | `/learning/path/{id}` | Fetch a saved learning path |
| `GET` | `/learning/paths` | List user's generated paths |
| `POST` | `/learning/path/{id}/progress` | Mark course complete |
| `GET` | `/learning/courses/search` | Search course catalog |
| `GET` | `/learning/goals` | List all career goals |
| `GET` | `/learning/profile` | Get user profile summary |

### Profile
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/profile/upload-resume` | Upload PDF → extract skills |
| `POST` | `/profile/save` | Save learner profile |

---

## 🛠 Utility Commands

```bash
# Reset all user data (fresh demo slate)
docker exec pathpilot-db psql -U admin -d pathpilot \
  -c "TRUNCATE TABLE users CASCADE;"

# Restart database container (after PC reboot)
docker start pathpilot-db

# Check backend health
curl http://127.0.0.1:8000/health

# Check logs if something fails
docker logs pathpilot-db
```

---

## 🌱 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key |
| `SECRET_KEY` | ✅ | JWT signing secret (min 32 chars) |
| `SMTP_USERNAME` | ✅ | Gmail address for OTP emails |
| `SMTP_PASSWORD` | ✅ | Gmail app password (not account password) |
| `PRS_DETERMINISTIC_MODE` | ❌ | `false` = use Gemini, `true` = rule-based only |
| `PATHPILOT_DATASET_DIR` | ❌ | Path to datasets folder (default: `../datasets`) |
| `OLLAMA_BASE_URL` | ❌ | Set to `http://localhost:11434` to use local LLM |
| `OLLAMA_MODEL` | ❌ | Ollama model name (default: `mistral`) |

---

## 🤝 Contributors

Built for the **AI-Powered Personalized Learning Path Recommender Hackathon 2026**

| Name | Role |
|---|---|
| Aary Tadwalkar | Full-Stack AI Engineer |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.