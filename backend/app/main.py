# from altair import DateTime
from fastapi import FastAPI, Depends, File, UploadFile, Form, HTTPException, BackgroundTasks, Header
from app.services import taxonomy
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal, init_db, get_db
import boto3
import time
import os
import uuid
from dotenv import load_dotenv
import app.schemas as schemas
from app import models
from app.taxonomy import ROLE_TAXONOMY
import app.services.extraction as extraction
import app.services.embeddings as embeddings
import hashlib
import app.services.adapters as adapters
from app.services.prs.dataset_loader import (
    DatasetValidationError,
    load_prs_datasets,
)
from app.services.prs.assessment_service import (
    get_assessment_questions,
    score_assessment_for_prototype,
    validate_assessment_answers,
    validate_combined_answers,
    score_role_specific,
)
from app.services.learning.chat_engine import ChatEngine, LearnerProfileDraft
from app.services.learning.path_generator import generate_learning_path, LearningPathResult
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
from typing import List
import bcrypt as _bcrypt
import random
from google import genai
from google.genai import types
from datetime import datetime, timedelta
import jwt
# from pgvector.sqlalchemy import CosineDistance
# If the above fails again, change it to use the operator string directly inside the query.
from sqlalchemy import func
import numpy as np
import json
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


load_dotenv()

app = FastAPI(
    title="PathPilot — AI Learning Path API",
    description="Personalized learning path generation, chat, and progress tracking",
    contact={"name": "PathPilot Team"}
)
print("MAIN FILE LOADED")
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize the database on startup
    init_db()
    db = next(get_db())

    try:
        seed_query_queue(db)
    finally:
        db.close()
    # 2. Configure the background scheduler
    scheduler = BackgroundScheduler()
    
    # We need a fresh database session for the background task
    def scheduled_sync_job():
        db = next(get_db())
        try:
            print("--- Running Scheduled Opportunity Sync ---")
            background_opportunity_sync(db)
        finally:
            db.close()

    # 3. Schedule the job to run safely every 6 hours
    # This prevents IP bans by keeping traffic extremely low
    scheduler.add_job(
        scheduled_sync_job,
        'interval',
        hours=1
    )
    
    scheduler.add_job(
        taxonomy_similarity_report_job,
        'interval',
        weeks=1
    )


    scheduler.start()
    
    yield # The FastAPI server runs while yielding here
    
    # 4. Shut down the scheduler cleanly when the server stops
    scheduler.shutdown()

# Update your FastAPI instance to use the lifespan manager
app = FastAPI(
    title="Imperium Alumni Platform API",
    description=(
        "## Imperium Alumni Platform\n\n"
        "Backend API for the Imperium Alumni Portal, providing:\n"
        "- **Authentication** (signup, OTP verification, login)\n"
        "- **Placement Readiness Score (PRS)** — Module 2 AI evaluation engine\n"
        "- **Opportunity Intelligence** — Module 1 job/internship matching\n"
        "- **Profile Management** — resume upload, skill and project tracking\n\n"
        "### PRS Evaluation Pipeline\n"
        "The PRS engine runs five pillars in sequence:\n"
        "1. Skill Readiness (30%)\n"
        "2. Projects + Experience (25%)\n"
        "3. Role Alignment (20%)\n"
        "4. Resume Quality (15%)\n"
        "5. Certificate Quality (10%)\n"
    ),
    version="1.0.0",
    contact={"name": "Imperium Dev Team"},
    openapi_tags=[
        {"name": "Auth",        "description": "Signup, OTP verification, and login"},
        {"name": "PRS",         "description": "Placement Readiness Score evaluation, history, and results"},
        {"name": "Profile",     "description": "Resume upload and profile management"},
        {"name": "Opportunities","description": "Opportunity ingestion, sync, and matching"},
        {"name": "Health",       "description": "Service health check"},
    ],
    lifespan=lifespan,
)

# --- NEW CORS CONFIGURATION ---
from fastapi.middleware.cors import CORSMiddleware

# Make sure this block is right under your 'app = FastAPI()' line!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------

# NOTE: Delete the old @app.on_event("startup") function entirely!
# --- SECURITY UTILITIES ---
# --- SECURITY UTILITIES ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

# Use bcrypt directly — passlib 1.7.4 is incompatible with bcrypt >= 4.x
# (passlib's detect_wrap_bug() test uses a 73-byte password that bcrypt 4.x rejects)
pwd_context = None  # kept for reference, not used

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt directly.
    bcrypt has a hard 72-byte limit; passwords over that are truncated by the
    algorithm anyway, so we hash the encoded bytes directly.
    """
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time comparison via bcrypt.checkpw."""
    return _bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def generate_otp() -> str:
    # Generates a 6-digit numeric string
    return str(random.randint(100000, 999999))

def send_otp_email(receiver_email: str, otp: str):

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    sender_email = os.getenv("SMTP_USERNAME")
    sender_password = os.getenv("SMTP_PASSWORD")

    subject = "PathPilot Verification OTP"

    body = f"""
    Your verification OTP is:

    {otp}

    This OTP will expire in 10 minutes.

    - PathPilot Team
    """

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:

        server = smtplib.SMTP(
            smtp_server,
            smtp_port
        )

        server.starttls()

        server.login(
            sender_email,
            sender_password
        )

        server.send_message(msg)

        server.quit()

        print(f"OTP email sent to {receiver_email}")

    except Exception as e:

        print(f"Email sending failed: {e}")
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- AUTHENTICATION ENDPOINTS ---

@app.post("/auth/signup")
def signup(user_data: schemas.UserSignup, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email already registered and verified.")
        # If unverified, we will overwrite the old OTP
        user = existing_user
    else:
        user = models.User(email=user_data.email)
        db.add(user)

    user.hashed_password = get_password_hash(user_data.password)
    user.otp_code = generate_otp()
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    user.is_verified = False

    db.commit()
    
    # In a production environment, you would use smtplib or a service like AWS SES here.
    # For development, print the OTP to the terminal.
    send_otp_email(
    user.email,
    user.otp_code
        )

    return {"message": "Signup successful. Please check your email for the OTP."}


@app.post("/auth/verify-otp")
def verify_otp(request: schemas.OTPVerify, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    if user.is_verified:
        raise HTTPException(status_code=400, detail="User is already verified.")

    if not user.otp_code or user.otp_code != request.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    if datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    # Mark user as verified and clear the OTP
    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()

    return {"message": "Email verified successfully. You can now complete your profile."}


@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(request: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Invalid email or password.")
        
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=404, detail="Invalid email or password.")
        
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email is not verified. Please verify your OTP.")

    access_token_expires = timedelta(hours=24)
    access_token = create_access_token(
        data={"sub": user.email, "id": user.id,"name": user.name if user.name else ""}, 
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    # 1. Test Database Connectivity
    db_status = "Healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"Unhealthy: {str(e)}"

    # 2. Test MinIO Storage Connectivity
    storage_status = "Healthy"
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT')}",
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY")
        )
        # Check if it can read the buckets
        s3_client.list_buckets()
    except Exception as e:
        storage_status = f"Unhealthy: {str(e)}"

    return {
        "status": "online",
        "dependencies": {
            "postgres_pgvector": db_status,
            "minio_object_storage": storage_status
        }
    }


@app.get(
    "/prs/roles",
    response_model=schemas.PRSRoleListResponse,
    tags=["PRS"],
    summary="List supported target roles",
    description=(
        "Returns the full list of roles that can be evaluated by the PRS engine. "
        "A role appears here only when it has a complete role-skill mapping in the dataset. "
        "Dataset warnings are included for diagnostics but do not block role selection."
    ),
)
def get_prs_roles():
    """
    Return the dataset-backed roles that can be evaluated by Module 2.

    A role appears here only when it has a role-skill mapping, because that
    mapping is the critical dataset for PRS scoring. Dataset warnings are
    exposed for diagnostics, but they do not block role selection.
    """
    try:
        datasets = load_prs_datasets()
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "PRS datasets are missing or invalid.",
                "errors": exc.errors,
            },
        )

    return {
        "roles": [{"name": role} for role in datasets.roles],
        "warnings": datasets.warnings,
    }


@app.get(
    "/prs/assessment",
    response_model=schemas.PRSAssessmentResponse,
    tags=["PRS"],
    summary="Get assessment questions",
    description=(
        "Returns assessment questions for Module 2. "
        "Without ?role=: returns the 5 generic questions (backward compatible). "
        "With ?role=<role_name>: returns 5 generic + 5 role-specific questions (10 total). "
        "These questions are backend-owned — never accept client-calculated answers. "
        "Pass the selected option codes in `assessment_answers` when calling POST /prs/evaluate."
    ),
)
def get_prs_assessment(role: str = ""):
    """Return backend-owned assessment questions for Module 2 (5 generic + 5 role-specific)."""
    from app.services.prs.assessment_service import get_combined_questions
    return {"questions": get_combined_questions(role)}


