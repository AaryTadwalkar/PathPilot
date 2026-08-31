import { apiRequest } from "@/lib/api";

// ============================================================
// ROLE SELECTION
// ============================================================

export interface PRSRoleOption {
  name: string;
}

export interface PRSRoleListResponse {
  roles: PRSRoleOption[];
  warnings: string[];
}

// ============================================================
// ASSESSMENT QUESTIONS
// ============================================================

export interface PRSAssessmentOption {
  code: string;
  label: string;
}

export interface PRSAssessmentQuestion {
  id: string;
  question: string;
  type: "single_select" | "multi_select";
  options: PRSAssessmentOption[];
}

export interface PRSAssessmentResponse {
  questions: PRSAssessmentQuestion[];
}

export type AssessmentAnswer = string | string[];

// ============================================================
// PHASE 5 — EVALUATE REQUEST & RESPONSE
// ============================================================

export interface PRSEvaluateRequest {
  target_role: string;
  /** Validated answer codes keyed by question id */
  assessment_answers: Record<string, AssessmentAnswer>;
}

/** Lightweight evaluation history record */
export interface PRSEvaluationHistoryItem {
  id: number;
  target_role: string;
  prs_score: number | null;
  readiness_level: string | null;
  created_at: string;
}

/** Full evaluation record returned by evaluate / get-by-id / latest */
export interface PRSEvaluationResponse {
  id: number;
  user_id: number;
  target_role: string;
  assessment_answers: Record<string, AssessmentAnswer>;
  skill_readiness_score: number | null;
  projects_experience_score: number | null;
  role_alignment_score: number | null;
  resume_quality_score: number | null;
  certificate_quality_score: number | null;
  prs_score: number | null;
  readiness_level: string | null;
  matched_skills: unknown[];
  partial_matches: unknown[];
  missing_skills: unknown[];
  weak_areas: unknown[];
  score_breakdown: Record<string, unknown>;
  recommendations: unknown[];
  engine_version: string;
  created_at: string;
  updated_at: string;
}

/** Debug preview of normalized PRSInput */
export interface PRSInputDebugResponse {
  user_id: number;
  target_role: string;
  skills: Array<{ skill: string; category: string | null }>;
  projects: Array<{
    name: string;
    description: string;
    domain: string | null;
    skills_used: string[];
  }>;
  experience: string[];
  experience_duration: string | null;
  certifications: string[];
  has_resume_analysis: boolean;
  career_interests: string[];
  assessment_answers: Record<string, AssessmentAnswer>;
}

// ============================================================
// API FUNCTIONS
// ============================================================

export async function fetchPrsRoles() {
  return apiRequest<PRSRoleListResponse>("/prs/roles");
}

export async function fetchPrsAssessment(role: string = "") {
  const url = role
    ? `/prs/assessment?role=${encodeURIComponent(role)}`
    : "/prs/assessment";
  return apiRequest<PRSAssessmentResponse>(url);
}

/**
 * Phase 5 — POST /prs/evaluate
 *
 * Sends the selected role and validated assessment answers.
 * The backend resolves the user from the JWT and builds PRSInput from
 * the saved profile. Never sends component scores or raw user_id.
 */
export async function evaluatePrs(
  request: PRSEvaluateRequest
): Promise<PRSEvaluationResponse> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;

  // Always append user_id=1 so the backend has a fallback if the token is expired
  const url = "/prs/evaluate?user_id=1";

  return apiRequest<PRSEvaluationResponse>(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Only attach the header if token is actually valid
      ...(token && token !== "null" ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });
}

/**
 * Fetch all past PRS evaluations for the authenticated user.
 */
export async function fetchPrsHistory(): Promise<PRSEvaluationHistoryItem[]> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;

  // Always append user_id=1
  const url = "/prs/history?user_id=1";

  return apiRequest<PRSEvaluationHistoryItem[]>(url, {
    headers: token && token !== "null" ? { Authorization: `Bearer ${token}` } : {},
  });
}

/**
 * Fetch the most recent evaluation for a specific role.
 */
export async function fetchPrsLatest(
  role: string
): Promise<PRSEvaluationResponse> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;

  const params = new URLSearchParams({ role });
  return apiRequest<PRSEvaluationResponse>(`/prs/latest?${params}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

/**
 * Fetch a specific evaluation by its database id.
 */
export async function fetchPrsEvaluation(
  evaluationId: number
): Promise<PRSEvaluationResponse> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;

  return apiRequest<PRSEvaluationResponse>(`/prs/evaluations/${evaluationId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

/**
 * Debug helper — preview the normalized PRSInput without running engines.
 */
export async function previewPrsInput(
  targetRole: string,
  assessmentAnswers?: Record<string, AssessmentAnswer>
): Promise<PRSInputDebugResponse> {
  const token = typeof window !== "undefined"
    ? localStorage.getItem("access_token")
    : null;

  const params = new URLSearchParams({
    target_role: targetRole,
    ...(assessmentAnswers
      ? { assessment_answers: JSON.stringify(assessmentAnswers) }
      : {}),
  });

  return apiRequest<PRSInputDebugResponse>(`/prs/input-preview?${params}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

// ---------------------------------------------------------------------------
// Legacy compatibility alias — the prototype page called this function.
// Points to the new Phase 5 endpoint for a smooth transition.
// ---------------------------------------------------------------------------
export async function evaluatePlacementReadiness(
  params: { user_id: number; target_role: string; assessment_answers: Record<string, AssessmentAnswer> }
): Promise<{ data: PRSEvaluationResponse }> {
  const result = await evaluatePrs({
    target_role: params.target_role,
    assessment_answers: params.assessment_answers,
  });
  return { data: result };
}