"use client";

/**
 * app/career-path/weekly-plan/page.tsx
 * ======================================
 * Dedicated full-page Weekly Study Plan view for a Career Path.
 *
 * What this file does:
 *   Renders a detailed week-by-week study plan for a saved career path.
 *   Fetches path data from GET /career/path/{id} using the id passed as
 *   a URL search param (?id=N).
 *
 * Overall design:
 *   Standalone page, dark theme matching the career-path page.
 *   Each week is a card showing:
 *     - Week number + goal bucket badge
 *     - Total effort hours (milestone effort) vs study capacity
 *     - Actual weeks this spans at current pace (effort / study_hours_per_week)
 *     - Each milestone: icon, title, delta, type badge, primary skills
 *   Summary header shows total milestones, total hours, total ETA weeks,
 *   study hours/week.
 *
 * Elements:
 *   WeekCard       One week's card with milestone rows inside
 *   WeeklyPlanPage Main page component (default export)
 *
 * Final output:
 *   A clean, scrollable weekly plan view. Linked from /career-path results.
 */

import { useEffect, useState } from "react";
import {
  ArrowLeft, Clock, Brain, Code2, Award, Zap,
  CheckCircle2, Circle, CalendarDays, Target,
  Loader2, AlertCircle, BookOpen, TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { fetchCareerPath, CareerPathResponse, Milestone } from "@/services/career.service";

// ============================================================
// Helpers
// ============================================================

const BUCKET_STYLE: Record<string, string> = {
  "Immediate":   "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  "Short-Term":  "bg-brand-secondary0/20 text-brand-ai border-brand-primary",
  "Medium-Term": "bg-amber-500/20 text-amber-300 border-amber-500/30",
  "Long-Term":   "bg-rose-500/20 text-rose-300 border-rose-500/30",
};

const BUCKET_ACCENT: Record<string, string> = {
  "Immediate":   "border-l-emerald-500",
  "Short-Term":  "border-l-blue-500",
  "Medium-Term": "border-l-amber-500",
  "Long-Term":   "border-l-rose-500",
};

function milestoneIcon(type: string) {
  switch (type) {
    case "skill":         return Brain;
    case "project":       return Code2;
    case "certification": return Award;
    default:              return Zap;
  }
}

function typeColor(type: string) {
  switch (type) {
    case "skill":         return "bg-brand-secondary0/20 text-brand-ai border-brand-primary";
    case "project":       return "bg-amber-500/20 text-amber-300 border-amber-500/30";
    case "certification": return "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    default:              return "bg-brand-bg0/20 text-brand-text border-slate-600";
  }
}

// ============================================================
// Week Card
// ============================================================

function WeekCard({
  week, milestones, completedIds, studyHoursPerWeek, weekIndex,
}: {
  week: { week_number: number; goal_bucket: string; milestones: string[]; hours_this_week: number };
  milestones: Milestone[];
  completedIds: Set<string>;
  studyHoursPerWeek: number;
  weekIndex: number;
}) {
  const bucket = week.goal_bucket;
  const accentClass = BUCKET_ACCENT[bucket] ?? "border-l-slate-500";
  const totalEffortHours = week.hours_this_week;
  const spansWeeks = Math.ceil(totalEffortHours / studyHoursPerWeek);
  const allDone = milestones.every(m => completedIds.has(m.id));
  const doneCnt = milestones.filter(m => completedIds.has(m.id)).length;

  return (
    <div
      className={`rounded-xl bg-[#1e1844] border border-white/10 border-l-4 ${accentClass}
        overflow-hidden transition-all duration-200 hover:border-white/20`}
    >
      {/* Week header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold
            ${allDone ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-white/60"}`}>
            {allDone ? <CheckCircle2 className="w-4 h-4" /> : week.week_number}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white">
                {spansWeeks > 1
                  ? `Weeks ${week.week_number}–${week.week_number + spansWeeks - 1}`
                  : `Week ${week.week_number}`}
              </span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${BUCKET_STYLE[bucket] ?? "bg-brand-text text-brand-text border-slate-600"}`}>
                {bucket}
              </span>
            </div>
            <p className="text-[11px] text-brand-text mt-0.5">
              {doneCnt}/{milestones.length} completed
            </p>
          </div>

        </div>

        {/* Hours info */}
        <div className="text-right">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-white justify-end">
            <Clock className="w-3.5 h-3.5 text-brand-ai" />
            {totalEffortHours}h effort
          </div>
          <p className="text-[11px] text-brand-text mt-0.5">
            ≈ {spansWeeks} {spansWeeks === 1 ? "week" : "weeks"} @ {studyHoursPerWeek}h/wk
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-[#1a1535]">
        <div
          className="h-full bg-gradient-to-r from-brand-primary to-emerald-400 transition-all duration-500"
          style={{ width: `${milestones.length > 0 ? (doneCnt / milestones.length) * 100 : 0}%` }}
        />
      </div>

      {/* Milestones */}
      <div className="divide-y divide-slate-800/60">
        {milestones.map((ms) => {
          const Icon = milestoneIcon(ms.type);
          const done = completedIds.has(ms.id);
          return (
            <div key={ms.id} className={`flex items-start gap-3 px-5 py-4 ${done ? "opacity-60" : ""}`}>
              {/* Status */}
              <div className="mt-0.5 shrink-0">
                {done
                  ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  : <Circle className="w-4 h-4 text-brand-text" />
                }
              </div>

              {/* Type icon */}
              <div className="shrink-0 w-8 h-8 rounded-lg bg-white/5 border border-white/20
                flex items-center justify-center">
                <Icon className="w-3.5 h-3.5 text-brand-ai" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <p className={`text-sm font-medium leading-snug ${done ? "line-through text-brand-text" : "text-white"}`}>
                    {ms.title}
                  </p>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${typeColor(ms.type)}`}>
                      {ms.type}
                    </span>
                    <span className="text-[11px] font-bold text-brand-ai">
                      +{ms.projected_delta.toFixed(1)} pts
                    </span>
                  </div>
                </div>
                <p className="text-xs text-brand-text mt-0.5 leading-relaxed">{ms.description}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <span className="flex items-center gap-1 text-[11px] text-brand-text">
                    <Clock className="w-3 h-3" />
                    {ms.effort_hours}h
                  </span>
                  {ms.primary_skills.slice(0, 4).map(s => (
                    <span key={s} className="px-1.5 py-0.5 rounded text-[10px]
                      bg-white/10 text-white/70 border border-white/20">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// Main Page
// ============================================================

export default function WeeklyPlanPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathId = searchParams.get("id");

  const [careerPath, setCareerPath] = useState<CareerPathResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!pathId) { setError("No career path ID provided."); setLoading(false); return; }
    fetchCareerPath(Number(pathId))
      .then(data => {
        setCareerPath(data);
        setCompletedIds(new Set(data.completed_milestone_ids ?? []));
      })
      .catch(e => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, [pathId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a1535] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-ai animate-spin" />
      </div>
    );
  }

  if (error || !careerPath) {
    return (
      <div className="min-h-screen bg-[#1a1535] flex flex-col items-center justify-center gap-3">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <p className="text-red-300">{error ?? "Path not found."}</p>
        <Link href="/career-path" className="text-brand-ai hover:underline text-sm">
          ← Back to Career Path
        </Link>
      </div>
    );
  }

  const totalEffortHours = careerPath.eta_hours;
  const studyHours       = careerPath.study_hours_per_week;
  const totalWeeks       = careerPath.eta_weeks;
  const doneCnt          = completedIds.size;
  const totalMs          = careerPath.milestones.length;
  const pct              = totalMs > 0 ? Math.round((doneCnt / totalMs) * 100) : 0;

  // Map milestone ID → Milestone object for quick lookup
  const msMap: Record<string, Milestone> = {};
  for (const ms of careerPath.milestones) msMap[ms.id] = ms;

  return (
    <div className="min-h-screen bg-[#1a1535] text-white">
      {/* Header */}
      <div className="border-b border-white/10 bg-[#1a1535] backdrop-blur sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href={`/career-path`}
              className="text-brand-text hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-base font-bold text-white">Weekly Study Plan</h1>
              <p className="text-xs text-brand-text">{careerPath.target_role} · {careerPath.engine_version}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-brand-text">
            <BookOpen className="w-3.5 h-3.5 text-brand-ai" />
            {studyHours}h/week commitment
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* Summary stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { icon: CalendarDays, label: "Total Weeks",    value: `${totalWeeks}w`,         sub: "calendar ETA",         color: "text-brand-ai" },
            { icon: Clock,        label: "Total Effort",   value: `${totalEffortHours}h`,   sub: `${studyHours}h/wk pace`, color: "text-amber-300"  },
            { icon: Target,       label: "Milestones",     value: `${totalMs}`,             sub: `${doneCnt} done`,        color: "text-emerald-300"},
            { icon: TrendingUp,   label: "PRS Gain",       value: `+${(careerPath.projected_final_prs - careerPath.current_prs_score).toFixed(1)}`, sub: "after all done", color: "text-brand-ai" },
          ].map(({ icon: Icon, label, value, sub, color }) => (
            <div key={label} className="rounded-xl bg-[#1e1844] border border-white/10 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Icon className={`w-4 h-4 ${color}`} />
                <span className="text-[11px] text-brand-text uppercase tracking-wider">{label}</span>
              </div>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-[11px] text-brand-text mt-0.5">{sub}</p>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div className="rounded-xl bg-[#1e1844] border border-white/10 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-white">Overall Progress</span>
            <span className="text-sm font-bold text-brand-ai">{pct}% complete</span>
          </div>
          <div className="h-3 bg-[#1a1535] rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-brand-primary to-emerald-400 rounded-full transition-all duration-700"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-brand-text mt-2">
            {doneCnt} of {totalMs} milestones completed
          </p>
        </div>

        {/* ── How to read note ── */}
        <div className="rounded-xl bg-[#1e1844] border border-brand-ai/40 px-5 py-4">
          <p className="text-xs text-brand-ai font-semibold mb-1">How to read the hours</p>
          <p className="text-xs text-brand-text leading-relaxed">
            <strong className="text-white">Effort hours</strong> is the total study time a milestone requires
            (e.g. "Learn FastAPI = 35h"). At <strong className="text-white">{studyHours}h/week</strong>,
            a 35h milestone spans ≈ {Math.ceil(35 / studyHours)} calendar weeks.
            The ETA ({totalWeeks} weeks) is the sum of all effort hours ÷ your weekly commitment.
          </p>
        </div>

        {/* ── Week cards ── */}
        <div className="space-y-4">
          {careerPath.weekly_plan.map((week) => {
            const weekMilestones = week.milestones
              .map(id => msMap[id])
              .filter(Boolean) as Milestone[];
            return (
              <WeekCard
                key={week.week_number}
                week={week}
                milestones={weekMilestones}
                completedIds={completedIds}
                studyHoursPerWeek={studyHours}
                weekIndex={week.week_number}
              />
            );
          })}
        </div>

        {careerPath.weekly_plan.length === 0 && (
          <div className="text-center py-16 text-brand-text">
            <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No weekly plan available for this path.</p>
          </div>
        )}
      </div>
    </div>
  );
}