# ---------------------------------------------------------------------------
# Phase 5  -- PRS Input Builder endpoints
# Phase 6  -- Skill Readiness Engine
# Phase 7  -- Projects + Experience Engine
# Phase 8  -- Certificate Quality Engine
# Phase 9  -- Resume Quality Engine
# Phase 10 -- Role Alignment Engine
# Phase 11 -- PRS Orchestrator
# Phase 12 -- Recommendation Engine
# ---------------------------------------------------------------------------
from app.services.prs.input_builder import build_prs_input, prs_input_to_dict
from app.services.prs.skill_engine import calculate_skill_readiness
from app.services.prs.projects_engine import calculate_projects_experience
from app.services.prs.certificate_engine import calculate_certificate_quality
from app.services.prs.resume_engine import calculate_resume_quality
from app.services.prs.role_alignment_engine import calculate_role_alignment
from app.services.prs.orchestrator import orchestrate_prs
from app.services.prs.recommendation_engine import generate_recommendations
from sqlalchemy.orm import joinedload


def _get_current_user_id(token: str) -> int | None:
    """Decode JWT and return user id. Returns None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("id"))
    except Exception:
        return None


def _resolve_user_from_token(
    authorization: str | None,
    user_id_fallback: int | None,
    db: Session,
):
    """
    Resolve the authenticated User ORM object.

    Priority:
    1. Bearer token in Authorization header  → trusted identity
    2. user_id_fallback query param           → legacy prototype path

    Never trusts a client-supplied user_id when a valid token is present.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        uid = _get_current_user_id(token)
        if uid:
            user = (
                db.query(models.User)
                .options(
                    joinedload(models.User.skills),
                    joinedload(models.User.projects),
                )
                .filter(models.User.id == uid)
                .first()
            )
            if not user:
                raise HTTPException(status_code=404, detail="Authenticated user not found.")
            return user

    # Legacy fallback — still validates that the user exists
    if user_id_fallback:
        user = (
            db.query(models.User)
            .options(
                joinedload(models.User.skills),
                joinedload(models.User.projects),
            )
            .filter(models.User.id == user_id_fallback)
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return user

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide a Bearer token or user_id.",
    )


