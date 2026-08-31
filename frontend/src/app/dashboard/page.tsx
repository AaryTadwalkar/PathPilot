"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  BarChart2,
  BookOpen,
  Map,
  Award,
  TrendingUp,
  Loader2,
  Plus
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchAllPaths, PathSummary } from "@/services/learning.service";

export default function DashboardPage() {
  const router = useRouter();
  const [paths, setPaths] = useState<PathSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (!storedUser) {
      router.push("/auth");
      return;
    }
    
    loadDashboard();
  }, [router]);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const data = await fetchAllPaths();
      setPaths(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-primary" />
      </div>
    );
  }

  const activePath = paths.length > 0 ? paths[0] : null;
  const totalPaths = paths.length;
  const totalCoursesCompleted = paths.reduce((sum, path) => sum + (path.completed_course_ids?.length || 0), 0);

  // SVG Radar Chart Math
  const skills = [
    { name: 'Python', target: 80, current: 40 },
    { name: 'ML', target: 90, current: 20 },
    { name: 'Web Dev', target: 60, current: 50 },
    { name: 'Data', target: 70, current: 30 },
    { name: 'Cloud', target: 50, current: 10 },
    { name: 'Mobile', target: 40, current: 10 }
  ];

  const size = 200;
  const center = size / 2;
  const radius = (size / 2) - 20;

  const getCoordinatesForAngle = (angle: number, value: number) => {
    const r = (value / 100) * radius;
    const x = center + r * Math.cos(angle - Math.PI / 2);
    const y = center + r * Math.sin(angle - Math.PI / 2);
    return { x, y };
  };

  const getPathData = (type: 'target' | 'current') => {
    return skills.map((skill, index) => {
      const angle = (Math.PI * 2 * index) / skills.length;
      const { x, y } = getCoordinatesForAngle(angle, skill[type]);
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ') + ' Z';
  };

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col">
      <header className="bg-brand-bg border-b border-brand-border h-16 flex items-center px-6 sticky top-0 z-10 justify-between">
        <div className="flex items-center">
          <Button variant="ghost" size="icon" onClick={() => router.push("/")} className="mr-4 text-brand-text hover:text-white">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <BarChart2 className="h-6 w-6 text-brand-primary mr-2" />
          <h1 className="text-xl font-bold text-white">My Learning Dashboard</h1>
        </div>
        <Button onClick={() => router.push("/chat")} size="sm" className="bg-brand-primary text-white">
          <Plus className="h-4 w-4 mr-2" /> Start New Path
        </Button>
      </header>

      <main className="flex-grow max-w-6xl w-full mx-auto p-6 space-y-8">
        
        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-brand-secondary flex items-center justify-center">
                <Map className="h-6 w-6 text-brand-primary" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Paths Created</p>
                <p className="text-3xl font-bold text-white">{totalPaths}</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-500/20 flex items-center justify-center">
                <BookOpen className="h-6 w-6 text-green-400" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Courses Completed</p>
                <p className="text-3xl font-bold text-white">{totalCoursesCompleted}</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-purple-500/20 flex items-center justify-center">
                <Award className="h-6 w-6 text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Skills Mastered</p>
                <p className="text-3xl font-bold text-white">4</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6 flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-orange-500/20 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-orange-400" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Current Streak</p>
                <p className="text-3xl font-bold text-white">3 Days</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Active Path Section */}
          <Card className="bg-white/5 border-white/10 lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg text-white">Active Learning Path</CardTitle>
            </CardHeader>
            <CardContent>
              {activePath ? (
                <div className="space-y-6">
                  <div>
                    <h3 className="font-bold text-xl text-white">{activePath.goal_name}</h3>
                    <div className="flex justify-between text-sm text-brand-text mt-2 mb-1">
                      <span>Progress</span>
                      <span>{activePath.completed_course_ids?.length || 0} / {activePath.total_courses} Courses</span>
                    </div>
                    <div className="w-full bg-white/10 rounded-full h-2">
                      <div 
                        className="bg-brand-primary h-2 rounded-full transition-all" 
                        style={{ width: `${activePath.total_courses > 0 ? ((activePath.completed_course_ids?.length || 0) / activePath.total_courses) * 100 : 0}%` }}
                      ></div>
                    </div>
                  </div>
                  
                  <Button onClick={() => router.push(`/learning-path?id=${activePath.id}`)} variant="outline" className="w-full border-white/20 text-white">
                    Continue Path
                  </Button>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-brand-text mb-4">You have no active learning paths.</p>
                  <Button onClick={() => router.push("/chat")} className="bg-brand-primary text-white">Create Path</Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Skill Development Radar */}
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-lg text-white">Skill Development</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center justify-center">
              <svg width={size} height={size} className="overflow-visible">
                {/* Background circles */}
                {[20, 40, 60, 80, 100].map(level => (
                  <circle key={level} cx={center} cy={center} r={(level / 100) * radius} fill="none" stroke="rgba(255,255,255,0.1)" />
                ))}
                
                {/* Axes */}
                {skills.map((_, index) => {
                  const angle = (Math.PI * 2 * index) / skills.length;
                  const { x, y } = getCoordinatesForAngle(angle, 100);
                  return (
                    <line key={index} x1={center} y1={center} x2={x} y2={y} stroke="rgba(255,255,255,0.1)" />
                  );
                })}

                {/* Data Paths */}
                <path d={getPathData('target')} fill="rgba(99, 102, 241, 0.2)" stroke="rgba(99, 102, 241, 0.8)" strokeWidth="2" />
                <path d={getPathData('current')} fill="rgba(239, 68, 68, 0.2)" stroke="rgba(239, 68, 68, 0.8)" strokeWidth="2" />
                
                {/* Labels */}
                {skills.map((skill, index) => {
                  const angle = (Math.PI * 2 * index) / skills.length;
                  const { x, y } = getCoordinatesForAngle(angle, 120);
                  return (
                    <text key={index} x={x} y={y} fill="#9ca3af" fontSize="10" textAnchor="middle" dominantBaseline="middle">
                      {skill.name}
                    </text>
                  );
                })}
              </svg>

              <div className="flex gap-4 mt-6 text-xs text-brand-text">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 bg-red-500/20 border border-red-500/80 rounded"></div>
                  Current
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 bg-indigo-500/20 border border-indigo-500/80 rounded"></div>
                  Target
                </div>
              </div>
            </CardContent>
          </Card>
          
        </div>

      </main>
    </div>
  );
}
