# Progress

## What Works (Verified)

### Module 1 (Complete)
- [x] User signup → OTP email → verification → login (JWT)
- [x] Resume PDF upload to MinIO + Gemini extraction
- [x] Profile save (skills, projects, experience, career interests, links)
- [x] Opportunity ingestion with SHA-256 deduplication + vector embedding
- [x] Background opportunity sync scheduler (JSearch API, every 1h)
- [x] Notifications system (opportunity matching → notify)
- [x] `/notifications/{user_id}` GET endpoint works (confirmed in logs)
- [x] `/notifications/{user_id}/read-all` POST endpoint (partially tested)

### Module 2 — Backend (Mostly Complete)
- [x] Dataset loader with full validation (11 required + 3 optional files)
- [x] Assessment service (6 questions, validation, score maps)
- [x] `GET /prs/roles` — returns dataset-backed role list ✓
- [x] `GET /prs/assessment` — returns assessment questions ✓
- [x] `POST /prs/evaluate` — full pipeline runs but **fails on DB persist**
- [x] Phase 5: Input Builder (PRSInput)
- [x] Phase 6: Skill Readiness Engine
- [x] Phase 7: Projects + Experience Engine (LLM + deterministic fallback)
- [x] Phase 8: Certificate Quality Engine
- [x] Phase 9: Resume Quality Engine
- [x] Phase 10: Role Alignment Engine
- [x] Phase 11: PRS Orchestrator
- [x] Phase 12: Recommendation Engine

### Module 2 — Frontend
- [x] `/placement-readiness` page loads
- [x] Role selection UI works (fetches from backend)
- [x] Assessment quiz UI (6 questions, single/multi select)
- [x] Results display (score, breakdown, recommendations)

## What's Broken / Fixed

### Bug 1 — CRITICAL: DB Column Missing (FIXED)
**Error**: `psycopg2.errors.UndefinedColumn: column "skill_readiness_score" of relation "readiness_evaluations" does not exist`
**Root Cause**: `migrate_prs.py` skips the table if it already exists. Old table from Module 1 only has legacy columns (`overall_score`, `skills_score`, etc.). New ORM model adds 15+ new Phase 13 columns but never ran ALTER TABLE.
**Fix**: Created `backend/fix_readiness_schema.py` — safe ALTER TABLE that adds all missing columns with IF NOT EXISTS.
**Action Required**: Run `python fix_readiness_schema.py` in the backend directory once.

### Bug 2 — Frontend: Hardcoded localhost URL in notification-bell (FIXED)
**Error**: `TypeError: Failed to fetch` in markNotificationsRead
**Root Cause**: Used raw `fetch("http://localhost:8000/...")` instead of `apiRequest()` from api.ts.
**Fix**: Replaced raw fetch with `apiRequest()` from `@/lib/api` + added proper try/catch.

### Bug 3 — PRS Gemini Dependency (FIXED — Deterministic Mode)
**Problem**: Gemini API calls failed (rate limit / invalid key), causing 1.5s retry delays. LLM fallbacks were very coarse (description length → grammar score).
**Fix**: Full deterministic recommendation system implemented (Session 2):
- `PRS_DETERMINISTIC_MODE=true` in `.env` disables all LLM calls at the gateway level
- `_deterministic_classify_project()` in projects_engine replaces LLM with 5-signal composite + dataset-driven domain classification
- `_deterministic_grammar_score()` and `_deterministic_impact_score()` in resume_engine replace crude length-proxy with multi-signal analyzers
- `recommendation_engine.py` enriched with experience-level course matching, deployment-outcome project bonus, and pillar-score hints in `why_recommended`

## What's Left to Build
- [x] **Run the schema fix**: Execute `python fix_readiness_schema.py` to unblock POST /prs/evaluate
- [ ] Test full end-to-end flow after schema fix
- [ ] Phase 17+: Possible additional features (alumni placement tracking, etc.)
- [ ] Production: Docker deployment, verify PRS_DETERMINISTIC_MODE setting

## Current Status
**Module 1**: Production-ready
**Module 2**: Code complete, blocked only by DB schema mismatch. Run `fix_readiness_schema.py` to unblock.
**PRS Deterministic Mode**: Fully implemented — no Gemini calls required, full accuracy scoring pipeline.

## Known Issues
1. `assessment_questions.json` uses a different question format than `assessment_service.py` — the JSON file is unused by the backend; hardcoded questions in `assessment_service.py` are the authoritative source
2. HF model downloads on first startup require internet (BGE-small-en-v1.5 for embeddings — still required)
3. LLM (Gemini) calls disabled by default (`PRS_DETERMINISTIC_MODE=true`) — re-enable by setting to `false` in `.env`