@app.post(
    "/prs/evaluate",
    response_model=schemas.PRSEvaluationResponse,
    tags=["PRS"],
    summary="Run full PRS evaluation",
    description=(
        "Runs the complete PRS pipeline for the authenticated user against the selected target role.\n\n"
        "**Pipeline (Phases 6-12):**\n"
        "1. Skill Readiness Engine (weight: 30%)\n"
        "2. Projects + Experience Engine (weight: 25%)\n"
        "3. Certificate Quality Engine (weight: 10%)\n"
        "4. Resume Quality Engine (weight: 15%)\n"
        "5. Role Alignment Engine (weight: 20%)\n"
        "6. PRS Orchestrator — computes final score + readiness level\n"
        "7. Recommendation Engine — gap-closing recommendations\n\n"
        "**Security:** User identity is always resolved from the JWT Bearer token. "
        "Never accepts client-submitted component scores. "
        "Role is validated against the dataset before evaluation."
    ),
)
def evaluate_prs(
    request: schemas.PRSEvaluateRequest,
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Phase 5-12 -- Full PRS Pipeline.

    Runs all five pillar engines, orchestrator, and recommendation engine:
      - Phase 6:  Skill Readiness Engine       -> skill_readiness_score
      - Phase 7:  Projects + Experience Engine -> projects_experience_score
      - Phase 8:  Certificate Quality Engine   -> certificate_quality_score
      - Phase 9:  Resume Quality Engine        -> resume_quality_score
      - Phase 10: Role Alignment Engine        -> role_alignment_score
      - Phase 11: PRS Orchestrator             -> prs_score + readiness_level
      - Phase 12: Recommendation Engine        -> recommendations

    Security: user identity always resolved from JWT -- never from client.
    """
    # 1. Resolve identity
    user = _resolve_user_from_token(authorization, user_id, db)

    # 2. Validate the target role against the dataset
    try:
        datasets = load_prs_datasets()
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "PRS datasets unavailable.", "errors": exc.errors},
        )

    available_roles = {r.lower() for r in datasets.roles}
    if request.target_role.strip().lower() not in available_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Role '{request.target_role}' is not in the supported role list.",
        )

    # 3. Validate assessment answers (generic + role-specific)
    try:
        validated_answers = validate_combined_answers(
            request.assessment_answers, request.target_role.strip()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # 4. Build normalized PRS input
    try:
        prs_input = build_prs_input(
            user=user,
            target_role=request.target_role.strip(),
            assessment_answers=validated_answers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # -- Phase 6: Skill Readiness Engine --
    skill_result = calculate_skill_readiness(prs_input, datasets)

    # -- Phase 7: Projects + Experience Engine --
    proj_result = calculate_projects_experience(prs_input, datasets)

    # Blend role-specific depth score (10% weight) into project pillar score
    role_depth = score_role_specific(validated_answers, request.target_role.strip())
    proj_result.score = round(
        proj_result.score * 0.90 + role_depth * 0.10, 2
    )

    # -- Phase 8: Certificate Quality Engine --
    cert_result = calculate_certificate_quality(prs_input, datasets)

    # -- Phase 9: Resume Quality Engine --
    resume_result = calculate_resume_quality(prs_input, datasets)

    # -- Phase 10: Role Alignment Engine --
    alignment_result = calculate_role_alignment(prs_input, datasets)

    # -- Phase 11: PRS Orchestrator --
    # Collect all engine-level weak areas to feed into the orchestrator
    engine_weak_areas = (
        proj_result.weak_areas
        + cert_result.weak_areas
        + resume_result.weak_areas
        + alignment_result.weak_areas
    )
    prs_result = orchestrate_prs(
        target_role=prs_input.target_role,
        skill_readiness_score=skill_result.score,
        projects_experience_score=proj_result.score,
        role_alignment_score=alignment_result.score,
        resume_quality_score=resume_result.score,
        certificate_quality_score=cert_result.score,
        engine_weak_areas=engine_weak_areas,
        missing_skills=skill_result.missing_skills,
    )

    # -- Phase 12: Recommendation Engine --
    rec_result = generate_recommendations(prs_input, prs_result, datasets)

    # -- Persist complete PRS evaluation --
    evaluation = models.ReadinessEvaluation(
        user_id=user.id,
        target_role=prs_input.target_role,
        assessment_answers=validated_answers,
        # Pillar scores
        skill_readiness_score=round(skill_result.score, 2),
        projects_experience_score=round(proj_result.score, 2),
        certificate_quality_score=round(cert_result.score, 2),
        resume_quality_score=round(resume_result.score, 2),
        role_alignment_score=round(alignment_result.score, 2),
        # Phase 11: final PRS
        prs_score=prs_result.prs_score,
        readiness_level=prs_result.readiness_level,
        # Diagnostics
        matched_skills=skill_result.matched_skills,
        partial_matches=skill_result.partial_matches,
        missing_skills=prs_result.missing_skills,
        weak_areas=prs_result.weak_areas,
        score_breakdown={
            "skill_readiness":     skill_result.to_dict(),
            "projects_experience": proj_result.to_dict(),
            "certificate_quality": cert_result.to_dict(),
            "resume_quality":      resume_result.to_dict(),
            "role_alignment":      alignment_result.to_dict(),
            "orchestrator":        prs_result.to_dict(),
            "recommendations":     rec_result.to_dict(),
            "prs_input_snapshot":  prs_input_to_dict(prs_input),
            "phases_complete": [
                "input_builder",
                "skill_readiness",
                "projects_experience",
                "certificate_quality",
                "resume_quality",
                "role_alignment",
                "orchestrator",
                "recommendation_engine",
            ],
        },
        # Phase 12: structured flat recommendation list
        recommendations=rec_result.flat_list(),
        engine_version="prs-v1",
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    return evaluation


@app.get("/prs/input-preview", response_model=schemas.PRSInputDebugResponse)
def preview_prs_input(
    target_role: str,
    assessment_answers: str = "{}",
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Phase 5 diagnostic endpoint — returns the normalized PRSInput without
    running any scoring engine or persisting data.

    Useful for verifying that the correct profile data will flow into the
    PRS engines. Resume text is excluded for privacy.

    assessment_answers should be passed as a JSON string query param.
    Example: ?target_role=AI+Engineer&assessment_answers={}
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    try:
        parsed_answers = json.loads(assessment_answers)
    except (json.JSONDecodeError, TypeError):
        parsed_answers = {}

    # Use empty validated answers for preview
    try:
        validated = validate_assessment_answers(parsed_answers) if parsed_answers else {}
    except ValueError:
        validated = {}

    try:
        prs_input = build_prs_input(
            user=user,
            target_role=target_role.strip() or "Preview",
            assessment_answers=validated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return prs_input_to_dict(prs_input)


@app.get(
    "/prs/latest",
    response_model=schemas.PRSEvaluationResponse,
    tags=["PRS"],
    summary="Get latest evaluation for a role",
    description=(
        "Returns the most recent PRS evaluation for the authenticated user for a specific role. "
        "Role matching is case-insensitive. "
        "Returns 404 if no evaluation exists for this role yet. "
        "Use POST /prs/evaluate to create one."
    ),
)
def get_prs_latest(
    role: str,
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Return the most recent PRS evaluation for the authenticated user
    for a specific role. Role matching is case-insensitive.
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    # Case-insensitive role search using lower() on both sides
    from sqlalchemy import func as sqlfunc
    evaluation = (
        db.query(models.ReadinessEvaluation)
        .filter(
            models.ReadinessEvaluation.user_id == user.id,
            sqlfunc.lower(models.ReadinessEvaluation.target_role) == role.strip().lower(),
        )
        .order_by(models.ReadinessEvaluation.created_at.desc())
        .first()
    )

    if not evaluation:
        raise HTTPException(
            status_code=404,
            detail=f"No PRS evaluation found for role '{role}'. Run POST /prs/evaluate first.",
        )

    return evaluation


@app.get(
    "/prs/history",
    response_model=list[schemas.PRSEvaluationHistoryItem],
    tags=["PRS"],
    summary="Get evaluation history",
    description=(
        "Returns all past PRS evaluations for the authenticated user, ordered newest first. "
        "Returns a lightweight summary per evaluation (no full score breakdown). "
        "Use GET /prs/evaluations/{evaluation_id} to fetch a specific full evaluation. "
        "Supports `limit` (max results, default 20, max 100) and `skip` (offset for pagination)."
    ),
)
def get_prs_history(
    limit: int = 20,
    skip: int = 0,
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Return all past PRS evaluations for the authenticated user,
    ordered newest first. Paginated with limit/skip.
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    # Clamp limit to 1-100
    limit = max(1, min(limit, 100))
    skip  = max(0, skip)

    evaluations = (
        db.query(models.ReadinessEvaluation)
        .filter(models.ReadinessEvaluation.user_id == user.id)
        .order_by(models.ReadinessEvaluation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return evaluations


@app.get(
    "/prs/evaluations/{evaluation_id}",
    response_model=schemas.PRSEvaluationResponse,
    tags=["PRS"],
    summary="Get a specific evaluation by ID",
    description=(
        "Returns the full PRS evaluation record for the given ID, including the complete "
        "score breakdown (all five pillars, orchestrator output, and recommendations). "
        "Users can only access their own evaluations — attempting to access another user's "
        "evaluation returns 404, not 403, to prevent user enumeration."
    ),
)
def get_prs_evaluation(
    evaluation_id: int,
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Return a specific PRS evaluation by its id.
    Users can only access their own evaluations.
    404 is returned (not 403) to prevent user ID enumeration.
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    evaluation = (
        db.query(models.ReadinessEvaluation)
        .filter(
            models.ReadinessEvaluation.id == evaluation_id,
            models.ReadinessEvaluation.user_id == user.id,
        )
        .first()
    )

    if not evaluation:
        raise HTTPException(
            status_code=404,
            detail=f"PRS evaluation {evaluation_id} not found or access denied.",
        )

    return evaluation



# --- UPLOAD ENDPOINT ---
@app.post("/profile/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    user_id: int | None = Form(default=None),   # legacy fallback — prefer JWT
    db: Session = Depends(get_db)
):
    """
    Accepts a PDF, reads it into memory for AI extraction, saves the file to MinIO,
    and returns both the pre-signed storage URL and the Gemini-structured profile data.

    Auth: Bearer token preferred; user_id form-param accepted as legacy fallback.
    """
    # BUG-001 fix: resolve user identity from JWT first, user_id as fallback
    user = _resolve_user_from_token(authorization, user_id, db)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are allowed.")

    # 1. Read file bytes into memory for the PyMuPDF parser
    file_bytes = await file.read()

    # 2. Extract text from PDF — raises ValueError for image/scanned PDFs
    resume_text = extraction.parse_pdf_from_bytes(file_bytes)
    try:
        extracted_ai_data = extraction.extract_profile_data(resume_text)
    except ValueError as ve:
        # Empty/image PDF detected — return 400 with human-readable detail
        raise HTTPException(status_code=400, detail=str(ve))

    # 3. CRITICAL: Reset the file pointer to the beginning of the file.
    # Because we just read the file for the AI, the pointer is at the end.
    # If we don't reset it to 0, MinIO will upload an empty 0-byte file.
    await file.seek(0)

    s3_client = boto3.client(
        "s3",
        endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT')}",
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY")
    )

    bucket_name = os.getenv("MINIO_BUCKET_NAME")
    unique_filename = f"user_{user.id}_{uuid.uuid4().hex}.pdf"  # use resolved user.id

    try:
        # Check if the bucket exists; create if missing
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except Exception:
            s3_client.create_bucket(Bucket=bucket_name)

        # 4. Upload the physical PDF to MinIO
        s3_client.upload_fileobj(
            file.file,
            bucket_name,
            unique_filename,
            ExtraArgs={"ContentType": "application/pdf"}
        )

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': unique_filename},
            ExpiresIn=604800  # BUG-005 partial fix: 7 days instead of 15 minutes
        )

        # 5. Return both the storage data and the AI data to the frontend
        return {
            "message": "Resume parsed and uploaded successfully",
            "file_key": unique_filename,
            "presigned_url": presigned_url,
            "extracted_data": extracted_ai_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    
@app.post("/profile/save", response_model=schemas.UserProfileResponse)
def save_user_profile(
    profile_data: schemas.UserProfileCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    # BUG-001 fix: resolve user from JWT first; fall back to email lookup for legacy calls
    try:
        db_user = _resolve_user_from_token(authorization, None, db)
    except HTTPException:
        # No valid token — fall back to email lookup (existing behavior preserved)
        db_user = db.query(models.User).filter(models.User.email == profile_data.email).first()

    try:
        if not db_user:
            # Final fallback: look up by email from request body
            db_user = db.query(models.User).filter(models.User.email == profile_data.email).first()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found. Please sign up first.")
        
        if profile_data.resume_url:
            db_user.resume_url = profile_data.resume_url  # Save the MinIO file key to the user's record for reference

        # 2. Generate the mathematical embedding vector (non-blocking — embedding failure never stops a save)
        embedding_vector = None
        try:
            skill_text = ", ".join([skill.skill for skill in profile_data.skills])
            project_text = " ".join([f"{p.name}: {p.description}" for p in profile_data.projects])
            experience_text = ", ".join(profile_data.experience)
            full_profile_text = f"Skills: {skill_text}. Projects: {project_text}. Experience: {experience_text}. Interests: {', '.join(profile_data.career_interests)}"
            embedding_vector = embeddings.generate_embedding(full_profile_text)
            if embedding_vector is not None:
                embedding_vector = embedding_vector.tolist() \
                    if hasattr(embedding_vector, "tolist") \
                    else list(embedding_vector)
        except Exception as emb_err:
            print(f"[profile/save] Embedding generation skipped (non-fatal): {emb_err}")
            embedding_vector = None


        # 3. Update the existing user record with the new resume data
        db_user.name = profile_data.name
        db_user.college = profile_data.college
        db_user.department = profile_data.department
        db_user.graduation_year = profile_data.graduation_year
        db_user.cgpa = profile_data.cgpa
        def _norm_url(url: str | None) -> str | None:
            """Normalize user-typed URLs: add https:// if scheme is missing."""
            if not url:
                return None
            url = str(url).strip()
            if url and not url.startswith(("http://", "https://")):
                url = "https://" + url
            return url or None

        db_user.github_url = _norm_url(profile_data.github_url)
        db_user.linkedin_url = _norm_url(profile_data.linkedin_url)

        db_user.career_interests = profile_data.career_interests
        db_user.opportunity_preferences = (
        profile_data.opportunity_preferences
        )
        db_user.experience = profile_data.experience
        db_user.experience_duration = profile_data.experience_duration
        # Write certifications extracted by Gemini into the dedicated JSON column
        # so certificate_engine can score them on next PRS run
        db_user.certifications = profile_data.certifications or []
        db_user.profile_embedding = embedding_vector if embedding_vector else None
 

        # 4. Clear old skills and projects to prevent duplicates if they update their profile later
        db.query(models.UserSkill).filter(models.UserSkill.user_id == db_user.id).delete()
        db.query(models.UserProject).filter(models.UserProject.user_id == db_user.id).delete()

        # 5. Append specific skills
        for skill_item in profile_data.skills:
            db_skill = models.UserSkill(
                user_id=db_user.id,
                skill=skill_item.skill,
                category=skill_item.category if skill_item.category else "General",
                domain="Uncategorized"
            )
            db.add(db_skill)

        # 6. Append relevant projects
        for proj_item in profile_data.projects:
            db_project = models.UserProject(
                user_id=db_user.id,
                name=proj_item.name,
                description=proj_item.description,
                domain=proj_item.domain,
                skills_used=proj_item.skills_used
            )
            db.add(db_project)

        db.commit()
        db.refresh(db_user)
        return db_user

    except Exception as e:
        import traceback
        traceback.print_exc()

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Database profile synchronization failed: {str(e)}"
        )

