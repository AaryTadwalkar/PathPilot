# System Patterns

## Architecture Overview

```
Frontend (Next.js 16)
  └── src/app/placement-readiness/page.tsx   — PRS UI (role select → quiz → results)
  └── src/services/prs.service.ts            — API calls for PRS endpoints
  └── src/components/notification-bell.tsx   — Notification polling component
  └── src/lib/api.ts                         — Centralized apiRequest helper (base URL: http://127.0.0.1:8000)

Backend (FastAPI)
  └── app/main.py                            — All route handlers
  └── app/models.py                          — SQLAlchemy ORM models
  └── app/schemas.py                         — Pydantic request/response models
  └── app/services/prs/
      ├── dataset_loader.py                  — Loads + validates 11 JSON datasets
      ├── assessment_service.py              — Assessment questions + validation + scoring
      ├── input_builder.py                   — Builds PRSInput from user ORM record
      ├── skill_engine.py                    — Phase 6: Skill Readiness
      ├── projects_engine.py                 — Phase 7: Projects + Experience
      ├── certificate_engine.py              — Phase 8: Certificate Quality
      ├── resume_engine.py                   — Phase 9: Resume Quality
      ├── role_alignment_engine.py           — Phase 10: Role Alignment
      ├── orchestrator.py                    — Phase 11: Score combination
      ├── recommendation_engine.py           — Phase 12: Recommendations
      └── llm_gateway.py                     — Gemini API with retry + deterministic fallback
```

## Key Design Patterns

### PRS Pipeline (Phases 5-12)
```
POST /prs/evaluate
  1. Resolve user from JWT (or user_id fallback)
  2. Validate target_role against dataset
  3. validate_assessment_answers() → normalized dict
  4. build_prs_input() → PRSInput dataclass
  5. calculate_skill_readiness()       → SkillReadinessResult
  6. calculate_projects_experience()   → ProjectsExperienceResult
  7. calculate_certificate_quality()   → CertResult
  8. calculate_resume_quality()        → ResumeResult
  9. calculate_role_alignment()        → AlignmentResult
 10. orchestrate_prs()                 → PRSResult (final score + weak areas)
 11. generate_recommendations()        → RecommendationResult
 12. Persist ReadinessEvaluation ORM record
 13. Return PRSEvaluationResponse
```

### Dataset Architecture
- **11 JSON files** in `/datasets/` loaded at startup via `load_prs_datasets()`
- LRU-cached (`@lru_cache(maxsize=4)`) — loaded once per process
- Required files (failure = startup error): skills_master, role_skill_mapping, role_domain_mapping, role_tech_stack_mapping, stack_sophistication_mapping, certificates_dataset, certificate_provider_scores, certificate_level_mapping, 3 alias files
- Optional files (warning only): courses_dataset, projects_dataset, assessment_questions

### LLM Gateway (Phase 15)
- Wraps Gemini API calls with 3 retries and exponential backoff
- If all retries fail → **deterministic fallback** so pipeline never blocks
- Used by: projects_engine (domain classification), resume_engine (grammar/clarity)

### Security Pattern
- JWT tokens decoded to get user identity — never trust client-submitted user_id when token present
- `_resolve_user_from_token()` provides priority: JWT > user_id fallback
- Component scores never accepted from client

### Database Patterns
- PostgreSQL + pgvector (384-dim vectors for profile/opportunity embeddings)
- Migrations: additive only — never drop tables/columns
- `init_db()` uses `create_all(checkfirst=True)` — safe for existing databases
- `migrate_prs.py` and `fix_readiness_schema.py` handle ALTER TABLE safely

## Critical Bug Patterns Discovered

### Schema Drift Bug
When `migrate_prs.py` sees an existing `readiness_evaluations` table it **SKIPS** it.
This means new columns added to the ORM model never get added to the DB.
**Fix**: `fix_readiness_schema.py` — ALTER TABLE with IF NOT EXISTS for each missing column.

### URL Consistency Bug
`notification-bell.tsx` used hardcoded `http://localhost:8000` while `api.ts` uses `http://127.0.0.1:8000`.
These resolve differently on some OS/browser combos.
**Fix**: Use centralized `apiRequest()` from `api.ts` everywhere.
