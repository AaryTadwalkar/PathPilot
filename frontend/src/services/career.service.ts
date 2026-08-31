/**
 * career.service.ts
 * ==================
 * Module 3 - Career Path Simulator frontend service layer.
 *
 * What this file does:
 *   Provides typed API functions for all 5 Career endpoints.
 *   Mirrors the exact JSON shapes returned by main.py M3-9 endpoints.
 *
 * Design:
 *   Follows the same pattern as prs.service.ts — uses apiRequest() from lib/api.ts.
 *   All types exported so the page component is fully typed.
 *
 * Endpoints covered:
 *   POST  /career/simulate                         → CareerPathResponse
 *   GET   /career/paths                            → CareerPathSummary[]
 *   GET   /career/path/{id}                        → CareerPathResponse
 *   PATCH /career/path/{id}/milestones/{mid}/complete → MilestoneCompleteResponse
 *   POST  /career/what-if                          → WhatIfResponse
 */

import { apiRequest } from "@/lib/api";

// ============================================================
// Shared sub-types
// ============================================================

export interface GapEntry {
  target_prs: number;
  total_gap: number;
  gaps: Record<string, number>;
  priorities: Record<string, number>;
  ordered_pillars: string[];
  pillar_labels: Record<string, string>;
  pillar_scores: Record<string, number>;   // actual current score per pillar
}

export interface Milestone {
  id: string;
  type: "skill" | "project" | "certification" | "resume";
  title: string;
  description: string;
  projected_delta: number;
  effort_hours: number;
  roi: number;
  primary_skills: string[];
  pillar: string;
  priority_label: "High" | "Medium" | "Low";
}

export interface WeeklyEntry {
  week_number: number;
  goal_bucket: "Immediate" | "Short-Term" | "Medium-Term" | "Long-Term";
  milestones: string[];   // milestone IDs
  hours_this_week: number;
}

export interface RoleProgression {
  target_role: string;
  role_found: boolean;
  entry_path: string[];
  next_roles: string[];
  adjacent_roles: string[];
  senior_path: string;
  typical_experience_years: string;
  typical_years_to_next: string;
}

// ============================================================
// POST /career/simulate response
// ============================================================

export interface CareerPathResponse {
  career_path_id: number;
  target_role: string;
  current_prs_score: number;
  current_readiness: string;
  target_prs_score: number;
  projected_final_prs: number;
  eta_weeks: number;
  eta_hours: number;
  study_hours_per_week: number;
  gap_analysis: GapEntry;
  milestones: Milestone[];
  weekly_plan: WeeklyEntry[];
  role_progression: RoleProgression;
  completed_milestone_ids: string[];
  engine_version: string;
  created_at: string;
  updated_at?: string;
  last_progress_update?: string;
}

// ============================================================
// GET /career/paths response item
// ============================================================

export interface CareerPathSummary {
  career_path_id: number;
  target_role: string;
  current_prs_score: number;
  projected_final_prs: number;
  eta_weeks: number;
  milestone_count: number;
  completed_count: number;
  engine_version: string;
  created_at: string;
}

// ============================================================
// POST /career/what-if
// ============================================================

export interface WhatIfRequest {
  target_role: string;
  hypothetical_skills?: string[];
  hypothetical_project?: {
    name: string;
    description: string;
    skills_used: string[];
    domain?: string;
  } | null;
  hypothetical_certifications?: string[];
}

export interface WhatIfMutationResult {
  mutation_type: string;
  payload: string;
  delta: number;
  skipped: boolean;
  new_prs_score: number;
}

export interface WhatIfResponse {
  target_role: string;
  original_prs_score: number;
  simulated_prs_score: number;
  overall_delta: number;
  mutations_applied: number;
  mutations_skipped: number;
  per_mutation: WhatIfMutationResult[];
  summary: string;
}

// ============================================================
// PATCH milestone complete response
// ============================================================

export interface MilestoneCompleteResponse {
  career_path_id: number;
  milestone_id: string;
  completed: boolean;
  completed_count: number;
  total_milestones: number;
  progress_pct: number;
  last_progress_update: string;
}

// ============================================================
// API functions
// ============================================================

/** POST /career/simulate — run full pipeline and save result */
export async function simulateCareerPath(
  targetRole: string,
  studyHoursPerWeek?: number,
  targetPrsScore?: number,
): Promise<CareerPathResponse> {
  return apiRequest<CareerPathResponse>("/career/simulate?user_id=1", {
    method: "POST",
    body: JSON.stringify({
      target_role: targetRole,
      study_hours_per_week: studyHoursPerWeek ?? null,
      target_prs_score: targetPrsScore ?? null,
    }),
  });
}

/** GET /career/paths — list saved career paths */
export async function fetchCareerPaths(): Promise<CareerPathSummary[]> {
  return apiRequest<CareerPathSummary[]>("/career/paths?user_id=1");
}

/** GET /career/path/{id} — full detail */
export async function fetchCareerPath(id: number): Promise<CareerPathResponse> {
  return apiRequest<CareerPathResponse>(`/career/path/${id}?user_id=1`);
}

/** PATCH milestone complete toggle */
export async function toggleMilestoneComplete(
  careerPathId: number,
  milestoneId: string,
  completed: boolean,
): Promise<MilestoneCompleteResponse> {
  return apiRequest<MilestoneCompleteResponse>(
    `/career/path/${careerPathId}/milestones/${milestoneId}/complete?user_id=1`,
    {
      method: "PATCH",
      body: JSON.stringify({ completed }),
    },
  );
}

/** POST /career/what-if */
export async function runWhatIf(req: WhatIfRequest): Promise<WhatIfResponse> {
  return apiRequest<WhatIfResponse>("/career/what-if?user_id=1", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
