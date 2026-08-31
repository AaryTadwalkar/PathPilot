# Active Context — Post-Demo Changes Implementation (2026-07-27)

## Session Summary
Implemented 3 of 4 company-requested post-demo changes. Change 1 (color theme) is blocked
pending the company's brand hex code.

---

## Changes Implemented This Session

### Change 4 — Resume Parser (COMPLETE ✅)
**Problem**: PyMuPDF `get_text("text")` only extracts text-layer PDFs. Image-based PDFs
(Canva, scanned) returned 0 chars, causing Gemini to receive an empty prompt and return nulls.

**Fixes applied**:
1. `backend/app/services/extraction.py`:
   - Switched from `get_text("text")` to `get_text("blocks")` + Y-bucket sort (multi-column aware)
   - Added `_extract_text_via_vision()`: renders pages at 200 DPI → PNG → Gemini Vision API
   - If text layer < 150 chars, auto-falls back to Vision OCR (no user action needed)
   - Format-flexible Gemini prompt: handles non-standard headers, two-column layouts
   - Guard: if both methods fail, raises ValueError → 400 to frontend
2. `backend/app/main.py`: Catches ValueError from extraction → 400 HTTPException
3. `frontend/src/app/profile-setup/page.tsx`: Format-specific error message

**Verified**:
- Aary (Jake LaTeX): 2488 chars extracted via text layer ✅
- Yashraj (Canva image PDF): 3470 chars extracted via Vision OCR ✅
- Both: TypeScript check passes, backend auto-reload successful ✅

### Change 3 — Upload Resume via Profile Icon (COMPLETE ✅)
**Problem**: `goResume()` and `FileUp` icon existed in profile-menu.tsx but the
`<DropdownMenuItem>` was never rendered and `/resume-upload` route didn't exist.

**Fixes applied**:
1. `frontend/src/components/profile-menu.tsx`: Added missing DropdownMenuItem "Upload New Resume"
2. `frontend/src/app/resume-upload/page.tsx` [NEW FILE]: Two-step page:
   - Step 1: Upload PDF → calls POST /profile/upload-resume (existing endpoint, reused)
   - Step 2: ProfileForm pre-filled with merged data (existing profile + extracted, with diff highlighting)
   - Merge strategy: scalar fields = AI wins if non-empty; arrays = deduplicated union
   - Auth check on mount; format-specific error messages

**Verified**: TypeScript check passes ✅

### Change 2 — Role-Specific Questions (COMPLETE ✅)
**Problem**: 6 hardcoded generic questions, no role differentiation.
**Target**: 5 generic + 5 role-specific = 10 questions per evaluation.

**Fixes applied**:
1. `datasets/role_specific_questions.json` [NEW FILE]: 75 questions (5 × 15 roles)
2. `backend/app/services/prs/assessment_service.py` [REWRITTEN]:
   - Reduced to 5 generic questions (removed `real_world_usage` — projects_engine defaults to "no", backward safe)
   - Added `get_role_specific_questions(role)`, `get_combined_questions(role)`
   - Added `validate_combined_answers(answers, role)` — optional role-specific validation
   - Added `score_role_specific(answers, role)` → 0-100 role depth score
3. `backend/app/main.py`:
   - `GET /prs/assessment?role=...` now returns 10 questions (or 5 without role param)
   - `POST /prs/evaluate` uses `validate_combined_answers()` + blends `score_role_specific()` at 10% weight into proj_result.score
4. `frontend/src/services/prs.service.ts`: `fetchPrsAssessment(role)` passes ?role= param
5. `frontend/src/app/placement-readiness/page.tsx`:
   - Removed premature on-mount questions fetch
   - Replaced Continue button with `handleConfirmRole()` that fetches questions for the selected role THEN transitions to QUIZ
   - Resets assessmentAnswers on role change

**Verified**:
- `GET /prs/assessment?role=AI+Engineer` → 10 questions ✅
- `GET /prs/assessment` (no role) → 5 questions (backward compat) ✅
- TypeScript: zero errors ✅

---

## Change 1 — Color Theme (COMPLETE ✅)
**Problem**: The frontend used hardcoded `indigo-*`, `purple-*`, and `slate-*` Tailwind classes, which did not match the company's design system.
**Target**: Implement the company's brand colors natively.

**Fixes applied**:
1. Added CSS variables for brand colors inside `@theme inline` in `frontend/src/app/globals.css`.
2. Created a script (`frontend/replace_theme.js`) to find-and-replace all instances of the old hardcoded colors with semantic brand classes (e.g. `from-brand-primary`, `bg-brand-card`, `text-brand-heading`) across the entire `frontend/src` directory (19 files updated).
3. Evaluated TS code post-replacement to ensure zero syntax breaks.

**Verified**: TypeScript checks passed. Tailwind v4 correctly maps the inline theme variables.

---

## Previous Session History (archived)
See archive_logs.md for full bug-fix history from prior sessions (2026-07-18).

---

## Current State (PathPilot Implementation - 2026-08-31)
**Backend**: Upgraded to support PathPilot AI Learning Path Recommender.
- `chat_engine.py` integrated for conversational learner profiling using Gemini.
- `path_generator.py` added to generate personalized topological course sequences.
- `explainability.py` added for generating course recommendations reasoning.
- New schemas and `LearningPath` & `ChatSession` ORM models added to track progress.
- API endpoints for `/learning/*` successfully implemented.
- Configuration updated to point to `pathpilot` DB instead of `imperium`.

**Datasets**:
- `courses_catalog.json` created with 60+ courses across various domains.
- `learning_goals.json` created with 20 distinct learning paths mapped to courses.

**Pending Operations**:
- Legacy scripts (`ingest_webdev_jobs.py`, `migrate_prs.py`, `migrate_career.py`, `reset_db.py`) were slated for deletion but are pending manual user cleanup due to terminal permission timeouts.

## Next Steps
1. User to delete the legacy scripts manually if required.
2. Restart backend to load new routes.
3. Test the `/learning/chat` and `/learning/path/generate` endpoints via Postman or Swagger UI.