@app.get(
    "/profile/{user_id}",
    response_model=schemas.UserProfileResponse
)
def get_profile(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    # BUG-001 fix: JWT takes precedence; user_id path param used as fallback
    user = _resolve_user_from_token(authorization, user_id, db)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "college": user.college,
        "department": user.department,
        "graduation_year": user.graduation_year,
        "cgpa": user.cgpa,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "resume_url": user.resume_url,
        "career_interests":
            user.career_interests or [],
        "opportunity_preferences":
            user.opportunity_preferences or [],
        "experience":
            user.experience or [],
        "experience_duration":
            user.experience_duration,
        # certifications must be returned so edit page doesn't wipe them on re-save
        "certifications": user.certifications or [],
        "skills": [
            {
                "skill": s.skill,
                "category": s.category
            }
            for s in user.skills
        ],
        "projects": [
            {
                "name": p.name,
                "description": p.description,
                "domain": p.domain,
                "skills_used":
                    p.skills_used or []
            }
            for p in user.projects
        ]
    }



@app.post("/opportunities/ingest", response_model=schemas.OpportunityResponse)
def ingest_opportunity(job_data: schemas.OpportunityCreate, db: Session = Depends(get_db)):
    """
    Accepts standardized job data, performs SHA-256 deduplication based on Company, Title, 
    and Location, vectorizes the job description, and saves it to PostgreSQL.
    """
    try:
        # 1. Create the deduplication hash
        hash_string = f"{job_data.company}_{job_data.title}_{job_data.location}".lower()
        job_hash = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
        
        # 2. Check if this job already exists to prevent duplicates
        existing_job = db.query(models.Opportunity).filter(models.Opportunity.external_hash == job_hash).first()
        if existing_job:
            raise HTTPException(status_code=409, detail=f"Duplicate job detected. ID: {existing_job.id}")

        # 3. Generate the semantic vector for the job description
        full_job_text = f"""
        Title: {job_data.title}
        Company: {job_data.company}
        Type: {job_data.opportunity_type}

        Required Skills:
        {", ".join(job_data.required_skills)}

        Preferred Skills:
        {", ".join(job_data.preferred_skills)}

        Description:
        {job_data.description}
        """
        description_vector = embeddings.generate_embedding(full_job_text)
        
        # 4. Save the new opportunity to the database
        new_job = models.Opportunity(
            external_hash=job_hash,
            source=job_data.source,
            opportunity_type=job_data.opportunity_type,
            title=job_data.title,
            company=job_data.company,
            location=job_data.location,
            stipend=job_data.stipend,
            is_remote=job_data.is_remote,
            application_url=str(job_data.application_url),
            description=job_data.description,
            required_experience=job_data.required_experience,
            required_skills=job_data.required_skills,
            preferred_skills=job_data.preferred_skills,
            allowed_branches=job_data.allowed_branches,
            allowed_batches=job_data.allowed_batches,
            min_cgpa=job_data.min_cgpa,
            description_embedding=description_vector if description_vector else None
        )
        
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        
        return new_job

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to ingest opportunity: {str(e)}")
    
def seed_query_queue(db: Session):

    user_records = (
        db.query(models.User.career_interests)
        .all()
    )

    unique_queries = set()

    for record in user_records:

        interests = record[0] or []

        for interest in interests:

            interest = interest.strip().lower()

            queries = [

                (
                    f"{interest} fresher jobs Pune India",
                    "full_time",
                    6
                ),

                (
                    f"{interest} internship India",
                    "internship",
                    4
                ),

                (
                    f"{interest} hackathon India",
                    "hackathon",
                    24
                ),

                (
                    f"{interest} fellowship India",
                    "fellowship",
                    12
                ),
            ]

            unique_queries.update(queries)

    for query, category, cooldown in unique_queries:

        exists = (
            db.query(models.QueryQueue)
            .filter(
                models.QueryQueue.query == query
            )
            .first()
        )

        if exists:
            continue

        db.add(
            models.QueryQueue(
                query=query,
                category=category,
                cooldown_hours=cooldown,
                next_run=datetime.utcnow() + timedelta(
                    minutes=random.randint(1, 180)
                )
            )
        )

    db.commit()

def background_opportunity_sync(db: Session):
    # db = SessionLocal()
    try:
        """
        Runs in the background. Queries the database for unique user career interests,
        dynamically builds API adapters for those specific roles, and fetches live opportunities.
        """
        print("--- Starting Dynamic Opportunity Sync ---")
        print("SYNC FUNCTION STARTED")
        # 1. Fetch all career interests from every user in the database
        # This returns a list of tuples containing the JSON arrays, e.g., [(["AI Engineer"],), (["Backend", "AI Engineer"],)]
        due_queries = (
        db.query(models.QueryQueue)
            .filter(
                models.QueryQueue.is_active == True,
                models.QueryQueue.next_run <= datetime.utcnow()
            )
            .limit(2)
            .all()
        )
        if not due_queries:
            print("No due queries.")
            return
        # 4. Dynamically build the adapter list
        active_adapters = []
        
        for queued_query in due_queries:

            active_adapters.append(
                (
                    queued_query,
                    adapters.JSearchAdapter(
                        api_key=os.getenv("RAPIDAPI_KEY"),
                        search_query=queued_query.query
                    )
                )
            )

        # 5. Execute the scrape and save loop
        new_jobs_added = 0
        for queued_query, adapter in active_adapters:
            try:
                print(f"Running query: {queued_query.query}")
                normalized_jobs = adapter.fetch_and_normalize()
                print(f"Fetched {len(normalized_jobs)} jobs")
                db.commit()

                time.sleep(3) # Sleep to be extra safe against rate limits
                
                for job_data in normalized_jobs:
                    hash_string = f"{job_data['company']}_{job_data['title']}_{job_data['location']}".lower()
                    job_hash = hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
                    
                    existing_job = db.query(models.Opportunity).filter(models.Opportunity.external_hash == job_hash).first()
                    if existing_job:
                        continue 

                    full_job_text = f"""
                    Title: {job_data['title']}
                    Company: {job_data['company']}
                    Type: {job_data['opportunity_type']}

                    Required Skills:
                    {", ".join(job_data['required_skills'])}

                    Preferred Skills:
                    {", ".join(job_data['preferred_skills'])}

                    Description:
                    {job_data['description']}
                    """
                    description_vector = embeddings.generate_embedding(full_job_text)
                    
                    new_job = models.Opportunity(
                        external_hash=job_hash,
                        source=job_data['source'],
                        opportunity_type=job_data['opportunity_type'],
                        title=job_data['title'],
                        company=job_data['company'],
                        location=job_data['location'],
                        stipend=job_data.get("stipend"),
                        is_remote=job_data.get("is_remote", False),
                        application_url=str(job_data['application_url']),
                        description=job_data['description'],
                        required_experience=job_data['required_experience'],
                        required_skills=job_data['required_skills'],
                        preferred_skills=job_data['preferred_skills'],
                        allowed_branches=job_data['allowed_branches'],
                        allowed_batches=job_data['allowed_batches'],
                        min_cgpa=job_data['min_cgpa'],
                        description_embedding=description_vector if description_vector else None
                    )
                    db.add(new_job)
                    new_jobs_added += 1
                    users = db.query(models.User).all()

                    for user in users:
                        preferences = (
                            user.opportunity_preferences or []
                        )

                        if (
                            job_data["opportunity_type"]
                            not in preferences
                        ):
                            continue

                        create_notification(
                            db=db,
                            user_id=user.id,
                            opportunity_id=None,
                            title=job_data["title"],
                            message=f"New opportunity at {job_data['company']}",
                            notification_type="opportunity"
                        )

                db.commit()
                
                queued_query.last_run = datetime.utcnow()

                queued_query.next_run = (
                    datetime.utcnow()
                    +
                    timedelta(
                        hours=queued_query.cooldown_hours
                    )
                )

                queued_query.failure_count = 0
            except Exception as e:
                if "429" in str(e):

                    queued_query.next_run = (
                        datetime.utcnow()
                        + timedelta(hours=2)
                    )

                    db.commit()

                    print(f"Rate limited for query: {queued_query.query}")
                queued_query.failure_count += 1

                if queued_query.failure_count >= 5:
                    queued_query.is_active = False

                db.commit()

                print(f"Adapter Sync Error: {e}")

                
        print(f"Background Sync Complete: Added {new_jobs_added} new unique opportunities.")
        
    finally:
        db.close()

