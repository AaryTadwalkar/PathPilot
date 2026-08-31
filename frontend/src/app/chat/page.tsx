"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Send,
  Brain,
  ArrowLeft,
  Loader2,
  CheckCircle,
  User,
  Bot
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { sendChatMessage, generateLearningPath } from "@/services/learning.service";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const router = useRouter();
  
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Hi! I'm PathPilot, your AI learning assistant. Tell me about your learning goals — what do you want to achieve? For example: 'I want to become a machine learning engineer' or 'I want to learn web development from scratch'."
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [sessionId, setSessionId] = useState<number | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [extractedProfile, setExtractedProfile] = useState<Record<string, any> | null>(null);
  const [isProfileComplete, setIsProfileComplete] = useState(false);
  const [isGeneratingPath, setIsGeneratingPath] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (!storedUser) {
      router.push("/auth");
    }
  }, [router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

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
    } catch (error: any) {
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, I encountered an error. Please try again." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGeneratePath = async () => {
    if (!extractedProfile) return;
    setIsGeneratingPath(true);
    try {
      const payload = {
        goal_id: extractedProfile.goal_id || "custom",
        current_skills: extractedProfile.current_skills || [],
        experience_level: extractedProfile.experience_level || "Beginner",
        weekly_study_hours: extractedProfile.weekly_study_hours || 10
      };
      const res = await generateLearningPath(payload);
      router.push(`/learning-path?id=${res.path_id}`);
    } catch (err: any) {
      alert(err.message || "Failed to generate path");
    } finally {
      setIsGeneratingPath(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col">
      <header className="bg-brand-bg border-b border-brand-border h-16 flex items-center px-6 sticky top-0 z-10">
        <Button variant="ghost" size="icon" onClick={() => router.push("/")} className="mr-4 text-brand-text hover:text-white">
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <Brain className="h-6 w-6 text-brand-primary mr-2" />
        <h1 className="text-xl font-bold">PathPilot AI Assistant</h1>
      </header>

      <main className="flex-grow flex flex-col md:flex-row max-w-7xl w-full mx-auto p-4 gap-6 overflow-hidden h-[calc(100vh-4rem)]">
        
        {/* Chat Area */}
        <Card className="flex-grow flex flex-col bg-white/5 border-white/10 h-full overflow-hidden">
          <CardContent className="flex-grow p-0 flex flex-col h-full">
            <div className="flex-grow overflow-y-auto p-4 space-y-4">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`flex max-w-[80%] items-end gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                    <div className={`h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-indigo-600' : 'bg-brand-secondary'}`}>
                      {msg.role === 'user' ? <User className="h-4 w-4 text-white" /> : <Bot className="h-4 w-4 text-brand-primary" />}
                    </div>
                    <div className={`p-3 rounded-2xl ${msg.role === 'user' ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-white/10 text-white rounded-bl-none'}`}>
                      {msg.content}
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex max-w-[80%] items-end gap-2">
                    <div className="h-8 w-8 rounded-full bg-brand-secondary flex items-center justify-center flex-shrink-0">
                      <Bot className="h-4 w-4 text-brand-primary" />
                    </div>
                    <div className="p-3 rounded-2xl bg-white/10 text-brand-text rounded-bl-none flex gap-1 items-center">
                      <span className="animate-bounce">.</span>
                      <span className="animate-bounce delay-100">.</span>
                      <span className="animate-bounce delay-200">.</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            
            <form onSubmit={handleSendMessage} className="p-4 border-t border-white/10 bg-white/5 flex gap-2">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Type your message..."
                className="flex-grow bg-black/20 border-white/10 text-white"
                disabled={isLoading || isGeneratingPath}
              />
              <Button type="submit" disabled={!inputValue.trim() || isLoading || isGeneratingPath} className="bg-brand-primary hover:bg-brand-primary/90 text-white">
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Sidebar */}
        <Card className="w-full md:w-80 flex-shrink-0 bg-white/5 border-white/10 h-max max-h-full overflow-y-auto">
          <CardContent className="p-6 space-y-6">
            <div>
              <h2 className="text-lg font-semibold flex items-center gap-2 text-white">
                <Brain className="h-5 w-5 text-brand-primary" />
                Profile Extraction
              </h2>
              <p className="text-sm text-brand-text mt-1">AI is building your profile based on our conversation.</p>
            </div>
            
            <div className="space-y-4">
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <p className="text-xs text-brand-text mb-1 uppercase font-semibold">🎯 Goal</p>
                <p className="text-sm text-white font-medium">{extractedProfile?.goal_id || extractedProfile?.goal_name || "Listening..."}</p>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <p className="text-xs text-brand-text mb-1 uppercase font-semibold">📊 Level</p>
                <p className="text-sm text-white font-medium">{extractedProfile?.experience_level || "Listening..."}</p>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <p className="text-xs text-brand-text mb-1 uppercase font-semibold">⏰ Weekly Hours</p>
                <p className="text-sm text-white font-medium">{extractedProfile?.weekly_study_hours ? `${extractedProfile.weekly_study_hours} hrs/week` : "Listening..."}</p>
              </div>
              <div className="p-3 bg-black/20 rounded-lg border border-white/5">
                <p className="text-xs text-brand-text mb-1 uppercase font-semibold">💡 Current Skills</p>
                <p className="text-sm text-white font-medium">{extractedProfile?.current_skills?.join(", ") || "Listening..."}</p>
              </div>
            </div>

            {isProfileComplete && (
              <Button 
                onClick={handleGeneratePath} 
                disabled={isGeneratingPath}
                className="w-full bg-green-600 hover:bg-green-700 text-white shadow-[0_0_15px_rgba(22,163,74,0.5)] transition-all animate-pulse hover:animate-none"
              >
                {isGeneratingPath ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                ✨ Generate My Learning Path
              </Button>
            )}
          </CardContent>
        </Card>

      </main>
    </div>
  );
}
