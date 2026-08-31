from sqlalchemy import Boolean  # Boolean column type for PostgreSQL
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, JSON, Index
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from app.database import Base

class User(Base):
    """
    SQLAlchemy model representing the core 'users' table in PostgreSQL.
    Tracks academic info, file URLs, metadata strings, and vector profiles.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    # --- NEW AUTHENTICATION FIELDS ---
    hashed_password = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    # ---------------------------------
    
    college = Column(String)
    department = Column(String)
    graduation_year = Column(Integer)
    cgpa = Column(Float)
    github_url = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    resume_url = Column(String, nullable=True)
    
    # Store dynamic lists directly into Postgres as native JSON structures
    career_interests = Column(
        JSON,
        default=list
    )

    opportunity_preferences = Column(
        JSON,
        default=lambda: ["Internship"]
    )

    experience = Column(
        JSON,
        default=list
    )
    experience_duration = Column(String, nullable=True)

    # Certifications extracted from resume by Gemini (list of cert name strings).
    # Read by input_builder._extract_certifications() → certificate_engine.
    # Example: ["NVIDIA DLI: Fundamentals of Deep Learning", "AWS Cloud Practitioner"]
    certifications = Column(
        JSON,
        default=list,
        nullable=True,
    )

    # Module 3: default study hours per week used for ETA calculations.
    # Can be overridden per-request in /career/simulate.
    default_study_hours_per_week = Column(Integer, default=10, nullable=True)


    # Vector column representing student profile (384 dimensions for BGE models)
    profile_embedding = Column(Vector(384), nullable=True)

    # Database relationships linking records across internal schemas
    skills       = relationship("UserSkill",   back_populates="owner", cascade="all, delete-orphan")
    projects     = relationship("UserProject",  back_populates="owner", cascade="all, delete-orphan")
    career_paths = relationship("CareerPath",   back_populates="owner", cascade="all, delete-orphan")
    what_if_logs = relationship("WhatIfLog",    back_populates="owner", cascade="all, delete-orphan")
    learning_paths = relationship("LearningPath", back_populates="owner", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="owner", cascade="all, delete-orphan")


class UserSkill(Base):
    """
    Represents individual skill rows associated with a unique student user account.
    """
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    skill = Column(String, index=True)
    category = Column(String, nullable=True)
    domain = Column(String, default="Uncategorized")
    
    owner = relationship("User", back_populates="skills")


class UserProject(Base):
    """
    Tracks detailed personal software development or technical engineering project elements.
    """
    __tablename__ = "user_projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    description = Column(Text)
    domain = Column(String, nullable=True)
    skills_used = Column(JSON, default=[])
    
    owner = relationship("User", back_populates="projects")


class Opportunity(Base):
    """
    SQLAlchemy database layout representing external job roles, internships, or hackathons.
    Includes target arrays for explicit filter criteria execution.
    """
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    external_hash = Column(String, unique=True, index=True)
    source = Column(String)
    opportunity_type = Column(String)
    title = Column(String, index=True)
    company = Column(String, index=True)
    location = Column(String)
    application_url = Column(String)
    description = Column(Text)
    required_experience = Column(String, nullable=True)
    
    # Matching configurations stored as native structured lists
    required_skills = Column(JSON, default=[])
    preferred_skills = Column(JSON, default=[])
    allowed_branches = Column(JSON, default=[])
    allowed_batches = Column(JSON, default=[])
    min_cgpa = Column(Float, default=0.0)
    stipend = Column(String, nullable=True)
    is_remote = Column(Boolean, default=False)
    posted_date = Column(DateTime, default=datetime.utcnow)
    deadline_date = Column(DateTime, nullable=True)
    
    # Semantic Search vector targets
    title_embedding = Column(Vector(384), nullable=True)
    description_embedding = Column(Vector(384), nullable=True)



class SkillEmbedding(Base):
    """
    Stores canonical skill embeddings for semantic taxonomy discovery.
    """
    __tablename__ = "skill_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    skill = Column(String, unique=True, index=True)
    embedding = Column(Vector(384), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # TODO: Enable pgvector indexing for production scaling later
    # Requires vector extension to be fully populated first
    # __table_args__ = (
    #     Index('idx_skill_embedding', embedding, postgresql_using='ivfflat', postgresql_with={'lists': 100}),
    # )

class UserNotification(Base):

    __tablename__ = "user_notifications"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        index=True
    )

    opportunity_id = Column(
        Integer,
        ForeignKey("opportunities.id"),
        nullable=True
    )

    notification_type = Column(
        String,
        default="opportunity"
    )

    title = Column(String)

    message = Column(Text)

    is_read = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    read_at = Column(
        DateTime,
        nullable=True
    )


class QueryQueue(Base):

    __tablename__ = "query_queue"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    query = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    category = Column(
        String,
        nullable=False
    )

    adapter = Column(
        String,
        default="jsearch"
    )

    cooldown_hours = Column(
        Integer,
        default=6
    )

    last_run = Column(
        DateTime,
        nullable=True
    )

    next_run = Column(
        DateTime,
        default=datetime.utcnow
    )

    failure_count = Column(
        Integer,
        default=0
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
    
class ReadinessEvaluation(Base):
    __tablename__ = "readiness_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    target_role = Column(String, nullable=False, index=True)

    # Stable self-report evidence collected for this exact target role.
    assessment_answers = Column(JSON, default=dict, nullable=False)

    # Phase 1 PRS persistence contract. Final PRS is derived from these
    # component scores using backend-owned deterministic weights.
    skill_readiness_score = Column(Float, nullable=True)
    projects_experience_score = Column(Float, nullable=True)
    role_alignment_score = Column(Float, nullable=True)
    resume_quality_score = Column(Float, nullable=True)
    certificate_quality_score = Column(Float, nullable=True)
    prs_score = Column(Float, nullable=True)
    readiness_level = Column(String, nullable=True)

    matched_skills = Column(JSON, default=list, nullable=False)
    partial_matches = Column(JSON, default=list, nullable=False)
    missing_skills = Column(JSON, default=list, nullable=False)
    weak_areas = Column(JSON, default=list, nullable=False)
    score_breakdown = Column(JSON, default=dict, nullable=False)
    recommendations = Column(JSON, default=list, nullable=False)
    engine_version = Column(String, default="prs-v1", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Legacy prototype columns kept temporarily so the existing experimental
    # endpoint does not break before Phase 13 replaces it with real PRS APIs.
    overall_score = Column(Float)
    skills_score = Column(Float)
    projects_score = Column(Float)
    resume_score = Column(Float)
    recommended_projects = Column(JSON, default=list)
    recommended_courses = Column(JSON, default=list)
    recommended_certifications = Column(JSON, default=list)
    resume_feedback = Column(JSON, default=dict)

    owner = relationship("User")

    __table_args__ = (
        Index(
            "idx_readiness_user_role_created",
            "user_id",
            "target_role",
            "created_at"
        ),
    )


class CareerPath(Base):
    """
    Persisted output of POST /career/simulate for one (user, target_role) pair.

    Use:
      Stores the full Module 3 engine output so the frontend can retrieve
      saved roadmaps without re-running all 5 engines.

    Contains:
      - gap_analysis JSON from GapEngine
      - milestones JSON (ordered list) from MilestoneEngine
      - weekly_plan JSON from ETAEngine
      - role_progression JSON from ProgressionEngine
      - completed_milestone_ids for progress tracking (Design Principle D5)

    Technologies:
      SQLAlchemy ORM over PostgreSQL. JSON columns store rich nested engine
      output without schema churn. Fields inside the JSON blobs are owned by
      the engine layer, not the DB layer, so engine changes don't require
      DB migrations.

    Key design:
      prs_evaluation_id is a FK to readiness_evaluations — Module 3 always
      consumes an existing PRS eval (Option B freshness decision). This FK
      records which eval was the basis for the roadmap.
    """
    __tablename__ = "career_paths"

    id                      = Column(Integer, primary_key=True, index=True)
    user_id                 = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),                   nullable=False, index=True)
    target_role             = Column(String(255), nullable=False, index=True)
    target_prs_score        = Column(Float, default=70.0)
    study_hours_per_week    = Column(Integer, default=10)
    prs_evaluation_id       = Column(Integer, ForeignKey("readiness_evaluations.id", ondelete="SET NULL"),  nullable=True)

    # PRS snapshot at time of generation
    current_prs_score       = Column(Float, nullable=True)
    current_readiness       = Column(String(100), nullable=True)

    # Engine outputs stored as JSON blobs
    gap_analysis            = Column(JSON, nullable=False, default=dict)
    milestones              = Column(JSON, nullable=False, default=list)
    weekly_plan             = Column(JSON, nullable=False, default=list)
    role_progression        = Column(JSON, nullable=False, default=dict)

    # ETA summary scalar fields (for quick DB queries without JSON parsing)
    eta_weeks               = Column(Integer, nullable=True)
    eta_hours               = Column(Integer, nullable=True)
    projected_final_prs     = Column(Float, nullable=True)

    # Progress tracking (D5) — list of completed milestone ID strings
    completed_milestone_ids = Column(JSON, nullable=False, default=list)
    last_progress_update    = Column(DateTime, nullable=True)

    engine_version          = Column(String(50), default="cps-v1", nullable=False)
    created_at              = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner        = relationship("User",                back_populates="career_paths")
    prs_eval     = relationship("ReadinessEvaluation", foreign_keys=[prs_evaluation_id])
    what_if_logs = relationship("WhatIfLog",           back_populates="career_path", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_career_paths_user_role", "user_id", "target_role", "created_at"),
    )


class WhatIfLog(Base):
    """
    Audit log for every POST /career/what-if call.

    Use:
      Written asynchronously via FastAPI BackgroundTask so it adds zero
      latency to the hot what-if path. Used for analytics only.

    Contains:
      - The full WhatIfRequest payload as JSON (for replay)
      - original_prs, simulated_prs, delta for trend analysis
      - mutations_applied count for usage analytics

    Technologies:
      SQLAlchemy ORM. Single JSON column stores the full request payload
      to avoid column sprawl as the WhatIfRequest schema evolves.

    Key design:
      career_path_id is nullable — /career/what-if can be called without
      first saving a career path (stateless what-if use case).
    """
    __tablename__ = "what_if_logs"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id",        ondelete="CASCADE"),  nullable=False, index=True)
    career_path_id      = Column(Integer, ForeignKey("career_paths.id", ondelete="SET NULL"), nullable=True)
    target_role         = Column(String(255), nullable=False)
    hypothetical_input  = Column(JSON, nullable=False)   # full WhatIfRequest payload
    original_prs        = Column(Float, nullable=True)
    simulated_prs       = Column(Float, nullable=True)
    delta               = Column(Float, nullable=True)
    mutations_applied   = Column(Integer, default=0)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner       = relationship("User",       back_populates="what_if_logs")
    career_path = relationship("CareerPath", back_populates="what_if_logs")

    __table_args__ = (
        Index("idx_what_if_logs_user", "user_id", "created_at"),
    )

class LearningPath(Base):
    """
    Stores a generated personalized learning path for a learner.
    Created by POST /learning/path/generate.
    Each record = one (user, goal) path generation.
    """
    __tablename__ = "learning_paths"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    goal_id = Column(String, nullable=False)  # e.g. "GOAL_ML_ENGINEER"
    goal_name = Column(String, nullable=False)
    experience_level = Column(String, nullable=False)  # beginner/intermediate/advanced
    current_skills = Column(JSON, default=list)
    weekly_study_hours = Column(Integer, default=10)
    phases = Column(JSON, default=list)  # ordered learning phases
    total_courses = Column(Integer, default=0)
    total_weeks = Column(Integer, default=0)
    completed_course_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="learning_paths")


class ChatSession(Base):
    """Stores conversation history for the learner profiling chat interface."""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    messages = Column(JSON, default=list)  # [{role, content, timestamp}]
    extracted_profile = Column(JSON, default=dict)  # LearnerProfileDraft as dict
    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="chat_sessions")
