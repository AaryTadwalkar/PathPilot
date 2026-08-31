"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  GraduationCap,
  BarChart2,
  MessageSquare,
  Map,
  BookOpen,
} from "lucide-react";

import ProfileMenu from "../components/profile-menu";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card";

import { Button } from "../components/ui/button";

const modules = [
  {
    title: "AI Learning Assistant",
    subtitle: "Conversational Goal Setting",
    description: "Chat with AI to describe your learning goals. Get a personalized learning path in minutes.",
    route: "/chat",
    active: true,
    icon: MessageSquare,
  },
  {
    title: "My Learning Path",
    subtitle: "Personalized Roadmap",
    description: "View your AI-generated learning roadmap with courses, milestones, and progress tracking.",
    route: "/learning-path",
    active: true,
    icon: Map,
  },
  {
    title: "Progress Dashboard",
    subtitle: "Skill Development Tracker",
    description: "Track your learning progress, skill acquisition, and milestone completion over time.",
    route: "/dashboard",
    active: true,
    icon: BarChart2,
  },
  {
    title: "Course Explorer",
    subtitle: "Course Catalog",
    description: "Browse and search curated courses across all domains. Filter by skill, level, and provider.",
    route: "/courses",
    active: true,
    icon: BookOpen,
  },
];

export default function DashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState({
    name: "User",
    email: "",
  });

  useEffect(() => {
    const storedUser = localStorage.getItem("user");

    if (storedUser) {
      const parsed = JSON.parse(storedUser);
      setUser({
        name:
          parsed.name ||
          parsed.email?.split("@")[0] ||
          "User",
        email: parsed.email || "",
      });
    }
  }, []);

  return (
    <div className="min-h-screen bg-brand-bg">
      <header className="bg-brand-bg border-b border-brand-border">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-brand-primary flex items-center justify-center">
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold">PathPilot</span>
          </div>

          <div className="flex items-center gap-3">
            <ProfileMenu name={user.name} email={user.email} />
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-bold">Welcome Back 👋</h1>
        <p className="text-brand-text mt-2">
          AI-powered personalized learning path assistant
        </p>

        <div className="grid md:grid-cols-3 gap-6 mt-10">
          {modules.map((module, index) => {
            const Icon = module.icon;

            return (
              <Card key={index} className={`flex flex-col h-full shadow-sm ${module.active ? 'hover:shadow-md transition-shadow border-brand-primary' : ''}`}>
                <CardHeader>
                  <div className={`h-10 w-10 rounded-lg flex items-center justify-center mb-4 ${module.active ? 'bg-brand-secondary text-brand-primary' : 'bg-brand-bg text-brand-text'}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle className={`text-xl ${module.active ? '' : 'text-brand-text'}`}>
                    {module.title}
                  </CardTitle>
                  <p className={`text-xs font-semibold uppercase tracking-wider ${module.active ? 'text-brand-primary' : 'text-brand-text'}`}>
                    {module.subtitle}
                  </p>
                </CardHeader>
                
                <CardContent className="flex-grow flex flex-col justify-between">
                  <p className="text-sm text-brand-text mb-6">
                    {module.description}
                  </p>
                  
                  {module.active ? (
                    <Button 
                      onClick={() => router.push(module.route)}
                      className="w-full bg-brand-primary hover:bg-brand-primary text-white shadow-sm"
                    >
                      Launch Module
                    </Button>
                  ) : (
                    <Button disabled variant="outline" className="w-full text-brand-text border-brand-border">
                      In Development
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </main>
    </div>
  );
}