def collect_unique_skills(db: Session):
    """
    Collects every unique normalized skill from:
    - user profiles
    - projects
    - opportunities

    Returns a Python set of clean canonical skills.
    """

    all_skills = set()

    # =========================================
    # 1. USER SKILLS
    # =========================================

    user_skills = db.query(models.UserSkill.skill).all()

    for row in user_skills:
        skill = row[0]

        if not skill:
            continue

        skill = skill.strip()

        if len(skill) < 2:
            continue

        normalized = taxonomy.normalize_skill(skill)

        all_skills.add(normalized)

    # =========================================
    # 2. PROJECT SKILLS
    # =========================================

    projects = db.query(models.UserProject.skills_used).all()

    for row in projects:

        skills_list = row[0]

        if not skills_list:
            continue

        for skill in skills_list:

            if not skill:
                continue

            skill = skill.strip()

            if len(skill) < 2:
                continue

            normalized = taxonomy.normalize_skill(skill)

            all_skills.add(normalized)

    # =========================================
    # 3. OPPORTUNITY SKILLS
    # =========================================

    opportunities = db.query(models.Opportunity.required_skills).all()

    for row in opportunities:

        skills_list = row[0]

        if not skills_list:
            continue

        for skill in skills_list:

            if not skill:
                continue

            skill = skill.strip()

            if len(skill) < 2:
                continue

            normalized = taxonomy.normalize_skill(skill)

            all_skills.add(normalized)

    return all_skills


def sync_skill_embeddings(db: Session):
    """
    Generates embeddings for newly discovered skills
    and stores them in the skill_embeddings table.
    """

    # 1. Collect all known skills
    collected_skills = collect_unique_skills(db)

    # 2. Fetch already embedded skills
    existing = db.query(models.SkillEmbedding.skill).all()

    existing_set = {row[0].lower().strip() for row in existing}

    # 3. Find only missing skills
    
    missing_skills = {
        skill for skill in collected_skills
        if skill.lower().strip() not in existing_set
    }



    print(f"Found {len(missing_skills)} new skills requiring embeddings.")

    # 4. Generate embeddings
    for skill in missing_skills:

        embedding = embeddings.generate_embedding(skill)

        if not embedding:
            continue

        db_skill = models.SkillEmbedding(
            skill=skill,
            embedding=embedding
        )

        db.add(db_skill)

    db.commit()

    print("Skill embedding synchronization complete.")


