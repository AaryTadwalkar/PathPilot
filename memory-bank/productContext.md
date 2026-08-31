# Product Context

## Why This Project Exists
Imperium Alumni Portal solves two core problems for college students:
1. **Discovery Gap**: Students don't know about relevant internships/jobs — Module 1 auto-discovers and surfaces matching opportunities using semantic AI
2. **Readiness Gap**: Students don't know HOW ready they are for placement — Module 2 gives them a score, breakdown, and actionable improvement plan

## Problems Being Solved
- Students waste time applying for roles they're not ready for
- Career advisors lack data to give personalized guidance
- Students don't know what skills/projects/certs to prioritize next

## How It Should Work

### User Journey (Module 2 — PRS)
1. User selects a **target role** (e.g., "AI Engineer") from a dataset-backed list
2. User answers **6 assessment questions** about their deployment, ownership, engineering practices, experience, real-world usage, and problem-solving approach
3. Backend runs the **5-engine PRS pipeline** on their saved profile + assessment answers
4. User sees their **Placement Readiness Score (0-100)**, readiness level label, pillar breakdown, and ranked recommendations
5. User can view **history** of past evaluations to track improvement over time

### Pillar Weights (spec-defined, immutable)
| Pillar | Weight |
|--------|--------|
| Skill Readiness | 30% |
| Projects + Experience | 25% |
| Role Alignment | 20% |
| Resume Quality | 15% |
| Certificate Quality | 10% |

### Readiness Levels
| Score | Level |
|-------|-------|
| 85-100 | Highly Placement Ready |
| 70-84 | Industry Ready |
| 55-69 | Developing Readiness |
| 40-54 | Needs Improvement |
| 0-39 | Early Preparation Stage |

## User Experience Goals
- Fast evaluation (< 5s despite LLM calls — fallback if LLM unavailable)
- Transparent scoring — user sees exactly why each pillar scored as it did
- Actionable — every recommendation explains "why" based on their specific gaps
- History-aware — track improvement over multiple evaluations
