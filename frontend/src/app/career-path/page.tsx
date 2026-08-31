"use client";

/**
 * app/career-path/page.tsx
 * ==========================
 * Module 3 — Career Path Simulator UI.
 *
 * What this file does:
 *   Full career path simulation page. Lets the student:
 *   1. Pick a target role and set study hours → POST /career/simulate
 *   2. View their roadmap: gap analysis, milestone roadmap, weekly plan, progression chain
 *   3. Check off milestones as completed (PATCH /career/path/{id}/milestones/{mid}/complete)
 *   4. Run what-if queries via a toggle panel (POST /career/what-if)
 *   5. Switch between saved career paths (GET /career/paths)
 *
 * Overall design:
 *   Four views managed by a `view` state:
 *     "SETUP"    → role picker + study hours input
 *     "LOADING"  → animated spinner while backend runs pipeline
 *     "RESULTS"  → full roadmap UI (default after simulate)
 *     "HISTORY"  → list of previously saved paths
 *
 *   Dark glassmorphism aesthetic matching the placement-readiness page.
 *   Pure SVG gap ring chart (no chart library dependency).
 *   Milestone cards with live completion toggle.
 *   What-If panel: debounced live re-fetch on skill chip toggle.
 *
 * Elements:
 *   GapRingChart      SVG ring chart for per-pillar gap visualisation
 *   MilestoneCard     Single milestone row with completion toggle
 *   WhatIfPanel       Collapsible skill toggle + live delta preview
 *   CareerPathPage    Main page component (default export)
 *
 * Final output:
 *   A production-quality Career Path Simulator page integrated into
 *   the existing Next.js routing at /career-path.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Target, Clock, TrendingUp, CheckCircle2, Circle,
  Brain, Code2, Award, Zap, ChevronRight, ArrowLeft,
  Loader2, AlertCircle, RefreshCw, BarChart3, Map,
  Sparkles, ChevronDown, ChevronUp, Star, BookOpen,
  GitBranch, Users, Layers,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";
import {
  simulateCareerPath, fetchCareerPaths, fetchCareerPath,
  toggleMilestoneComplete, runWhatIf,
  CareerPathResponse, CareerPathSummary, Milestone, WhatIfResponse,
} from "@/services/career.service";
import { fetchPrsRoles } from "@/services/prs.service";

// ============================================================
// Types & constants
// ============================================================

type View = "SETUP" | "LOADING" | "RESULTS" | "HISTORY";

const PILLAR_LABELS: Record<string, string> = {
  skill_readiness:     "Skill Readiness",
  projects_experience: "Projects & Experience",
  role_alignment:      "Role Alignment",
  resume_quality:      "Resume Quality",
  certificate_quality: "Certificate Quality",
};

const PILLAR_COLORS: Record<string, string> = {
  skill_readiness:     "#6366f1",
  projects_experience: "#f59e0b",
  role_alignment:      "#10b981",
  resume_quality:      "#3b82f6",
  certificate_quality: "#8b5cf6",
};

// ============================================================
// Helper functions
// ============================================================


function milestoneIcon(type: string) {
  switch (type) {
    case "skill":         return Brain;
    case "project":       return Code2;
    case "certification": return Award;
    default:              return Zap;
  }
}

function priorityColor(label: string) {
  switch (label) {
    case "High":   return "bg-red-500/20 text-red-300 border-red-500/30";
    case "Medium": return "bg-amber-500/20 text-amber-300 border-amber-500/30";
    default:       return "bg-white/10 text-white/70 border-white/20";
  }
}

function readinessGradient(level: string) {
  switch (level) {
    case "Highly Placement Ready": return "from-emerald-500 to-teal-400";
    case "Industry Ready":         return "from-brand-primary to-brand-ai-light";
    case "Developing Readiness":   return "from-amber-500 to-orange-400";
    case "Needs Improvement":      return "from-orange-500 to-red-400";
    default:                       return "from-brand-primary to-brand-ai-light";
  }
}

function deltaLabel(delta: number) {
  if (delta > 0) return `+${delta.toFixed(1)} pts`;
  if (delta < 0) return `${delta.toFixed(1)} pts`;
  return "No change";
}

// ============================================================
// Gap Ring Chart (pure SVG)
// ============================================================

function GapRingChart({
  pillar, score, color, size = 80,
}: {
  pillar: string; score: number;
  color: string; size?: number;
}) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  // Ring filled = actual score / 100 (not the gap)
  const filled = Math.min(1, Math.max(0, score / 100));
  const dash = filled * circ;
  const cx = size / 2;

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background track */}
        <circle cx={cx} cy={cx} r={r} fill="none" stroke="#1e293b" strokeWidth={8} />
        {/* Filled arc = actual score */}
        <circle
          cx={cx} cy={cx} r={r} fill="none"
          stroke={color} strokeWidth={8}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cx})`}
          style={{ transition: "stroke-dasharray 0.8s ease" }}
        />
        <text x={cx} y={cx - 4} textAnchor="middle" dominantBaseline="middle"
          fill="white" fontSize={size < 70 ? 10 : 12} fontWeight="700">
          {Math.round(score)}
        </text>
        <text x={cx} y={cx + 8} textAnchor="middle" dominantBaseline="middle"
          fill="#64748b" fontSize={size < 70 ? 7 : 8}>
          /100
        </text>
      </svg>
      <span className="text-[10px] text-brand-text text-center leading-tight max-w-[70px]">
        {PILLAR_LABELS[pillar] ?? pillar}
      </span>
    </div>
  );
}

// ============================================================
// Milestone Card
// ============================================================

function MilestoneCard({
  milestone, isCompleted, onToggle, careerPathId,
}: {
  milestone: Milestone;
  isCompleted: boolean;
  onToggle: (id: string, done: boolean) => void;
  careerPathId: number;
}) {
  const [toggling, setToggling] = useState(false);
  const Icon = milestoneIcon(milestone.type);

  async function handleToggle() {
    setToggling(true);
    try {
      await onToggle(milestone.id, !isCompleted);
    } finally {
      setToggling(false);
    }
  }

  return (
    <div
      className={`group relative flex items-start gap-4 p-4 rounded-xl border transition-all duration-200
        ${isCompleted
          ? "bg-brand-sidebar border-slate-700/40 opacity-70"
          : "bg-brand-sidebar border-slate-700/60 hover:border-brand-primary hover:bg-brand-sidebar"
        }`}
    >
      {/* Completion toggle */}
      <button
        onClick={handleToggle}
        disabled={toggling}
        className="mt-0.5 shrink-0 transition-transform hover:scale-110"
        aria-label={isCompleted ? "Mark incomplete" : "Mark complete"}
      >
        {toggling
          ? <Loader2 className="w-5 h-5 text-brand-ai animate-spin" />
          : isCompleted
            ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            : <Circle className="w-5 h-5 text-brand-text group-hover:text-brand-ai" />
        }
      </button>

      {/* Icon */}
      <div className="shrink-0 w-9 h-9 rounded-lg bg-brand-primary/10 border border-brand-primary
        flex items-center justify-center">
        <Icon className="w-4 h-4 text-brand-ai" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <h4 className={`text-sm font-semibold leading-snug
            ${isCompleted ? "line-through text-brand-text" : "text-white"}`}>
            {milestone.title}
          </h4>
          <div className="flex items-center gap-1.5 shrink-0 flex-wrap">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border
              ${priorityColor(milestone.priority_label)}`}>
              {milestone.priority_label}
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium
              bg-brand-primary/20 text-brand-ai border border-brand-primary">
              +{milestone.projected_delta.toFixed(1)} pts
            </span>
          </div>
        </div>
        <p className="text-xs text-brand-text mt-1 leading-relaxed">{milestone.description}</p>
        <div className="flex items-center gap-3 mt-2 text-[11px] text-brand-text">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {milestone.effort_hours}h
          </span>
          {milestone.primary_skills.slice(0, 3).map(s => (
            <span key={s} className="px-1.5 py-0.5 rounded bg-white/10 text-white/80 text-[10px] border border-white/15">
              {s}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// What-If Panel
// ============================================================

function WhatIfPanel({
  targetRole, suggestedSkills,
}: {
  targetRole: string;
  suggestedSkills: string[];
}) {
  const [open, setOpen] = useState(false);
  const [toggled, setToggled] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<WhatIfResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function toggleSkill(skill: string) {
    setToggled(prev => {
      const next = new Set(prev);
      next.has(skill) ? next.delete(skill) : next.add(skill);
      return next;
    });
  }

  // Debounced what-if re-fetch
  useEffect(() => {
    if (!open || toggled.size === 0) { setResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true); setError(null);
      try {
        const res = await runWhatIf({
          target_role: targetRole,
          hypothetical_skills: Array.from(toggled),
        });
        setResult(res);
      } catch (e: any) {
        setError(e.message ?? "What-if failed");
      } finally {
        setLoading(false);
      }
    }, 600);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [toggled, open, targetRole]);

  return (
    <div className="rounded-xl border border-brand-primary bg-brand-sidebar overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4
          hover:bg-brand-secondary0/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-secondary0/20 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-brand-ai" />
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-white">What-If Simulator</p>
            <p className="text-xs text-brand-text">See how new skills would affect your score</p>
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-brand-text" /> : <ChevronDown className="w-4 h-4 text-brand-text" />}
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-brand-primary">
          <p className="text-xs text-brand-text mt-4 mb-3">
            Toggle skills hypothetically — score updates in real time
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {suggestedSkills.map(skill => (
              <button
                key={skill}
                onClick={() => toggleSkill(skill)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-150
                  ${toggled.has(skill)
                    ? "bg-brand-secondary0 text-white border-brand-border shadow-lg shadow-none"
                    : "bg-brand-sidebar text-brand-text border-slate-600 hover:border-brand-border"
                  }`}
              >
                {toggled.has(skill) ? "✓ " : ""}{skill}
              </button>
            ))}
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-sm text-brand-ai">
              <Loader2 className="w-4 h-4 animate-spin" />
              Simulating…
            </div>
          )}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
          {result && !loading && (
            <div className="rounded-lg bg-brand-sidebar border border-brand-primary p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-brand-text">Current PRS</span>
                <span className="text-sm font-bold text-white">{result.original_prs_score.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-brand-text">Projected PRS</span>
                <span className="text-sm font-bold text-brand-ai">{result.simulated_prs_score.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between border-t border-slate-700 pt-2">
                <span className="text-xs text-brand-text">Net Change</span>
                <span className={`text-sm font-bold ${result.overall_delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {deltaLabel(result.overall_delta)}
                </span>
              </div>
              <p className="text-xs text-brand-text mt-1">{result.summary}</p>
            </div>
          )}
          {toggled.size === 0 && !loading && (
            <p className="text-xs text-brand-text italic">Select skills above to see projected impact</p>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// Main Page
// ============================================================

export default function CareerPathPage() {
  const [view, setView] = useState<View>("SETUP");
  const [roles, setRoles] = useState<string[]>([]);
  const [roleQuery, setRoleQuery] = useState("");
  const [selectedRole, setSelectedRole] = useState("");
  const [studyHours, setStudyHours] = useState(10);
  const [error, setError] = useState<string | null>(null);

  const [careerPath, setCareerPath] = useState<CareerPathResponse | null>(null);
  const [history, setHistory] = useState<CareerPathSummary[]>([]);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

  // Load roles on mount
  useEffect(() => {
    fetchPrsRoles()
      .then(r => setRoles(r.roles?.map((ro: any) => ro.name) ?? []))
      .catch(() => {});
  }, []);

  const filteredRoles = roles.filter(r =>
    r.toLowerCase().includes(roleQuery.toLowerCase())
  );

  // Run simulation
  async function handleSimulate() {
    if (!selectedRole) return;
    setError(null);
    setView("LOADING");
    try {
      const result = await simulateCareerPath(selectedRole, studyHours);
      setCareerPath(result);
      setCompletedIds(new Set(result.completed_milestone_ids ?? []));
      setView("RESULTS");
    } catch (e: any) {
      const msg = e.message ?? "Simulation failed";
      if (msg.includes("No PRS evaluation")) {
        setError("Run a PRS evaluation for this role first (Placement Readiness page), then come back.");
      } else {
        setError(msg);
      }
      setView("SETUP");
    }
  }

  // Load history
  async function handleViewHistory() {
    try {
      const paths = await fetchCareerPaths();
      setHistory(paths);
      setView("HISTORY");
    } catch (e: any) {
      setError(e.message);
    }
  }

  // Load saved path
  async function handleLoadPath(id: number) {
    setView("LOADING");
    try {
      const result = await fetchCareerPath(id);
      setCareerPath(result);
      setCompletedIds(new Set(result.completed_milestone_ids ?? []));
      setView("RESULTS");
    } catch (e: any) {
      setError(e.message);
      setView("HISTORY");
    }
  }

  // Toggle milestone
  const handleToggleMilestone = useCallback(async (milestoneId: string, done: boolean) => {
    if (!careerPath) return;
    await toggleMilestoneComplete(careerPath.career_path_id, milestoneId, done);
    setCompletedIds(prev => {
      const next = new Set(prev);
      done ? next.add(milestoneId) : next.delete(milestoneId);
      return next;
    });
  }, [careerPath]);

  // Suggested skills for what-if (missing skills from first milestone's primary_skills)
  const suggestedSkills = careerPath
    ? careerPath.milestones
        .filter(m => m.type === "skill")
        .flatMap(m => m.primary_skills)
        .slice(0, 10)
    : [];

  // Progress
  const totalMs = careerPath?.milestones.length ?? 0;
  const doneMs  = completedIds.size;
  const pct     = totalMs > 0 ? Math.round((doneMs / totalMs) * 100) : 0;

  // ============================================================
  // SETUP VIEW
  // ============================================================
  if (view === "SETUP") {
    return (
      <div className="min-h-screen bg-brand-sidebar text-white">
        {/* Header */}
        <div className="border-b border-white/10 bg-[#1a1535] backdrop-blur sticky top-0 z-10">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/" className="text-white/50 hover:text-white transition-colors">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-lg font-bold bg-gradient-to-r from-brand-ai-light to-white bg-clip-text text-transparent">
                  Career Path Simulator
                </h1>
                <p className="text-xs text-white/50">Module 3 — AI-powered roadmap</p>
              </div>
            </div>
            <button
              onClick={handleViewHistory}
              className="flex items-center gap-2 text-xs text-white/60 hover:text-white
                px-3 py-1.5 rounded-lg border border-white/20 hover:border-white/40 transition-all"
            >
              <BarChart3 className="w-3.5 h-3.5" />
              My Paths
            </button>
          </div>
        </div>

        <div className="max-w-2xl mx-auto px-6 py-16 space-y-8">
          {/* Hero */}
          <div className="text-center space-y-3">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full
              bg-brand-primary/10 border border-brand-primary text-brand-ai text-sm font-medium">
              <Sparkles className="w-4 h-4" />
              AI Career Roadmap
            </div>
            <h2 className="text-3xl font-bold text-white">
              Where do you want to go?
            </h2>
            <p className="text-brand-text max-w-md mx-auto">
              Pick a target role and we'll generate a personalised milestone
              roadmap — ranked by ROI, not guesswork.
            </p>
          </div>

          {/* Role search */}
          <Card className="bg-[#1a1535] border-white/10">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-white/60 font-medium">Target Role</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                value={roleQuery}
                onChange={e => setRoleQuery(e.target.value)}
                placeholder="Search roles…"
                className="bg-white/5 border-white/20 text-white placeholder:text-white/40
                  focus:border-brand-ai focus:ring-brand-ai/20"
              />
              <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
                {filteredRoles.length === 0 && (
                  <p className="text-xs text-brand-text text-center py-4">No roles found</p>
                )}
                {filteredRoles.map(role => (
                  <button
                    key={role}
                    onClick={() => { setSelectedRole(role); setRoleQuery(role); }}
                    className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all
                      ${selectedRole === role
                        ? "bg-brand-primary/40 border border-brand-ai text-white"
                        : "text-white/60 hover:bg-white/5 hover:text-white border border-transparent"
                      }`}
                  >
                    <span className="flex items-center justify-between">
                      {role}
                      {selectedRole === role && <CheckCircle2 className="w-4 h-4 text-brand-ai" />}
                    </span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Study hours */}
          <Card className="bg-[#1a1535] border-white/10">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-white/60 font-medium flex items-center gap-2">
                <Clock className="w-4 h-4 text-brand-ai" />
                Study Hours per Week
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <input
                  type="range" min={1} max={40} value={studyHours}
                  onChange={e => setStudyHours(Number(e.target.value))}
                  className="flex-1 accent-brand-ai"
                />
                <span className="text-white font-bold text-lg w-14 text-center
                  bg-brand-ai/20 rounded-lg py-1 border border-brand-ai">
                  {studyHours}h
                </span>
              </div>
              <p className="text-xs text-brand-text mt-2">
                Used to calculate your week-by-week study plan
              </p>
            </CardContent>
          </Card>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-900/20 border border-red-500/30">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {/* CTA */}
          <Button
            onClick={handleSimulate}
            disabled={!selectedRole}
            className="w-full h-12 text-base font-semibold bg-brand-ai hover:bg-brand-ai-hover text-white
              border-0 shadow-lg shadow-none
              disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            <Target className="w-4 h-4 mr-2" />
            Generate My Roadmap
          </Button>

          <p className="text-center text-xs text-brand-text">
            Requires a completed PRS evaluation for the selected role.{" "}
            <Link href="/placement-readiness" className="text-brand-ai hover:underline">
              Run evaluation →
            </Link>
          </p>
        </div>
      </div>
    );
  }

  // ============================================================
  // LOADING VIEW
  // ============================================================
  if (view === "LOADING") {
    return (
      <div className="min-h-screen bg-[#1a1535] flex flex-col items-center justify-center gap-6">
        <div className="relative">
          <div className="w-20 h-20 rounded-full border-2 border-brand-ai animate-ping absolute inset-0" />
          <div className="w-20 h-20 rounded-full bg-brand-ai/10 border border-brand-ai
            flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-brand-ai animate-spin" />
          </div>
        </div>
        <div className="text-center space-y-1">
          <p className="text-white font-semibold">Building your roadmap…</p>
          <p className="text-brand-text text-sm">Analysing gaps, scoring milestones by ROI</p>
        </div>
      </div>
    );
  }

  // ============================================================
  // HISTORY VIEW
  // ============================================================
  if (view === "HISTORY") {
    return (
      <div className="min-h-screen bg-[#1a1535] text-white">
        <div className="border-b border-white/10 bg-[#1a1535] backdrop-blur sticky top-0 z-10">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
            <button onClick={() => setView("SETUP")} className="text-white/50 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-bold text-white">My Career Paths</h1>
          </div>
        </div>

        <div className="max-w-3xl mx-auto px-6 py-8 space-y-4">
          {history.length === 0 && (
            <div className="text-center py-16 text-brand-text">
              <Map className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No saved career paths yet.</p>
              <button onClick={() => setView("SETUP")}
                className="mt-4 text-brand-ai hover:underline text-sm">
                Create one →
              </button>
            </div>
          )}
          {history.map(p => {
            const progress = p.milestone_count > 0
              ? Math.round((p.completed_count / p.milestone_count) * 100) : 0;
            return (
              <button
                key={p.career_path_id}
                onClick={() => handleLoadPath(p.career_path_id)}
                className="w-full text-left p-5 rounded-xl bg-[#1e1844] border border-white/10
                  hover:border-brand-ai hover:bg-[#221c4e] transition-all group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-white group-hover:text-brand-ai transition-colors">
                      {p.target_role}
                    </h3>
                    <p className="text-xs text-brand-text mt-0.5">
                      {new Date(p.created_at).toLocaleDateString("en-IN", {
                        day: "numeric", month: "short", year: "numeric"
                      })}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-brand-text group-hover:text-brand-ai mt-1 transition-colors" />
                </div>
                <div className="flex items-center gap-6 mt-3 text-xs text-brand-text">
                  <span className="flex items-center gap-1.5">
                    <BarChart3 className="w-3 h-3" />
                    PRS: {p.current_prs_score?.toFixed(1)} → {p.projected_final_prs?.toFixed(1)}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-3 h-3" />
                    {p.eta_weeks}w
                  </span>
                  <span className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    {p.completed_count}/{p.milestone_count}
                  </span>
                </div>
                {/* Progress bar */}
                <div className="mt-3 h-1.5 bg-[#1a1535] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-ai rounded-full transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  // ============================================================
  // RESULTS VIEW
  // ============================================================
  if (!careerPath) return null;
  const gap = careerPath.gap_analysis;
  const prog = careerPath.role_progression;

  return (
    <div className="min-h-screen bg-[#1a1535] text-white">
      {/* Header */}
      <div className="border-b border-white/10 bg-[#1a1535] backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button onClick={() => setView("SETUP")} className="text-white/50 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-base font-bold text-white">{careerPath.target_role}</h1>
              <p className="text-xs text-white/50">Career Path · {careerPath.engine_version}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleViewHistory}
              className="text-xs text-white/60 hover:text-white px-3 py-1.5
                rounded-lg border border-white/20 hover:border-white/40 transition-all"
            >
              My Paths
            </button>
            <button
              onClick={() => { setView("SETUP"); setSelectedRole(careerPath.target_role); setRoleQuery(careerPath.target_role); }}
              className="flex items-center gap-1.5 text-xs text-brand-ai hover:text-white
                px-3 py-1.5 rounded-lg border border-brand-ai/40 hover:border-brand-ai transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Re-simulate
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* ── Hero stats bar ── */}
        <div className={`rounded-2xl bg-gradient-to-r ${readinessGradient(careerPath.current_readiness)}
          p-px`}>
          <div className="rounded-2xl bg-brand-sidebar backdrop-blur p-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
              <div>
                <p className="text-xs text-brand-text mb-1">Current PRS</p>
                <p className="text-3xl font-black text-white">{careerPath.current_prs_score.toFixed(1)}</p>
                <p className="text-xs text-brand-text mt-0.5">{careerPath.current_readiness}</p>
              </div>
              <div>
                <p className="text-xs text-brand-text mb-1">Projected PRS</p>
                <p className="text-3xl font-black text-emerald-400">{careerPath.projected_final_prs.toFixed(1)}</p>
                <p className="text-xs text-brand-text mt-0.5">after all milestones</p>
              </div>
              <div>
                <p className="text-xs text-brand-text mb-1">ETA</p>
                <p className="text-3xl font-black text-brand-ai">{careerPath.eta_weeks}w</p>
                <p className="text-xs text-brand-text mt-0.5">{careerPath.study_hours_per_week}h/week · {careerPath.eta_hours}h total</p>
              </div>
              <div>
                <p className="text-xs text-brand-text mb-2">Progress</p>
                <p className="text-3xl font-black text-white">{pct}%</p>
                <p className="text-xs text-brand-text mt-0.5">{doneMs}/{totalMs} done</p>
              </div>
            </div>
            {/* Progress bar */}
            <div className="mt-5 h-2 bg-brand-sidebar rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-primary to-emerald-400 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* ── LEFT COLUMN: Gap analysis + What-If ── */}
          <div className="space-y-6">
            {/* Gap analysis */}
            <Card className="bg-[#1e1844] border-white/10">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm text-brand-text font-semibold flex items-center gap-2">
                  <Target className="w-4 h-4 text-red-400" />
                  Current Pillar Scores
                </CardTitle>
                <p className="text-xs text-brand-text mt-0.5">
                  Target: {gap.target_prs} pts per pillar · Total gap: {gap.total_gap.toFixed(1)} pts
                </p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  {gap.ordered_pillars.slice(0, 5).map(pillar => (
                    <GapRingChart
                      key={pillar}
                      pillar={pillar}
                      score={gap.pillar_scores?.[pillar] ?? (gap.target_prs - (gap.gaps[pillar] ?? 0))}
                      color={PILLAR_COLORS[pillar] ?? "#6366f1"}
                      size={72}
                    />
                  ))}
                </div>
                <p className="text-[10px] text-brand-text text-center mt-3">
                  Ring fill = actual score/100 · Ordered by gap priority
                </p>
              </CardContent>
            </Card>

            {/* What-If panel */}
            {suggestedSkills.length > 0 && (
              <WhatIfPanel targetRole={careerPath.target_role} suggestedSkills={suggestedSkills} />
            )}

            {/* Role progression chain */}
            {prog.role_found && (
              <Card className="bg-[#1e1844] border-white/10">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm text-brand-text font-semibold flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-emerald-400" />
                    Career Chain
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  {prog.entry_path.length > 0 && (
                    <div>
                      <p className="text-brand-text mb-1.5">Entry paths</p>
                      <div className="flex flex-wrap gap-1.5">
                        {prog.entry_path.map(r => (
                          <span key={r} className="px-2 py-0.5 rounded-full
                            bg-white/10 text-white/70 border border-white/20 text-[10px]">
                            {r}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="flex items-center justify-center py-1">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full
                      bg-brand-primary/20 border border-brand-primary text-brand-ai font-semibold">
                      <Star className="w-3 h-3" />
                      {prog.target_role}
                    </div>
                  </div>
                  {prog.next_roles.length > 0 && (
                    <div>
                      <p className="text-brand-text mb-1.5">After {prog.typical_years_to_next}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {prog.next_roles.map(r => (
                          <span key={r} className="px-2 py-0.5 rounded-full
                            bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                            {r}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {prog.senior_path && (
                    <div className="flex items-center gap-2 pt-1 border-t border-slate-800">
                      <TrendingUp className="w-3 h-3 text-amber-400 shrink-0" />
                      <span className="text-amber-300">{prog.senior_path}</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* ── RIGHT COLUMN: Milestones + Weekly plan ── */}
          <div className="lg:col-span-2 space-y-6">
            {/* Milestones */}
            <Card className="bg-[#1e1844] border-white/10">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm text-brand-text font-semibold flex items-center gap-2">
                  <Layers className="w-4 h-4 text-brand-ai" />
                  Milestone Roadmap
                  <span className="ml-auto text-xs text-brand-text font-normal">
                    Sorted by ROI (score gain / effort)
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {careerPath.milestones.length === 0 && (
                  <p className="text-sm text-brand-text text-center py-6">
                    No milestones generated — you may already be on track!
                  </p>
                )}
                {careerPath.milestones.map((ms) => (
                  <MilestoneCard
                    key={ms.id}
                    milestone={ms}
                    isCompleted={completedIds.has(ms.id)}
                    onToggle={handleToggleMilestone}
                    careerPathId={careerPath.career_path_id}
                  />
                ))}
              </CardContent>
            </Card>

            {/* Weekly plan redirect */}
            <Link
              href={`/career-path/weekly-plan?id=${careerPath.career_path_id}`}
              className="block rounded-xl border border-brand-primary/40 bg-[#1e1844]
                hover:bg-[#221c4e] hover:border-brand-primary transition-all group p-5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-brand-secondary0/20 flex items-center justify-center">
                    <BookOpen className="w-4 h-4 text-brand-ai" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white group-hover:text-brand-ai transition-colors">
                      Weekly Study Plan
                    </p>
                    <p className="text-xs text-brand-text">
                      {careerPath.weekly_plan.length} weeks · {careerPath.study_hours_per_week}h/week commitment
                    </p>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-brand-text group-hover:text-brand-ai transition-colors" />
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
