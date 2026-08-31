/**
 * learning.service.ts
 * ===================
 * What this file does:
 *   API abstraction layer for all PathPilot learning endpoints.
 *   Wraps /learning/* backend routes with typed TypeScript functions.
 *
 * Overall design:
 *   Each function calls apiRequest() from lib/api.ts.
 *   All responses are typed with local interfaces.
 *
 * Elements:
 *   fetchLearningGoals()        — GET /learning/goals
 *   sendChatMessage()           — POST /learning/chat
 *   generateLearningPath()      — POST /learning/path/generate
 *   fetchLearningPath()         — GET /learning/path/{id}
 *   fetchAllPaths()             — GET /learning/paths
 *   updateProgress()            — POST /learning/path/{id}/progress
 *   searchCourses()             — GET /learning/courses/search
 *
 * Final output:
 *   Typed API functions consumed by frontend pages.
 */
import { apiRequest } from "@/lib/api";

export interface LearningGoal {
  id: string;
  name: string;
  description: string;
  difficulty: string;
  estimated_weeks: number;
  required_skills: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  session_id: number;
  extracted_profile: Record<string, unknown> | null;
  is_profile_complete: boolean;
}

export interface CourseItem {
  id: string;
  title: string;
  provider: string;
  url: string;
  level: string;
  duration_hours: number;
  skills_taught: string[];
  domain: string;
  description: string;
  is_free: boolean;
  why_recommended: string;
}

export interface LearningPhase {
  phase_number: number;
  phase_name: string;
  description: string;
  courses: CourseItem[];
  estimated_weeks: number;
  skills_gained: string[];
}

export interface LearningPathResponse {
  path_id: number;
  goal_name: string;
  total_courses: number;
  total_weeks: number;
  phases: LearningPhase[];
  skill_gaps: string[];
  already_known: string[];
}

export interface PathSummary {
  id: number;
  goal_name: string;
  total_courses: number;
  total_weeks: number;
  completed_course_ids: string[];
  created_at: string;
}

export async function fetchLearningGoals(): Promise<LearningGoal[]> {
  const res = await apiRequest<{ goals: LearningGoal[] }>("/learning/goals");
  return res.goals || [];
}

export async function sendChatMessage(
  message: string,
  sessionId?: number
): Promise<ChatResponse> {
  const body: Record<string, unknown> = { message };
  if (sessionId) body.session_id = sessionId;
  return apiRequest<ChatResponse>("/learning/chat", { method: "POST", body: JSON.stringify(body) });
}

export async function generateLearningPath(payload: {
  goal_id: string;
  current_skills: string[];
  experience_level: string;
  weekly_study_hours: number;
}): Promise<LearningPathResponse> {
  return apiRequest<LearningPathResponse>("/learning/path/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchLearningPath(pathId: number): Promise<LearningPathResponse> {
  return apiRequest<LearningPathResponse>(`/learning/path/${pathId}`);
}

export async function fetchAllPaths(): Promise<PathSummary[]> {
  const res = await apiRequest<{ paths: PathSummary[] }>("/learning/paths");
  return res.paths || [];
}

export async function updateProgress(
  pathId: number,
  courseId: string,
  completed: boolean
): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>(`/learning/path/${pathId}/progress`, {
    method: "POST",
    body: JSON.stringify({ course_id: courseId, completed }),
  });
}

export async function searchCourses(query: string, level?: string): Promise<CourseItem[]> {
  const params = new URLSearchParams({ query });
  if (level) params.append("level", level);
  const res = await apiRequest<{ courses: CourseItem[] }>(`/learning/courses/search?${params.toString()}`);
  return res.courses || [];
}
