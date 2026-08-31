"use client";

/**
 * chat/page.tsx
 * =============
 * What this file does:
 *   Conversational AI chat interface for learner profiling.
 *   Fetches the user's saved profile on mount, shows a banner confirming
 *   the AI knows their skills, and skips asking for already-known info.
 *
 * Overall design:
 *   - Reads user from localStorage on mount, calls /learning/profile to load skills
 *   - First AI message is personalised with user's name and skill summary
 *   - Sends user_id in every message so backend injects profile context into Gemini
 *   - Sidebar shows extracted profile fields updating in real-time
 *
 * Elements:
 *   ChatPage         — main page component
 *   ProfileBanner    — top banner showing loaded profile skills
 *   handleSendMessage — sends message + session_id to backend
 *   handleGeneratePath — generates path from extracted profile
 *
 * Final output:
 *   Full chat UI at /chat with profile-aware AI responses
 */

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Send, Brain, ArrowLeft, Loader2, CheckCircle, User, Bot, Sparkles
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { sendChatMessage, generateLearningPath } from "@/services/learning.service";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface UserProfile {
  id: number;
  name: string;
  skills: string[];
  career_interests: string;
}

export default function ChatPage() {
  const router = useRouter();

  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [sessionId, setSessionId] = useState<number | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [extractedProfile, setExtractedProfile] = useState<Record<string, any> | null>(null);
  const [isProfileComplete, setIsProfileComplete] = useState(false);
  const [isGeneratingPath, setIsGeneratingPath] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load user profile on mount and personalise opening message
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (!storedUser) { router.push("/auth"); return; }

    const user = JSON.parse(storedUser);

    // Try to load full profile from backend
    const token = localStorage.getItem("access_token");
    fetch(`http://127.0.0.1:8000/learning/profile`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          const profile: UserProfile = {
            id: data.user_id || user.id,
            name: data.name || user.name || "there",
            skills: data.skills || [],
            career_interests: data.career_interests || "",
          };
          setUserProfile(profile);
          setMessages([buildOpeningMessage(profile)]);
        } else {
          setUserProfile({ id: user.id, name: user.name || "there", skills: [], career_interests: "" });
          setMessages([buildOpeningMessage(null)]);
        }
      })
      .catch(() => {
        setMessages([buildOpeningMessage(null)]);
      });
  }, [router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  function buildOpeningMessage(profile: UserProfile | null): ChatMessage {
    if (profile && profile.skills.length > 0) {
      const skillsPreview = profile.skills.slice(0, 5).join(", ");
      const more = profile.skills.length > 5 ? ` +${profile.skills.length - 5} more` : "";
      return {
        role: "assistant",
        content: `Hi ${profile.name}! 👋 I've loaded your profile — I can see you already know **${skillsPreview}${more}**.\n\nSo let's skip the basics! What's your specific learning goal? For example:\n• "I want to become a machine learning engineer"\n• "I want to build and deploy AI apps"\n• "I want to get into data science"`
      };
    }
    return {
      role: "assistant",
      content: "Hi! I'm PathPilot, your AI learning advisor. What do you want to achieve? For example: 'I want to become a machine learning engineer' or 'I want to learn web development from scratch'."
    };
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMsg = inputValue.trim();
    setInputValue("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const response = await sendChatMessage(userMsg, sessionId);
      setMessages(prev => [...prev, { role: "assistant", content: response.reply }]);
      if (response.session_id) setSessionId(response.session_id);
      if (response.extracted_profile) setExtractedProfile(response.extracted_profile);
      setIsProfileComplete(response.is_profile_complete);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, I hit an error. Please try again." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGeneratePath = async () => {
    if (!extractedProfile) return;
    setIsGeneratingPath(true);
    try {
      const res = await generateLearningPath({
        goal_id: extractedProfile.goal_id || "GOAL_ML_ENGINEER",
        current_skills: extractedProfile.current_skills || userProfile?.skills || [],
        experience_level: extractedProfile.experience_level || "intermediate",
        weekly_study_hours: extractedProfile.weekly_hours ?? 10,
      });
      router.push(`/learning-path?id=${res.path_id}`);
    } catch (err: any) {
      alert(err.message || "Failed to generate path");
    } finally {
      setIsGeneratingPath(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-brand-border h-16 flex items-center px-6 sticky top-0 z-10 shadow-sm">
        <Button variant="ghost" size="icon" onClick={() => router.push("/")} className="mr-4 text-brand-text hover:text-brand-heading">
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <Brain className="h-6 w-6 text-brand-primary mr-2" />
        <h1 className="text-xl font-bold text-brand-heading">PathPilot AI Assistant</h1>

        {/* Profile loaded badge */}
        {userProfile && userProfile.skills.length > 0 && (
          <div className="ml-auto flex items-center gap-2 bg-green-50 border border-green-200 rounded-full px-3 py-1">
            <CheckCircle className="h-3.5 w-3.5 text-green-600" />
            <span className="text-xs text-green-700 font-medium">
              Profile loaded · {userProfile.skills.length} skills
            </span>
          </div>
        )}
      </header>

      <main className="flex-grow flex flex-col md:flex-row max-w-7xl w-full mx-auto p-4 gap-6 overflow-hidden h-[calc(100vh-4rem)]">

        {/* Chat Area */}
        <Card className="flex-grow flex flex-col border-brand-border shadow-sm h-full overflow-hidden">
          <CardContent className="flex-grow p-0 flex flex-col h-full">
            <div className="flex-grow overflow-y-auto p-4 space-y-4">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`flex max-w-[82%] items-end gap-2 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                    {/* Avatar */}
                    <div className={`h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === "user" ? "bg-brand-primary" : "bg-brand-secondary border border-brand-border"}`}>
                      {msg.role === "user"
                        ? <User className="h-4 w-4 text-white" />
                        : <Bot className="h-4 w-4 text-brand-primary" />}
                    </div>
                    {/* Bubble */}
                    <div className={`p-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-brand-primary text-white rounded-br-none"
                        : "bg-white border border-brand-border text-brand-heading rounded-bl-none shadow-sm"
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-end gap-2">
                    <div className="h-8 w-8 rounded-full bg-brand-secondary border border-brand-border flex items-center justify-center flex-shrink-0">
                      <Bot className="h-4 w-4 text-brand-primary" />
                    </div>
                    <div className="p-3 rounded-2xl bg-white border border-brand-border rounded-bl-none shadow-sm flex gap-1 items-center">
                      <span className="h-2 w-2 bg-brand-text rounded-full animate-bounce" style={{animationDelay:"0ms"}}></span>
                      <span className="h-2 w-2 bg-brand-text rounded-full animate-bounce" style={{animationDelay:"150ms"}}></span>
                      <span className="h-2 w-2 bg-brand-text rounded-full animate-bounce" style={{animationDelay:"300ms"}}></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="p-4 border-t border-brand-border bg-white flex gap-2">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Type your message..."
                className="flex-grow border-brand-border text-brand-heading placeholder:text-brand-text"
                disabled={isLoading || isGeneratingPath}
              />
              <Button
                type="submit"
                disabled={!inputValue.trim() || isLoading || isGeneratingPath}
                className="bg-brand-primary hover:bg-brand-primary/90 text-white"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Sidebar */}
        <Card className="w-full md:w-80 flex-shrink-0 border-brand-border shadow-sm h-max max-h-full overflow-y-auto">
          <CardContent className="p-6 space-y-5">
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2 text-brand-heading">
                <Sparkles className="h-4 w-4 text-brand-primary" />
                Your Profile
              </h2>
              <p className="text-xs text-brand-text mt-1">
                {userProfile?.skills.length
                  ? "AI knows your resume. Just tell it your goal!"
                  : "AI is building your profile from our conversation."}
              </p>
            </div>

            {/* Known skills from resume */}
            {userProfile && userProfile.skills.length > 0 && (
              <div className="p-3 bg-green-50 rounded-lg border border-green-200">
                <p className="text-xs text-green-700 font-semibold mb-2 uppercase tracking-wide">✅ Skills from Resume</p>
                <div className="flex flex-wrap gap-1">
                  {userProfile.skills.slice(0, 10).map(s => (
                    <span key={s} className="text-[11px] px-2 py-0.5 bg-green-100 text-green-800 rounded-full">{s}</span>
                  ))}
                  {userProfile.skills.length > 10 && (
                    <span className="text-[11px] text-brand-text">+{userProfile.skills.length - 10} more</span>
                  )}
                </div>
              </div>
            )}

            {/* AI extracted fields */}
            <div className="space-y-3">
              {[
                { label: "🎯 Goal", value: extractedProfile?.goal_statement },
                { label: "📊 Level", value: extractedProfile?.experience_level },
                { label: "⏰ Weekly Hours", value: extractedProfile?.weekly_hours ? `${extractedProfile.weekly_hours} hrs/week` : null },
                { label: "💡 Interests", value: extractedProfile?.interests?.join(", ") },
              ].map(({ label, value }) => (
                <div key={label} className="p-3 bg-brand-secondary rounded-lg border border-brand-border">
                  <p className="text-[10px] text-brand-text mb-1 uppercase font-semibold tracking-wide">{label}</p>
                  <p className={`text-sm font-medium ${value ? "text-brand-heading" : "text-brand-text italic"}`}>
                    {value || "Listening…"}
                  </p>
                </div>
              ))}
            </div>

            {isProfileComplete && (
              <Button
                onClick={handleGeneratePath}
                disabled={isGeneratingPath}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold"
              >
                {isGeneratingPath
                  ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />Generating…</>
                  : <><Sparkles className="h-4 w-4 mr-2" />✨ Generate My Learning Path</>}
              </Button>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
