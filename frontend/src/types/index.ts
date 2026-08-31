export interface UserProfile {
  id: string;
  fullName: string;
  email: string;
  college: string;
  department: string;
  graduationYear: string;
  cgpa: string;
  githubUrl: string;
  linkedinUrl: string;
  careerInterests: string;
  skills: string[];
  projects: Project[];
  experiences: Experience[];
}

export interface Project {
  id: string;
  name: string;
  domain: string;
  description: string;
  skillsUsed: string;
}

export interface Experience {
  id: string;
  role: string;
  company: string;
  duration: string;
}

export interface JobOpportunity {
  id: string;
  company: string;
  title: string;
  location: string;
  type: "Internship" | "Full-Time";
  matchScore: number;
  matchedSkills: string[];
  missingSkills: string[];
  postedAgo: string;
  applyUrl: string;
}

export interface FilterState {
  search: string;
  types: ("Internship" | "Full-Time")[];
  minMatchScore: number;
}
