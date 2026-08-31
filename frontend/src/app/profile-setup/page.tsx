"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { GraduationCap, Upload, X, Plus, Loader2, Briefcase, FolderOpen } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { saveProfile } from "@/services/profile.service";
import ProfileForm from "@/components/profile-form";
const uid = () => Math.random().toString(36).substring(2, 9);

export default function ProfileSetupPage() {
  const router = useRouter();
  
  // Authentication & Loading State
  const [userId, setUserId] = useState<number | null>(null);
  const [email, setEmail] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);

  // Form Data State — use snake_case to match ProfileForm component bindings
    const [formData, setFormData] = useState({
    fullName: "",
    learningGoal: "",
    experienceLevel: "Beginner",
    weeklyStudyHours: 10,
    learningStyle: "Mixed",
    college: "",
    department: "",
    graduationYear: "2028",
    cgpa: "0.0",
    github_url: "",          // snake_case: matches ProfileForm's setFormData key
    linkedin_url: "",        // snake_case: matches ProfileForm's setFormData key
    careerInterests: "",
    opportunityPreferences: [
    "Internship"
  ],
    skills: [] as string[],
    projects: [] as any[],
    experience: [] as any[],
    experienceDuration: "",
    certifications: [] as string[],  // NEW: Gemini-extracted cert names
  });
  const [newSkill, setNewSkill] = useState("");
  const togglePreference = (
  preference: string
  ) => {

    setFormData(prev => {

      const exists =
        prev.opportunityPreferences.includes(
          preference
        );

      return {
        ...prev,

        opportunityPreferences:
          exists
            ? prev.opportunityPreferences.filter(
                p => p !== preference
              )
            : [
                ...prev.opportunityPreferences,
                preference
              ]
      };
    });

  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/auth");
      return;
    }
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      setUserId(payload.id);
      setEmail(payload.sub);
    } catch (e) {
      router.push("/auth");
    }
  }, [router]);

  const handleUpload = async () => {
    if (!file || !userId) return;
    setIsProcessing(true);
    
    const data = new FormData();
    data.append("user_id", userId.toString());
    data.append("file", file);

    try {
      const response = await fetch("http://127.0.0.1:8000/profile/upload-resume", {
        method: "POST",
        body: data,
      });

      if (!response.ok) throw new Error("Extraction failed");

      const result = await response.json();
      const extracted = result.extracted_data;

      // Populate Replit's UI state with Gemini's extraction
      setFormData({
        fullName: extracted.name || "",
        learningGoal: "",
        experienceLevel: "Beginner",
        weeklyStudyHours: 10,
        learningStyle: "Mixed",
        college: extracted.college || "",
        department: extracted.department || "",
        graduationYear: extracted.graduation_year?.toString() || "2028",
        cgpa: extracted.cgpa?.toString() || "0.0",
        github_url: extracted.github_url || "",       // snake_case to match ProfileForm
        linkedin_url: extracted.linkedin_url || "",   // snake_case to match ProfileForm
        careerInterests: extracted.career_interests?.join(", ") || "",
        opportunityPreferences: extracted.opportunity_preferences || ["Internship"],
        skills: extracted.skills?.map((s: any) => s.skill) || [],
        projects: extracted.projects?.map((p: any) => ({
          id: uid(),
          name: p.name,
          domain: p.domain || "",
          description: p.description,
          skillsUsed: p.skills_used?.join(", ") || ""
        })) || [],
        experience: extracted.experience?.map((e: string) => ({
          id: uid(),
          role: e,
          company: "",
          duration: ""
        })) || [],
        experienceDuration: extracted.experience_duration || "",
        certifications: extracted.certifications || [],  // carry Gemini-extracted certs
      });
      
      setStep(2);
    } catch (error: any) {
      const detail: string = error?.message || "";
      if (detail.includes("insufficient content") || detail.includes("text-based PDF")) {
        alert(
          "⚠️ Could not read this PDF.\n\n" +
          "Your resume appears to be a scanned image, Canva export, or a PDF without an embedded text layer.\n\n" +
          "Please export your resume as a text-based PDF from Word, Google Docs, or Overleaf, and try again."
        );
      } else {
        alert("Failed to process resume. Ensure the backend is running and try again.");
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSave = async () => {
    setIsProcessing(true);
    
    try {
      // Reformat UI state back into Python Pydantic Schema
      const finalPayload = {
        name: formData.fullName,
        email: email,
        college: formData.college,
        department: formData.department,
        graduation_year: parseInt(formData.graduationYear) || 2028,
        cgpa: parseFloat(formData.cgpa) || 0.0,
        github_url: formData.github_url || null,       // snake_case state key
        linkedin_url: formData.linkedin_url || null,   // snake_case state key
        career_interests: formData.careerInterests.split(",").map(i => i.trim()).filter(Boolean),
        opportunity_preferences: formData.opportunityPreferences,
        experience: formData.experience.map(
          e =>
            e.company
              ? `${e.role} at ${e.company}`
              : e.role
        ),
        experience_duration: formData.experienceDuration,
        skills: formData.skills.map(s => ({ skill: s, category: "General" })),
        projects: formData.projects.map(p => ({
          name: p.name,
          domain: p.domain,
          description: p.description,
          skills_used: p.skillsUsed.split(",").map((s: string) => s.trim()).filter(Boolean)
        })),
        // NEW: certifications extracted by Gemini — flows to users.certifications → certificate_engine
        certifications: formData.certifications || [],
      };

      await saveProfile(finalPayload);

      router.push("/");
    } catch (error) {
      alert("Error saving profile to database.");
    } finally {
      setIsProcessing(false);
    }
  };

  // Dynamic Array Handlers
  const handleAddSkill = () => {
    if (newSkill.trim() && !formData.skills.includes(newSkill.trim())) {
      setFormData(prev => ({ ...prev, skills: [...prev.skills, newSkill.trim()] }));
      setNewSkill("");
    }
  };
  const removeSkill = (sk: string) => setFormData(p => ({ ...p, skills: p.skills.filter(s => s !== sk) }));
  
  const addProject = () => setFormData(p => ({ ...p, projects: [...p.projects, { id: uid(), name: "", domain: "", description: "", skillsUsed: "" }] }));
  const removeProject = (id: string) => setFormData(p => ({ ...p, projects: p.projects.filter(proj => proj.id !== id) }));
  const updateProject = (id: string, field: string, value: string) => setFormData(p => ({
    ...p, projects: p.projects.map(proj => proj.id === id ? { ...proj, [field]: value } : proj)
  }));

  // KEEP THE UPLOAD SCREEN FOR STEP 1
  if (step === 1) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center p-4">
        <Card className="w-full max-w-lg shadow-lg">
          <CardHeader className="text-center">
            <div className="mx-auto w-12 h-12 bg-brand-secondary rounded-full flex items-center justify-center mb-4">
              <Upload className="h-6 w-6 text-brand-primary" />
            </div>
            <CardTitle>Intelligent Onboarding</CardTitle>
            <CardDescription>Upload your resume to instantly pre-fill your profile.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="border-2 border-dashed border-brand-border rounded-xl p-8 text-center hover:bg-brand-bg transition-colors">
              <Input type="file" accept=".pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mx-auto max-w-xs cursor-pointer" />
            </div>
            <Button onClick={handleUpload} disabled={!file || isProcessing} className="w-full bg-brand-primary hover:bg-brand-primary">
              {isProcessing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Extract Intelligence"}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // REPLACE THE GIANT FORM WITH YOUR NEW COMPONENT FOR STEP 2
  return (
    <ProfileForm
      formData={formData}
      setFormData={setFormData}
      onSave={handleSave}
    />
  );
}