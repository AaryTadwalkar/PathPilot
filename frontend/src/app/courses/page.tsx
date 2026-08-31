"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, Search, Filter, Loader2, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { searchCourses, CourseItem } from "@/services/learning.service";

export default function CoursesPage() {
  const router = useRouter();
  
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState("All");
  const [domainFilter, setDomainFilter] = useState("All");
  
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    loadCourses();
  }, [debouncedQuery, levelFilter]);

  const loadCourses = async () => {
    setLoading(true);
    try {
      const results = await searchCourses(debouncedQuery, levelFilter !== "All" ? levelFilter : undefined);
      setCourses(results);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredCourses = domainFilter === "All" 
    ? courses 
    : courses.filter(c => c.domain === domainFilter);

  const levels = ["All", "Beginner", "Intermediate", "Advanced"];
  const domains = ["All", "Python", "ML", "Web Dev", "Data Science", "Cloud"];

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col">
      <header className="bg-brand-bg border-b border-brand-border h-16 flex items-center px-6 sticky top-0 z-10">
        <Button variant="ghost" size="icon" onClick={() => router.push("/")} className="mr-4 text-brand-text hover:text-white">
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <BookOpen className="h-6 w-6 text-brand-primary mr-2" />
        <h1 className="text-xl font-bold text-white">Course Explorer</h1>
      </header>

      <main className="flex-grow max-w-7xl w-full mx-auto p-6 space-y-6">
        
        {/* Search & Filters */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex flex-col md:flex-row gap-4">
          <div className="relative flex-grow">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-brand-text" />
            <Input 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for courses, skills, or topics..." 
              className="pl-10 bg-black/20 border-white/10 text-white w-full"
            />
          </div>
          <div className="flex gap-2">
            {levels.map(level => (
              <Button 
                key={level} 
                variant={levelFilter === level ? "default" : "outline"}
                className={levelFilter === level ? "bg-brand-primary text-white" : "text-brand-text border-white/20"}
                onClick={() => setLevelFilter(level)}
              >
                {level}
              </Button>
            ))}
          </div>
        </div>

        {/* Domain Filters */}
        <div className="flex gap-2 overflow-x-auto pb-2">
          {domains.map(domain => (
            <Button
              key={domain}
              variant="ghost"
              className={`rounded-full px-4 text-sm whitespace-nowrap ${domainFilter === domain ? 'bg-white/20 text-white' : 'text-brand-text hover:bg-white/10'}`}
              onClick={() => setDomainFilter(domain)}
            >
              {domain}
            </Button>
          ))}
        </div>

        <div className="flex justify-between items-center text-brand-text text-sm">
          <p>Showing {filteredCourses.length} courses</p>
        </div>

        {/* Results Grid */}
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-brand-primary" />
          </div>
        ) : filteredCourses.length === 0 ? (
          <div className="text-center py-20">
            <BookOpen className="h-16 w-16 text-brand-text mx-auto mb-4 opacity-30" />
            <h2 className="text-xl text-white font-bold mb-2">No courses found</h2>
            <p className="text-brand-text">Try adjusting your search or filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCourses.map(course => (
              <Card key={course.id} className="bg-white/5 border-white/10 hover:border-white/20 transition-colors flex flex-col h-full">
                <CardContent className="p-5 flex flex-col flex-grow">
                  <div className="flex justify-between items-start mb-3">
                    <span className="text-xs font-semibold px-2 py-1 bg-brand-secondary text-brand-primary rounded">{course.provider}</span>
                    <div className="flex gap-2">
                      {course.is_free && <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded">Free</span>}
                      <span className={`text-xs px-2 py-1 rounded ${course.level === 'Beginner' ? 'bg-green-500/20 text-green-400' : course.level === 'Intermediate' ? 'bg-orange-500/20 text-orange-400' : 'bg-red-500/20 text-red-400'}`}>
                        {course.level}
                      </span>
                    </div>
                  </div>
                  
                  <h3 className="font-bold text-white text-lg mb-2">{course.title}</h3>
                  <p className="text-sm text-brand-text mb-4 line-clamp-2 flex-grow">{course.description}</p>
                  
                  <div className="flex flex-wrap gap-1 mb-4">
                    {course.skills_taught.slice(0, 3).map(skill => (
                      <span key={skill} className="text-[10px] px-2 py-0.5 bg-white/10 text-white rounded-full">{skill}</span>
                    ))}
                    {course.skills_taught.length > 3 && <span className="text-[10px] px-2 py-0.5 text-brand-text">+{course.skills_taught.length - 3}</span>}
                  </div>
                  
                  <div className="flex justify-between items-center pt-4 border-t border-white/10 mt-auto">
                    <span className="text-xs text-brand-text flex items-center"><BookOpen className="w-3 h-3 mr-1"/> {course.duration_hours}h</span>
                    <a href={course.url} target="_blank" rel="noreferrer" className="flex items-center text-sm text-brand-primary hover:text-brand-primary/80 transition-colors">
                      View Course <ArrowRight className="w-4 h-4 ml-1" />
                    </a>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
        
      </main>
    </div>
  );
}
