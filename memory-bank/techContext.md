# Tech Context

## Technology Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | Latest | REST API framework |
| SQLAlchemy | 2.0 | ORM + query builder |
| Alembic | Latest | Database migrations (partially used) |
| PostgreSQL | 15+ | Primary database |
| pgvector | 0.2+ | Vector similarity extension |
| psycopg2 | 2.x | PostgreSQL driver |
| Pydantic v2 | Latest | Schema validation |
| passlib[bcrypt] | Latest | Password hashing |
| PyJWT | Latest | JWT tokens |
| APScheduler | Latest | Background job scheduler |
| boto3 | Latest | MinIO/S3 object storage |
| fitz (PyMuPDF) | Latest | PDF text extraction |
| google-genai | Latest | Gemini API client |
| sentence-transformers | Latest | BGE embeddings (384-dim) |
| numpy | Latest | Vector math |
| uvicorn | Latest | ASGI server |
| python-dotenv | Latest | Env var loading |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.2.7 | React framework (App Router) |
| TypeScript | Latest | Type safety |
| Tailwind CSS | Latest | Styling |
| shadcn/ui | Latest | Component library |
| lucide-react | Latest | Icons |
| Turbopack | Latest | Dev bundler |

### Infrastructure
| Service | Purpose |
|---------|---------|
| PostgreSQL | Primary database + pgvector |
| MinIO | S3-compatible object storage for resume PDFs |
| Gemini API | LLM for resume analysis + project classification |
| JSearch (RapidAPI) | Opportunity data source |

## Development Setup

### Backend
```bash
cd backend
# Activate venv
venv\Scripts\activate   # Windows
# Start server
uvicorn app.main:app --reload
# Run schema fix (REQUIRED after new columns added to ORM)
python fix_readiness_schema.py
```

### Frontend
```bash
cd frontend
npm run dev
# Runs on http://localhost:3000
# Expects backend at http://127.0.0.1:8000
```

## Environment Variables (backend/.env)
```
DATABASE_URL=postgresql://...
MINIO_ENDPOINT=...
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET_NAME=...
RAPIDAPI_KEY=...
GEMINI_API_KEY=...
SECRET_KEY=...  (JWT signing key)
SMTP_USERNAME=...
SMTP_PASSWORD=...
PRS_DATASET_DIR=../datasets  (optional, defaults to ../datasets)
```

## Dataset Files (datasets/)
```
skills_master.json             — canonical skill list with aliases/clusters
role_skill_mapping.json        — per-role required skills with criticality/demand scores
role_domain_mapping.json       — role → domain list mapping
role_tech_stack_mapping.json   — role → primary/secondary stack lists
stack_sophistication_mapping.json — stack name → sophistication score
certificates_dataset.json      — cert catalog with provider/level/alignment
certificate_provider_scores.json — provider → quality score (0-100)
certificate_level_mapping.json — level label → score (0-100)
courses_dataset.json           — course recommendations catalog
projects_dataset.json          — suggested project catalog
assessment_questions.json      — grouped question definitions (different format from assessment_service.py hardcoded questions)
aliases/skill_aliases.json     — skill name normalization aliases
aliases/certificate_aliases.json
aliases/stack_aliases.json
```

## Known Technical Constraints
- LLM calls (Gemini) fail in offline/rate-limited environments — all engines have deterministic fallbacks
- HuggingFace model download requires internet on first startup (BGE embeddings model)
- MinIO must be running for resume upload (health check endpoint shows status)
- `assessment_questions.json` format differs from `assessment_service.py` hardcoded format — the backend uses the hardcoded version; the JSON file is for potential future use
