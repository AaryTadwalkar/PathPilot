"""
app/schemas.py
==============
Pydantic models for request validation and response serialization.
"""

from pydantic import BaseModel, Field, HttpUrl, EmailStr
from typing import Any, Dict, List, Optional
from datetime import datetime

# ==========================================
# USER PROFILE SUBSCHEMAS
# ==========================================

class ProjectSchema(BaseModel):
    """
    Validates data structure for individual user projects extracted from a resume.
    """
    name: str
    description: str
    domain: Optional[str] = None
    skills_used: List[str] = []

class UserSkillSchema(BaseModel):
    """
    Validates structured data for a user skill extracted from a resume or profile.
    """
    skill: str
    category: Optional[str] = None

# ==========================================
# MAIN USER PROFILE SCHEMAS
# ==========================================

class UserProfileCreate(BaseModel):
    """
    Defines the incoming JSON format expected from the frontend or extraction engine
    when creating or modifying a student profile in the database.
    """
    name: Optional[str] = None
    email: EmailStr
    college: Optional[str] = None
    department: Optional[str] = None
    graduation_year: Optional[int] = None
    cgpa: Optional[float] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    career_interests: List[str] = []
    opportunity_preferences: List[str] = ["Internship"]
    experience: List[str] = []  # List of past roles/companies
    experience_duration: Optional[str] = None  # e.g., "6 months", "1 year"
    resume_url: Optional[str] = None
    skills: List[UserSkillSchema] = []
    projects: List[ProjectSchema] = []
    # Certifications extracted from resume (list of cert name strings).
    # Added to flow Gemini-extracted certs → users.certifications → certificate_engine.
    certifications: List[str] = []

class UserProfileResponse(UserProfileCreate):
    """
    Defines the outgoing JSON layout sent back to the client after a profile is successfully saved.
    Includes the auto-assigned database integer primary key.
    """
    id: int
    resume_url: Optional[str] = None

    class Config:
        from_attributes = True

class UserProfileDetailResponse(
    UserProfileResponse
):
    pass

# ==========================================
# OPPORTUNITY SCHEMAS
# ==========================================

class OpportunityCreate(BaseModel):
    """
    Defines strict structural validation for incoming raw opportunity listings
    sourced from platform aggregators or manual university placement entry.
    """
    source: str
    opportunity_type: str  # "Internship", "Full-Time", "Hackathon", "Fellowship"
    title: str
    company: str
    location: str
    application_url: HttpUrl
    description: str
    required_experience: Optional[str] = None  # e.g., "3 months", "0-1 years"
    stipend: Optional[str] = None
    is_remote: bool = False
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    allowed_branches: List[str] = []
    allowed_batches: List[int] = []
    min_cgpa: float = 0.0

    deadline_date: Optional[datetime] = None

class OpportunityResponse(OpportunityCreate):
    """
    Defines the layout returned to the client when querying or serving available opportunities.
    """
    id: int
    external_hash: str
    posted_date: datetime

    class Config:
        from_attributes = True

class MatchResponse(BaseModel):
    opportunity: OpportunityResponse
    score: float
    matched_skills: List[str]
    missing_skills: List[str]

    class Config:
        from_attributes = True

# app/schemas.py

# ==========================================
# AUTHENTICATION SCHEMAS
# ==========================================

class UserSignup(BaseModel):
    email: EmailStr
    password: str

class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

# ==========================================
# PLACEMENT READINESS SCHEMAS
# ==========================================

class PRSEvaluationBase(BaseModel):
    """
    Shared PRS evaluation shape.
    Every record belongs to one user and one selected target role.
    """
    target_role: str
    assessment_answers: Dict[str, Any] = Field(default_factory=dict)
    skill_readiness_score: Optional[float] = None
    projects_experience_score: Optional[float] = None
    role_alignment_score: Optional[float] = None
    resume_quality_score: Optional[float] = None
    certificate_quality_score: Optional[float] = None
    prs_score: Optional[float] = None
    readiness_level: Optional[str] = None
    matched_skills: List[Any] = Field(default_factory=list)
    partial_matches: List[Any] = Field(default_factory=list)
    missing_skills: List[Any] = Field(default_factory=list)
    weak_areas: List[Any] = Field(default_factory=list)
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Any] = Field(default_factory=list)
    engine_version: str = "prs-v1"


