"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Map,
  CheckCircle,
  Circle,
  Clock,
  BookOpen,
  Award,
  ChevronDown,
  ChevronUp,
  Loader2
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchLearningPath, fetchAllPaths, updateProgress, LearningPathResponse } from "@/services/learning.service";

export default function LearningPathPage() {
  const router = useRouter();
  
  const [pathData, setPathData] = useState<LearningPathResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [completedCourses, setCompletedCourses] = useState<Set<string>>(new Set());
  const [expandedPhases, setExpandedPhases] = useState<Set<number>>(new Set([1]));

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (!storedUser) {
      router.push("/auth");
      return;
    }
    
    loadData();
  }, [router]);

  const loadData = async () => {
    try {
      setLoading(true);
      const urlParams = new URLSearchParams(window.location.search);
      const idParam = urlParams.get("id");
      
      let targetId = idParam ? parseInt(idParam) : null;
      
      if (!targetId) {
        const paths = await fetchAllPaths();
        if (paths && paths.length > 0) {
          targetId = paths[0].id;
        }
      }
      
      if (targetId) {
        const data = await fetchLearningPath(targetId);
        setPathData(data);
        // Assuming there might be a completed field in the data in reality, 
        // but for now we'll just track locally or via some other means
        // If data has completed_courses, we'd initialize the set here.
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const togglePhase = (phaseNumber: number) => {
    const newExpanded = new Set(expandedPhases);
    if (newExpanded.has(phaseNumber)) {
      newExpanded.delete(phaseNumber);
    } else {
      newExpanded.add(phaseNumber);
    }
    setExpandedPhases(newExpanded);
  };

  const toggleCourseCompletion = async (courseId: string) => {
    if (!pathData) return;
    
    const isCompleted = completedCourses.has(courseId);
    const newCompleted = !isCompleted;
    
    // Optimistic UI update
    const newSet = new Set(completedCourses);
    if (newCompleted) newSet.add(courseId);
    else newSet.delete(courseId);
    setCompletedCourses(newSet);
    
    try {
      await updateProgress(pathData.path_id, courseId, newCompleted);
    } catch (err) {
      // Revert on failure
      console.error("Failed to update progress");
      const revertSet = new Set(completedCourses);
      if (isCompleted) revertSet.add(courseId);
      else revertSet.delete(courseId);
      setCompletedCourses(revertSet);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-primary" />
      </div>
    );
  }

  if (!pathData) {
    return (
      <div className="min-h-screen bg-brand-bg flex flex-col items-center justify-center p-4">
        <Map className="h-16 w-16 text-brand-text mb-4 opacity-50" />
        <h2 className="text-2xl font-bold text-white mb-2">No Learning Path Yet</h2>
        <p className="text-brand-text mb-6 text-center max-w-md">You haven't generated a learning path yet. Chat with PathPilot to create one tailored to your goals.</p>
        <Button onClick={() => router.push("/chat")} className="bg-brand-primary hover:bg-brand-primary/90">
          Create Learning Path
        </Button>
      </div>
    );
  }

  const completionPercentage = pathData.total_courses > 0 
    ? Math.round((completedCourses.size / pathData.total_courses) * 100) 
    : 0;

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col">
      <header className="bg-brand-bg border-b border-brand-border h-16 flex items-center px-6 sticky top-0 z-10">
        <Button variant="ghost" size="icon" onClick={() => router.push("/")} className="mr-4 text-brand-text hover:text-white">
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <Map className="h-6 w-6 text-brand-primary mr-2" />
        <h1 className="text-xl font-bold text-white">My Learning Path</h1>
      </header>

      <main className="flex-grow max-w-7xl w-full mx-auto p-6 space-y-6">
        
        {/* Top Stats Bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-full bg-brand-secondary flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-brand-primary" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Total Courses</p>
                <p className="text-2xl font-bold text-white">{pathData.total_courses}</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                <Clock className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Estimated Time</p>
                <p className="text-2xl font-bold text-white">{pathData.total_weeks} weeks</p>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-full bg-green-500/20 flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-400" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Completed</p>
                <p className="text-2xl font-bold text-white">{completedCourses.size}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-full bg-orange-500/20 flex items-center justify-center">
                <Award className="h-5 w-5 text-orange-400" />
              </div>
              <div>
                <p className="text-sm text-brand-text">Progress</p>
                <p className="text-2xl font-bold text-white">{completionPercentage}%</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-white/10 rounded-full h-2.5 mb-6">
          <div className="bg-brand-primary h-2.5 rounded-full transition-all duration-500" style={{ width: `${completionPercentage}%` }}></div>
        </div>

        <div className="flex flex-col lg:flex-row gap-6">
          
          {/* Main Phases Content */}
          <div className="flex-grow space-y-4">
            <h2 className="text-2xl font-bold text-white mb-4">Goal: {pathData.goal_name}</h2>
            
            {pathData.phases.map((phase) => (
              <Card key={phase.phase_number} className="bg-white/5 border-white/10 overflow-hidden">
                <div 
                  className="p-4 cursor-pointer hover:bg-white/5 transition-colors flex justify-between items-center"
                  onClick={() => togglePhase(phase.phase_number)}
                >
                  <div className="flex items-center gap-4">
                    <div className="h-8 w-8 rounded bg-brand-primary/20 text-brand-primary flex items-center justify-center font-bold">
                      {phase.phase_number}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white">{phase.phase_name}</h3>
                      <p className="text-sm text-brand-text">{phase.estimated_weeks} weeks</p>
                    </div>
                  </div>
                  {expandedPhases.has(phase.phase_number) ? <ChevronUp className="h-5 w-5 text-brand-text" /> : <ChevronDown className="h-5 w-5 text-brand-text" />}
                </div>
                
                {expandedPhases.has(phase.phase_number) && (
                  <div className="p-4 border-t border-white/10 bg-black/20">
                    <p className="text-brand-text mb-4 text-sm">{phase.description}</p>
                    
                    <div className="flex flex-wrap gap-2 mb-6">
                      {phase.skills_gained.map(skill => (
                        <span key={skill} className="px-2 py-1 bg-white/10 text-xs rounded text-white">{skill}</span>
                      ))}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {phase.courses.map(course => (
                        <Card key={course.id} className="bg-white/5 border-white/10 hover:border-white/20 transition-colors flex flex-col">
                          <CardContent className="p-4 flex-grow flex flex-col">
                            <div className="flex justify-between items-start mb-2">
                              <span className="text-xs font-semibold px-2 py-1 bg-brand-secondary text-brand-primary rounded">{course.provider}</span>
                              <span className={`text-xs px-2 py-1 rounded ${course.level === 'Beginner' ? 'bg-green-500/20 text-green-400' : course.level === 'Intermediate' ? 'bg-orange-500/20 text-orange-400' : 'bg-red-500/20 text-red-400'}`}>
                                {course.level}
                              </span>
                            </div>
                            <h4 className="font-bold text-white text-sm mb-1 line-clamp-2">{course.title}</h4>
                            <p className="text-xs text-brand-text mb-3">{course.duration_hours} hours</p>
                            
                            <p className="text-xs text-brand-text mb-4 line-clamp-3 italic flex-grow">"{course.why_recommended}"</p>
                            
                            <div className="flex justify-between items-center mt-auto pt-4 border-t border-white/10">
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className={`text-xs ${completedCourses.has(course.id) ? 'text-green-400' : 'text-brand-text'}`}
                                onClick={() => toggleCourseCompletion(course.id)}
                              >
                                {completedCourses.has(course.id) ? <CheckCircle className="h-4 w-4 mr-1" /> : <Circle className="h-4 w-4 mr-1" />}
                                {completedCourses.has(course.id) ? 'Completed' : 'Mark Done'}
                              </Button>
                              <a href={course.url} target="_blank" rel="noreferrer" className="text-xs text-brand-primary hover:underline">
                                View Course
                              </a>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>

          {/* Side Panel */}
          <div className="w-full lg:w-80 flex-shrink-0 space-y-4">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-sm uppercase text-brand-text tracking-wider">Target Skills (Gaps)</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="flex flex-wrap gap-2">
                  {pathData.skill_gaps.map(skill => (
                    <span key={skill} className="px-2 py-1 bg-indigo-500/20 text-indigo-300 text-xs rounded border border-indigo-500/30">
                      {skill}
                    </span>
                  ))}
                  {pathData.skill_gaps.length === 0 && <p className="text-xs text-brand-text">No gaps identified.</p>}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-sm uppercase text-brand-text tracking-wider">Already Known</CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="flex flex-wrap gap-2">
                  {pathData.already_known.map(skill => (
                    <span key={skill} className="px-2 py-1 bg-green-500/20 text-green-300 text-xs rounded border border-green-500/30">
                      {skill}
                    </span>
                  ))}
                  {pathData.already_known.length === 0 && <p className="text-xs text-brand-text">No prior skills logged.</p>}
                </div>
              </CardContent>
            </Card>
          </div>
          
        </div>
      </main>
    </div>
  );
}