def generate_taxonomy_similarity_report(db: Session):
    """
    Finds highly similar skills not already covered
    inside the taxonomy map.

    Produces a manual-review candidate report.
    """

    print("Starting taxonomy similarity discovery...")

    skill_rows = db.query(models.SkillEmbedding).all()

    report = []

    similarity_threshold = 0.985

    for i in range(len(skill_rows)):

        skill_a = skill_rows[i]

        for j in range(i + 1, len(skill_rows)):

            skill_b = skill_rows[j]

            # Avoid self-comparison
            if skill_a.skill == skill_b.skill:
                continue

            # Skip already mapped taxonomy pairs
            a_clean = skill_a.skill.lower().strip()
            b_clean = skill_b.skill.lower().strip()
            canonical_values = set(taxonomy.TAXONOMY_MAP.values())

            if skill_a.skill in canonical_values and skill_b.skill in canonical_values:
                continue

            if taxonomy.TAXONOMY_MAP.get(a_clean) == skill_b.skill:
                continue

            if taxonomy.TAXONOMY_MAP.get(b_clean) == skill_a.skill:
                continue

            # Vector similarity
            vec_a = np.array(skill_a.embedding)
            vec_b = np.array(skill_b.embedding)

            similarity = float(
                np.dot(vec_a, vec_b) /
                (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
            )

            # Candidate discovery
            if similarity >= similarity_threshold:

                report.append({
                    "candidate_skill": skill_a.skill,
                    "possible_match": skill_b.skill,
                    "similarity": round(float(similarity), 4)
                })

    # Sort strongest matches first
    report.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    # Save report
    with open("taxonomy_report.json", "w") as f:
        json.dump(report, f, indent=4)

    print(f"Generated taxonomy report with {len(report)} candidate pairs.")

    return report


def taxonomy_similarity_report_job():
    """
    Weekly scheduled job for taxonomy discovery.
    """

    db = next(get_db())

    try:

        print("Running weekly taxonomy discovery job...")

        sync_skill_embeddings(db)

        generate_taxonomy_similarity_report(db)

    except Exception as e:

        print(f"Taxonomy discovery job failed: {e}")

    finally:

        db.close()


@app.post("/opportunities/trigger-sync")
def trigger_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    API endpoint to manually trigger the background scraper/sync job.
    Returns immediately so the user isn't waiting for the web scrapers to finish.
    """
    print("TRIGGER ENDPOINT HIT")
    background_tasks.add_task(background_opportunity_sync, db)
    return {"message": "Opportunity synchronization started in the background."}



SEMANTIC_MATCH_THRESHOLD = 0.92
skill_embedding_cache = {}
def get_skill_embedding(
    skill_name: str,
    db: Session
):

    skill_name = taxonomy.normalize_skill(
        skill_name
    )

    cache_key = skill_name.lower().strip()

    # =========================
    # CACHE HIT
    # =========================

    if cache_key in skill_embedding_cache:
        return skill_embedding_cache[cache_key]

    # =========================
    # DATABASE FETCH
    # =========================

    row = (
        db.query(models.SkillEmbedding)
        .filter(
            models.SkillEmbedding.skill == skill_name
        )
        .first()
    )

    if row:

        skill_embedding_cache[cache_key] = row.embedding

        return row.embedding

    # =========================
    # GENERATE NEW EMBEDDING
    # =========================

    embedding = embeddings.generate_embedding(
        skill_name
    )

    new_skill = models.SkillEmbedding(
        skill=skill_name,
        embedding=embedding
    )

    db.add(new_skill)
    db.commit()

    # SAVE TO CACHE
    skill_embedding_cache[cache_key] = embedding

    return embedding

def cosine_similarity(
    vec1,
    vec2
):
    """Cosine similarity between two vectors. Returns 0.0 if either vector is zero-norm."""
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom < 1e-10:  # BUG-004: guard against zero-norm vectors
        return 0.0
    return float(np.dot(v1, v2) / denom)

def is_semantic_skill_match(
    user_skill: str,
    required_skill: str,
    db: Session
):

    user_embedding = get_skill_embedding(
        user_skill,
        db
    )

    required_embedding = get_skill_embedding(
        required_skill,
        db
    )

    similarity = cosine_similarity(
        user_embedding,
        required_embedding
    )

    return similarity >= SEMANTIC_MATCH_THRESHOLD

# Change the response_model to use our new schema
@app.get("/opportunities/matches", response_model=List[schemas.MatchResponse])
def get_personalized_matches(
        authorization: str | None = Header(default=None),
        user_id: int | None = None,   # BUG-003 fix: optional; JWT takes precedence
        limit: int = 30,
        location: str = None,
        opportunity_type: str = None,
        min_score: float = None,
        remote_only: bool = False,
        db: Session = Depends(get_db)
    ):
    # BUG-003 fix: resolve user from JWT, fall back to user_id query param
    user = _resolve_user_from_token(authorization, user_id, db)
    if user.profile_embedding is None:
        raise HTTPException(status_code=400, detail="User profile not vectorized yet. Save your profile first.")
    
    current_batch = user.graduation_year
    # 1. Fetch opportunities, calculating distance and score directly in the DB
    # We use CosineDistance from pgvector.sqlalchemy to ensure DB compatibility
    opportunities = db.query(
        models.Opportunity,
        models.Opportunity.description_embedding.cosine_distance(user.profile_embedding).label("distance")
    ).filter(
        user.cgpa >= models.Opportunity.min_cgpa
    ).order_by(text("distance ASC")).limit(50).all()
    ranked_matches = []
    user_skill_names = set()

    for skill in user.skills:

        normalized = taxonomy.normalize_skill(
            skill.skill
        )

        user_skill_names.add(
            normalized.lower()
        )

        related = taxonomy.RELATED_SKILLS.get(
            normalized,
            []
        )

        for r in related:

            user_skill_names.add(
                r.lower()
            )
    semantic_match_cache = {}
    for opp, distance in opportunities:

        if opp.allowed_batches:
            if current_batch not in opp.allowed_batches:
                continue

        # 2. Convert distance to similarity (0 to 1)
        sim = 1 - distance
        
        # 3. Calculate Skills Overlap
        opp_skills = (
            opp.required_skills or []
        )

        matched = []
        missing = []

        for required_skill in opp_skills:

            required_normalized = (
                taxonomy
                .normalize_skill(required_skill)
                .lower()
            )

            exact_found = (
                required_normalized
                in user_skill_names
            )

            if exact_found:

                matched.append(
                    required_normalized
                )

                continue

            semantic_found = False

            for user_skill in user_skill_names:

                # ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â 2. REPLACE THE OLD LOGIC WITH YOUR CACHE CHECK ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â
                cache_key = (user_skill, required_normalized)

                if cache_key in semantic_match_cache:
                    is_match = semantic_match_cache[cache_key]
                else:
                    is_match = is_semantic_skill_match(
                        user_skill,
                        required_normalized,
                        db
                    )
                    semantic_match_cache[cache_key] = is_match

                if is_match:
                    print(
                        f"Semantic Match: "
                        f"{user_skill} -> {required_normalized}"
                    )
                    semantic_found = True
                    break
                # ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â ---------------------------------------------- ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â

            if semantic_found:

                matched.append(
                    required_normalized
                )

            else:

                missing.append(
                    required_normalized
                )
        skill_score = len(matched) / len(opp_skills) if opp_skills else 0
        
        # 4. Freshness Score
        days_old = (datetime.utcnow() - (opp.posted_date or datetime.utcnow())).days
        freshness = max(0, 1 - (days_old / 30))
        
        # 5. Hybrid Scoring Formula
        final_score = (sim * 0.45) + (skill_score * 0.40) + (freshness * 0.15)
                
        #  # ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸Ãƒâ€¦Ã‚Â¡ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ INSERT INTERNSHIP PRIORITIZATION HERE
        # internship_bonus = 0
        # if current_batch >= 2027:
        #     if opp.opportunity_type and opp.opportunity_type.lower() == "internship":
        #         internship_bonus = 0.15

        # final_score += internship_bonus
        user_preferences = (
            user.opportunity_preferences or []
        )

        if (
            opp.opportunity_type
            and
            opp.opportunity_type in user_preferences
        ):
            final_score += 0.08
        final_score = min(final_score, 1.0)
        

        # Penalty for experience
        # Penalty for senior roles (Fix: Specifically look for years, ignore months)
        exp_lower = (opp.required_experience or "").lower()
        senior_terms = ["3 year", "4 year", "5 year", "3+ year", "4+ year", "5+ year"]
        
        if any(term in exp_lower for term in senior_terms):
            final_score *= 0.5

        ranked_matches.append({
            "opportunity": opp,
            "score": round(final_score, 2),
            "matched_skills": matched,
            "missing_skills": missing
        })

    # Sort by final score descending
    ranked_matches.sort(key=lambda x: x['score'], reverse=True)
    filtered_matches = ranked_matches

    if location:

        filtered_matches = [
            m for m in filtered_matches
            if location.lower()
            in (
                m["opportunity"].location or ""
            ).lower()
        ]

    if opportunity_type:

        filtered_matches = [
            m for m in filtered_matches
            if (
                m["opportunity"]
                .opportunity_type
                .lower()
                ==
                opportunity_type.lower()
            )
        ]

    if min_score:

        filtered_matches = [
            m for m in filtered_matches
            if m["score"] >= min_score
        ]

    if remote_only:

        filtered_matches = [
            m for m in filtered_matches
            if m["opportunity"].is_remote
        ]

    return filtered_matches[:limit]
    # return ranked_matches[:limit]


# @app.get("/profile/{user_id}")
# def get_profile(user_id: int, db: Session = Depends(get_db)):

#     user = db.query(models.User)\
#         .filter(models.User.id == user_id)\
#         .first()

#     if not user:
#         raise HTTPException(
#             status_code=404,
#             detail="User not found"
#         )

#     return user



class GapAnalysisRequest(schemas.BaseModel):
    user_id: int
    target_skills: List[str]

@app.post("/api/v1/skills/analyze-gap")
def analyze_skill_gap(request: GapAnalysisRequest, db: Session = Depends(get_db)):
    """
    Compares a student's known skills against a target list.
    """
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user_skill_names = set()

    for skill in user.skills:

        normalized = taxonomy.normalize_skill(
            skill.skill
        )

        user_skill_names.add(
            normalized.lower()
        )

        related = taxonomy.RELATED_SKILLS.get(
            normalized,
            []
        )

        for r in related:
            user_skill_names.add(
                r.lower()
            )
    
    matched, missing = [], []
    for target in request.target_skills:
        normalized_target = taxonomy.normalize_skill(target)
        if normalized_target.lower() in user_skill_names:
            matched.append(normalized_target)
        else:
            missing.append(normalized_target)

    return {
        "matched_skills": matched,
        "missing_skills": missing
    }
# Temporary endpoint:
@app.post("/admin/sync-skill-embeddings")
def sync_embeddings(
    db: Session = Depends(get_db)
):

    sync_skill_embeddings(db)

    return {
        "message":
        "embeddings synced"
    }

def create_notification(
    db,
    user_id,
    title,
    message,
    notification_type="opportunity",
    opportunity_id=None
):
    existing = (
        db.query(models.UserNotification)
        .filter(
            models.UserNotification.user_id == user_id,
            models.UserNotification.title == title
        )
        .first()
    )

    if existing:
        return

    notification = models.UserNotification(
        user_id=user_id,
        opportunity_id=opportunity_id,
        notification_type=notification_type,
        title=title,
        message=message
    )

    db.add(notification)

@app.get("/notifications/{user_id}")
def get_notifications(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    # BUG-002 fix: resolve from JWT first; path param used as fallback for existing clients
    resolved_user = _resolve_user_from_token(authorization, user_id, db)
    safe_user_id = resolved_user.id  # always use the server-resolved ID

    notifications = (
        db.query(
            models.UserNotification
        )
        .filter(
            models.UserNotification.user_id
            == safe_user_id
        )
        .order_by(
            models.UserNotification.created_at.desc()
        )
        .limit(50)
        .all()
    )

    unread_count = (
        db.query(
            models.UserNotification
        )
        .filter(
            models.UserNotification.user_id
            == safe_user_id,
            models.UserNotification.is_read
            .is_(False)  # BUG-017 fix: use .is_(False) instead of == False
        )
        .count()
    )

    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.notification_type,
                "title": n.title,
                "message": n.message,
                "created_at": n.created_at
            }
            for n in notifications
        ],
        "unread_count": unread_count
    }


@app.post(
    "/notifications/{user_id}/read-all"
)
def mark_all_read(
    user_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
):
    # BUG-002 fix: resolve identity from JWT; path param is fallback
    resolved_user = _resolve_user_from_token(authorization, user_id, db)

    db.query(
        models.UserNotification
    ).filter(
        models.UserNotification.user_id
        == resolved_user.id,
        models.UserNotification.is_read
        .is_(False)  # BUG-017 fix: use .is_(False)
    ).update(
        {
            "is_read": True,
            "read_at": datetime.utcnow()
        }
    )

    db.commit()

    return {
        "message":
        "Notifications marked read"
    }

@app.get("/opportunities/debug")
def debug_opportunities(
    db: Session = Depends(get_db)
):

    opportunities = (
        db.query(models.Opportunity)
        .limit(50)
        .all()
    )

    return [
        {
            "id": o.id,
            "company": o.company,
            "title": o.title,
            "type": o.opportunity_type,
            "location": o.location,
            "remote": o.is_remote,
            "skills": o.required_skills,
            "posted_date": o.posted_date,
        }
        for o in opportunities
    ]


# =============================================================================
# MODULE 3 — Career Path Simulator (M3-9)
# =============================================================================
# Imports for Module 3 engines (placed here to keep M1/M2 imports untouched)
from pydantic import BaseModel, Field
from typing import Optional

from app.services.career.career_orchestrator import orchestrate_career
from app.services.career.what_if_engine      import (
    WhatIfRequest, run_what_if,
    Mutation,
)
from app.services.prs.input_builder import build_prs_input, prs_input_to_dict
from app.services.prs.constants     import INDUSTRY_READY_THRESHOLD


# ---------------------------------------------------------------------------
# Request / Response schemas (inline — small enough to not need schemas.py)
# ---------------------------------------------------------------------------

class CareerSimulateRequest(BaseModel):
    """
    POST /career/simulate request body.

    Fields:
      target_role           role to generate path for (must be in dataset)
      study_hours_per_week  hours/week for ETA calculation (default: user profile default)
      target_prs_score      per-pillar target (default: 70.0 = INDUSTRY_READY_THRESHOLD)
    """
    target_role:          str   = Field(..., example="AI Engineer")
    study_hours_per_week: Optional[int]   = Field(None,  ge=1, le=80, example=10)
    target_prs_score:     Optional[float] = Field(None,  ge=50.0, le=100.0, example=70.0)


class WhatIfApiRequest(BaseModel):
    """
    POST /career/what-if request body.

    Fields:
      target_role                   role context for evaluation
      hypothetical_skills           skill names to add hypothetically
      hypothetical_project          a single project dict to add (name, description, skills_used, domain)
      hypothetical_certifications   cert names to add
    """
    target_role:                  str       = Field(..., example="AI Engineer")
    hypothetical_skills:          list[str] = Field(default_factory=list)
    hypothetical_project:         Optional[dict]    = Field(None)
    hypothetical_certifications:  list[str] = Field(default_factory=list)


class MilestoneCompleteRequest(BaseModel):
    """PATCH /career/path/{id}/milestones/{milestone_id}/complete request body."""
    completed: bool = Field(True)


# ---------------------------------------------------------------------------
# POST /career/simulate
# ---------------------------------------------------------------------------

@app.post(
    "/career/simulate",
    tags=["Career"],
    summary="Generate a full career path simulation",
    description=(
        "Runs the 5-engine Module 3 pipeline for the authenticated user.\n\n"
        "**Requires**: a fresh PRS evaluation (POST /prs/evaluate) for the same role. "
        "Returns HTTP 400 with a hint if none exists.\n\n"
        "**Pipeline**: Gap Analysis → Milestone Generation → ETA → Progression Chain\n\n"
        "**Result is saved** to the career_paths table and returned."
    ),
)
def career_simulate(
    request:       CareerSimulateRequest,
    authorization: str | None = Header(default=None),
    user_id:       int | None = None,
    db:            Session    = Depends(get_db),
):
    """
    Phase M3-9: POST /career/simulate.

    Resolves user from JWT, calls orchestrate_career(), persists the result,
    and returns the full career path JSON.
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    # Resolve study hours: request > user profile default > system default
    study_hours = (
        request.study_hours_per_week
        or getattr(user, "default_study_hours_per_week", None)
        or 10
    )
    target_prs = request.target_prs_score or INDUSTRY_READY_THRESHOLD

    result = orchestrate_career(
        user=user,
        target_role=request.target_role,
        study_hours_per_week=study_hours,
        target_prs_score=target_prs,
        db=db,
    )

    # Persist to career_paths
    path_row = models.CareerPath(
        user_id=user.id,
        target_role=request.target_role.strip(),
        target_prs_score=target_prs,
        study_hours_per_week=study_hours,
        prs_evaluation_id=result.prs_eval_id,
        current_prs_score=round(result.baseline_prs.prs_score, 2),
        current_readiness=result.baseline_prs.readiness_level,
        gap_analysis=result.gap_result.to_dict(),
        milestones=result.milestone_result.to_dict_list(),
        weekly_plan=[w.to_dict() for w in result.eta_result.weekly_plan],
        role_progression=result.progression.to_dict(),
        eta_weeks=result.eta_result.eta_weeks,
        eta_hours=result.eta_result.eta_hours,
        projected_final_prs=result.eta_result.projected_final_prs,
        completed_milestone_ids=[],
        engine_version="cps-v1",
    )
    db.add(path_row)
    db.commit()
    db.refresh(path_row)

    return {
        "career_path_id":       path_row.id,
        "target_role":          path_row.target_role,
        "current_prs_score":    path_row.current_prs_score,
        "current_readiness":    path_row.current_readiness,
        "target_prs_score":     path_row.target_prs_score,
        "projected_final_prs":  path_row.projected_final_prs,
        "eta_weeks":            path_row.eta_weeks,
        "eta_hours":            path_row.eta_hours,
        "study_hours_per_week": path_row.study_hours_per_week,
        "gap_analysis":         path_row.gap_analysis,
        "milestones":           path_row.milestones,
        "weekly_plan":          path_row.weekly_plan,
        "role_progression":     path_row.role_progression,
        "completed_milestone_ids": path_row.completed_milestone_ids,
        "engine_version":       path_row.engine_version,
        "created_at":           path_row.created_at,
    }


# ---------------------------------------------------------------------------
# GET /career/paths
# ---------------------------------------------------------------------------

@app.get(
    "/career/paths",
    tags=["Career"],
    summary="List all career paths for the authenticated user",
)
def list_career_paths(
    authorization: str | None = Header(default=None),
    user_id:       int | None = None,
    db:            Session    = Depends(get_db),
):
    """Return a summary list of all saved career paths for the user."""
    user = _resolve_user_from_token(authorization, user_id, db)

    paths = (
        db.query(models.CareerPath)
        .filter(models.CareerPath.user_id == user.id)
        .order_by(models.CareerPath.created_at.desc())
        .all()
    )

    return [
        {
            "career_path_id":      p.id,
            "target_role":         p.target_role,
            "current_prs_score":   p.current_prs_score,
            "projected_final_prs": p.projected_final_prs,
            "eta_weeks":           p.eta_weeks,
            "milestone_count":     len(p.milestones or []),
            "completed_count":     len(p.completed_milestone_ids or []),
            "engine_version":      p.engine_version,
            "created_at":          p.created_at,
        }
        for p in paths
    ]


# ---------------------------------------------------------------------------
# GET /career/path/{career_path_id}
# ---------------------------------------------------------------------------

@app.get(
    "/career/path/{career_path_id}",
    tags=["Career"],
    summary="Get a single saved career path with full detail",
)
def get_career_path(
    career_path_id: int,
    authorization:  str | None = Header(default=None),
    user_id:        int | None = None,
    db:             Session    = Depends(get_db),
):
    """Return the full career path row including milestones and weekly plan."""
    user = _resolve_user_from_token(authorization, user_id, db)

    path = (
        db.query(models.CareerPath)
        .filter(
            models.CareerPath.id      == career_path_id,
            models.CareerPath.user_id == user.id,
        )
        .first()
    )
    if not path:
        raise HTTPException(status_code=404, detail="Career path not found.")

    return {
        "career_path_id":          path.id,
        "target_role":             path.target_role,
        "current_prs_score":       path.current_prs_score,
        "current_readiness":       path.current_readiness,
        "target_prs_score":        path.target_prs_score,
        "projected_final_prs":     path.projected_final_prs,
        "eta_weeks":               path.eta_weeks,
        "eta_hours":               path.eta_hours,
        "study_hours_per_week":    path.study_hours_per_week,
        "gap_analysis":            path.gap_analysis,
        "milestones":              path.milestones,
        "weekly_plan":             path.weekly_plan,
        "role_progression":        path.role_progression,
        "completed_milestone_ids": path.completed_milestone_ids,
        "last_progress_update":    path.last_progress_update,
        "engine_version":          path.engine_version,
        "created_at":              path.created_at,
        "updated_at":              path.updated_at,
    }


# ---------------------------------------------------------------------------
# PATCH /career/path/{career_path_id}/milestones/{milestone_id}/complete
# ---------------------------------------------------------------------------

@app.patch(
    "/career/path/{career_path_id}/milestones/{milestone_id}/complete",
    tags=["Career"],
    summary="Mark a milestone as completed or uncompleted",
    description=(
        "Toggles a milestone's completion status in `completed_milestone_ids`.\n\n"
        "Set `completed: true` to mark done, `completed: false` to unmark.\n\n"
        "Returns updated progress summary."
    ),
)
def complete_milestone(
    career_path_id: int,
    milestone_id:   str,
    body:           MilestoneCompleteRequest,
    authorization:  str | None = Header(default=None),
    user_id:        int | None = None,
    db:             Session    = Depends(get_db),
):
    """
    Progress tracking endpoint (Design Principle D5).
    Idempotent: marking an already-completed milestone completed is a no-op.
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    path = (
        db.query(models.CareerPath)
        .filter(
            models.CareerPath.id      == career_path_id,
            models.CareerPath.user_id == user.id,
        )
        .first()
    )
    if not path:
        raise HTTPException(status_code=404, detail="Career path not found.")

    # Validate milestone_id exists in this path
    milestone_ids = {m["id"] for m in (path.milestones or [])}
    if milestone_id not in milestone_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Milestone '{milestone_id}' not found in this career path.",
        )

    completed_ids: list = list(path.completed_milestone_ids or [])

    if body.completed and milestone_id not in completed_ids:
        completed_ids.append(milestone_id)
    elif not body.completed and milestone_id in completed_ids:
        completed_ids.remove(milestone_id)

    path.completed_milestone_ids = completed_ids
    path.last_progress_update    = datetime.utcnow()
    db.commit()
    db.refresh(path)

    total      = len(path.milestones or [])
    done_count = len(path.completed_milestone_ids)

    return {
        "career_path_id":          path.id,
        "milestone_id":            milestone_id,
        "completed":               body.completed,
        "completed_count":         done_count,
        "total_milestones":        total,
        "progress_pct":            round(done_count / total * 100, 1) if total else 0.0,
        "last_progress_update":    path.last_progress_update,
    }


# ---------------------------------------------------------------------------
# POST /career/what-if
# ---------------------------------------------------------------------------

@app.post(
    "/career/what-if",
    tags=["Career"],
    summary="Simulate score impact of hypothetical profile changes",
    description=(
        "Applies hypothetical mutations (skills, projects, certifications) to the "
        "user's current profile and returns the projected PRS change.\n\n"
        "**Stateless on the hot path**: results are NOT saved automatically. "
        "The audit log is written asynchronously via BackgroundTask.\n\n"
        "**Requires**: a fresh PRS evaluation for the same role."
    ),
)
def career_what_if(
    request:          WhatIfApiRequest,
    background_tasks: BackgroundTasks,
    authorization:    str | None = Header(default=None),
    user_id:          int | None = None,
    db:               Session    = Depends(get_db),
):
    """
    Phase M3-9: POST /career/what-if.

    Resolves user, gets latest PRS eval, builds PRSInput + PRSResult,
    then calls run_what_if() with the hypothetical mutations.
    Audit log is written asynchronously (fire-and-forget).
    """
    user = _resolve_user_from_token(authorization, user_id, db)

    # Load datasets
    try:
        datasets = load_prs_datasets()
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "Career datasets unavailable.", "errors": exc.errors},
        )

    # Validate role
    available_roles = {r.lower() for r in datasets.roles}
    if request.target_role.strip().lower() not in available_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Role '{request.target_role}' is not supported.",
        )
    target_role = request.target_role.strip()

    # Option B freshness gate
    from app.services.career.career_orchestrator import (
        _get_fresh_prs_eval, _reconstruct_prs_result,
    )
    eval_row     = _get_fresh_prs_eval(user.id, target_role, db)
    baseline_prs = _reconstruct_prs_result(eval_row, target_role)

    # Build PRSInput (for dedup checks in project_delta)
    prs_input = build_prs_input(
        user=user,
        target_role=target_role,
        assessment_answers=eval_row.assessment_answers or {},
    )

    # Build WhatIfRequest
    what_if_req = WhatIfRequest(
        target_role=target_role,
        hypothetical_skills=request.hypothetical_skills,
        hypothetical_project=request.hypothetical_project,
        hypothetical_certifications=request.hypothetical_certifications,
    )

    result = run_what_if(prs_input, baseline_prs, what_if_req, datasets)

    # Fire-and-forget audit log
    def _write_audit_log():
        try:
            log_db = next(get_db())
            try:
                log_row = models.WhatIfLog(
                    user_id=user.id,
                    target_role=target_role,
                    hypothetical_input={
                        "skills":           request.hypothetical_skills,
                        "project":          request.hypothetical_project,
                        "certifications":   request.hypothetical_certifications,
                    },
                    original_prs=result.original_prs_score,
                    simulated_prs=result.simulated_prs_score,
                    delta=result.overall_delta,
                    mutations_applied=result.mutations_applied,
                )
                log_db.add(log_row)
                log_db.commit()
            finally:
                log_db.close()
        except Exception:
            pass  # Audit log failure must never affect the response

    background_tasks.add_task(_write_audit_log)

    return {
        "target_role":          target_role,
        "original_prs_score":   result.original_prs_score,
        "simulated_prs_score":  result.simulated_prs_score,
        "overall_delta":        result.overall_delta,
        "mutations_applied":    result.mutations_applied,
        "mutations_skipped":    result.mutations_skipped,
        "per_mutation":         result.per_mutation,
        "summary":              result.summary,
    }

# ==========================================
# PATHPILOT — LEARNING PATH ROUTES
# ==========================================

@app.get("/learning/goals", tags=["Learning"])
def get_learning_goals():
    datasets_dir = os.getenv("PATHPILOT_DATASET_DIR", "../datasets")
    try:
        with open(os.path.join(datasets_dir, "learning_goals.json"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"goals": []}

@app.post("/learning/chat", response_model=schemas.ChatResponse, tags=["Learning"])
def chat_profiling(
    request: schemas.ChatRequest,
    db: Session = Depends(get_db)
):
    # Fetch session or create new
    if request.session_id:
        session = db.query(models.ChatSession).filter(models.ChatSession.id == request.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        user_id = request.user_id
        if not user_id:
            user_id = 1  # Fallback for prototype
        session = models.ChatSession(user_id=user_id, messages=[])
        db.add(session)
        db.commit()
        db.refresh(session)
        
    engine = ChatEngine()
    history = session.messages
    reply, draft, is_complete = engine.process_message(request.message, history)
    
    # Update session
    messages = list(history)
    messages.append({"role": "user", "content": request.message})
    messages.append({"role": "assistant", "content": reply})
    session.messages = messages
    
    if draft:
        session.extracted_profile = {
            "goal_statement": draft.goal_statement,
            "current_skills": draft.current_skills,
            "experience_level": draft.experience_level,
            "weekly_hours": draft.weekly_hours,
            "interests": draft.interests
        }
        session.is_complete = is_complete
        
    db.commit()
    
    return schemas.ChatResponse(
        reply=reply,
        session_id=session.id,
        extracted_profile=session.extracted_profile if draft else None,
        is_profile_complete=is_complete
    )

@app.post("/learning/path/generate", response_model=schemas.LearningPathResponse, tags=["Learning"])
def generate_path(
    request: schemas.GeneratePathRequest,
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db)
):
    try:
        user = _resolve_user_from_token(authorization, user_id, db)
    except Exception:
        # For simplicity, fallback if no user
        user = db.query(models.User).first()
        
    datasets_dir = os.getenv("PATHPILOT_DATASET_DIR", "../datasets")
    
    try:
        result = generate_learning_path(
            goal_id=request.goal_id,
            current_skills=request.current_skills,
            experience_level=request.experience_level,
            weekly_hours=request.weekly_hours,
            datasets_dir=datasets_dir
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    with open(os.path.join(datasets_dir, "learning_goals.json"), "r") as f:
        goals = json.load(f).get("goals", [])
    goal_name = next((g["name"] for g in goals if g["id"] == request.goal_id), request.goal_id)

    path = models.LearningPath(
        user_id=user.id if user else 1,
        goal_id=request.goal_id,
        goal_name=goal_name,
        experience_level=request.experience_level,
        current_skills=request.current_skills,
        weekly_study_hours=request.weekly_hours,
        phases=result.phases,
        total_courses=len(result.course_list),
        total_weeks=result.total_weeks,
        completed_course_ids=[]
    )
    
    db.add(path)
    db.commit()
    db.refresh(path)
    
    return schemas.LearningPathResponse(
        path_id=path.id,
        goal_name=path.goal_name,
        total_courses=path.total_courses,
        total_weeks=path.total_weeks,
        phases=path.phases,
        skill_gaps=[],
        already_known=[]
    )

@app.get("/learning/path/{path_id}", response_model=schemas.LearningPathResponse, tags=["Learning"])
def get_learning_path(path_id: int, db: Session = Depends(get_db)):
    path = db.query(models.LearningPath).filter(models.LearningPath.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
        
    return schemas.LearningPathResponse(
        path_id=path.id,
        goal_name=path.goal_name,
        total_courses=path.total_courses,
        total_weeks=path.total_weeks,
        phases=path.phases,
        skill_gaps=[],
        already_known=[]
    )

@app.get("/learning/paths", tags=["Learning"])
def get_user_paths(
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db)
):
    try:
        user = _resolve_user_from_token(authorization, user_id, db)
        uid = user.id
    except:
        uid = 1
        
    paths = db.query(models.LearningPath).filter(models.LearningPath.user_id == uid).all()
    return paths

@app.post("/learning/path/{path_id}/progress", tags=["Learning"])
def update_progress(
    path_id: int,
    request: schemas.ProgressUpdateRequest,
    db: Session = Depends(get_db)
):
    path = db.query(models.LearningPath).filter(models.LearningPath.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
        
    completed = set(path.completed_course_ids or [])
    if request.completed:
        completed.add(request.course_id)
    else:
        completed.discard(request.course_id)
        
    # we need to assign a new list to trigger SQLAlchemy's JSON mutation tracking
    path.completed_course_ids = list(completed)
    db.commit()
    return {"status": "success", "completed_courses": path.completed_course_ids}

@app.get("/learning/courses/search", tags=["Learning"])
def search_courses(query: str):
    datasets_dir = os.getenv("PATHPILOT_DATASET_DIR", "../datasets")
    try:
        with open(os.path.join(datasets_dir, "courses_catalog.json"), "r") as f:
            catalog = json.load(f)
            
        results = [c for c in catalog if query.lower() in c.get("title", "").lower() or query.lower() in c.get("description", "").lower()]
        return {"results": results}
    except Exception:
        return {"results": []}

@app.get("/learning/profile", tags=["Learning"])
def get_learning_profile(
    authorization: str | None = Header(default=None),
    user_id: int | None = None,
    db: Session = Depends(get_db)
):
    try:
        user = _resolve_user_from_token(authorization, user_id, db)
    except:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "skills": [s.skill for s in user.skills]
    }