class PRSEvaluationCreate(PRSEvaluationBase):
    """
    Internal persistence schema used after backend engines calculate scores.
    Clients must not submit component scores directly.
    """
    user_id: int


class PRSEvaluationResponse(PRSEvaluationBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PRSBreakdownResponse(BaseModel):
    skill_readiness: Dict[str, Any] = Field(default_factory=dict)
    projects_experience: Dict[str, Any] = Field(default_factory=dict)
    role_alignment: Dict[str, Any] = Field(default_factory=dict)
    resume_quality: Dict[str, Any] = Field(default_factory=dict)
    certificate_quality: Dict[str, Any] = Field(default_factory=dict)


class PRSResultResponse(BaseModel):
    evaluation_id: int
    target_role: str
    prs_score: float
    readiness_level: str
    breakdown: PRSBreakdownResponse
    matched_skills: List[Any] = Field(default_factory=list)
    partial_matches: List[Any] = Field(default_factory=list)
    missing_skills: List[Any] = Field(default_factory=list)
    weak_areas: List[Any] = Field(default_factory=list)
    recommendations: List[Any] = Field(default_factory=list)
    calculated_at: datetime


class PRSEvaluationHistoryItem(BaseModel):
    id: int
    target_role: str
    prs_score: Optional[float] = None
    readiness_level: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PRSRoleOption(BaseModel):
    name: str


class PRSRoleListResponse(BaseModel):
    roles: List[PRSRoleOption]
    warnings: List[str] = Field(default_factory=list)

class PRSAssessmentOption(BaseModel):
    code: str
    label: str


class PRSAssessmentQuestion(BaseModel):
    id: str
    question: str
    type: str
    options: List[PRSAssessmentOption]


class PRSAssessmentResponse(BaseModel):
    questions: List[PRSAssessmentQuestion]


# ==========================================
# PHASE 5 — PRS EVALUATE REQUEST / INPUT DEBUG
# ==========================================

class PRSEvaluateRequest(BaseModel):
    """
    Body for POST /prs/evaluate.

    The client sends only the role and the validated assessment answers.
    The backend loads the profile from the authenticated user's database record.
    Component scores are NEVER accepted from the client.
    """
    target_role: str = Field(..., min_length=1, description="Target job role to evaluate")
    assessment_answers: Dict[str, Any] = Field(
        ...,
        description="Validated assessment answer codes from the assessment questions",
    )


class PRSInputDebugResponse(BaseModel):
    """
    Safe serialisation of a PRSInput object returned by GET /prs/input-preview.
    Resume text is intentionally excluded to avoid leaking PII.
    """
    user_id: int
    target_role: str
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    experience_duration: Optional[str] = None
    certifications: List[str] = Field(default_factory=list)
    has_resume_analysis: bool = False
    career_interests: List[str] = Field(default_factory=list)
    assessment_answers: Dict[str, Any] = Field(default_factory=dict)

# ==========================================
# PATHPILOT — LEARNING PATH SCHEMAS
# ==========================================

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    user_id: Optional[int] = None

class ChatResponse(BaseModel):
    reply: str
    session_id: int
    extracted_profile: Optional[Dict[str, Any]] = None
    is_profile_complete: bool = False

class LearningGoalOption(BaseModel):
    id: str
    name: str
    description: str
    difficulty: str
    estimated_weeks: int
    required_skills: List[str]

class GeneratePathRequest(BaseModel):
    goal_id: str
    current_skills: List[str] = []
    experience_level: str = "beginner"  # beginner | intermediate | advanced
    weekly_study_hours: int = 10
    interests: List[str] = []

class CourseItem(BaseModel):
    id: str
    title: str
    provider: str
    url: str
    level: str
    duration_hours: int
    skills_taught: List[str]
    domain: str
    description: str
    is_free: bool
    why_recommended: str = ""

class LearningPhase(BaseModel):
    phase_number: int
    phase_name: str  # "Phase 1: Foundations"
    description: str
    courses: List[CourseItem]
    estimated_weeks: int
    skills_gained: List[str]

class LearningPathResponse(BaseModel):
    path_id: int
    goal_name: str
    total_courses: int
    total_weeks: int
    phases: List[LearningPhase]
    skill_gaps: List[str]
    already_known: List[str]

class ProgressUpdateRequest(BaseModel):
    course_id: str
    completed: bool

class CourseSearchRequest(BaseModel):
    query: str
    level: Optional[str] = None
    domain: Optional[str] = None
