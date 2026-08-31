export interface UserSkill {
  skill: string;
  category?: string;
}

export interface Project {
  name: string;
  description: string;
  domain?: string;
  skills_used: string[];
}

export interface UserProfileCreate {
  name: string;
  email: string;
  college: string;
  department: string;
  graduation_year: number;
  cgpa: number;

  github_url?: string;
  linkedin_url?: string;

  career_interests: string[];

  opportunity_preferences: string[];

  experience: string[];
  experience_duration?: string;

  skills: UserSkill[];
  projects: Project[];
}