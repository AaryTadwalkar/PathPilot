"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { Textarea } from "@/components/ui/textarea";


interface Props {
  formData: any;
  setFormData: any;
  onSave: () => void;
  loading?: boolean;
  oldProfile?: any;
}

const uid = () =>
  Math.random()
    .toString(36)
    .substring(2, 9);

export default function ProfileForm({
  formData,
  setFormData,
  onSave,
  loading,
  oldProfile,
}: Props) {

  const [newSkill, setNewSkill] =
    useState("");

  function updateField(
    field: string,
    value: any
  ) {
    setFormData({
      ...formData,
      [field]: value,
    });
  }

  function changed(field: string) {

    if (!oldProfile) return false;

    return (
      JSON.stringify(
        oldProfile[field]
      ) !==
      JSON.stringify(
        formData[field]
      )
    );
  }

  function fieldClass(field: string) {

    return changed(field)
      ? "border-amber-400 bg-amber-50"
      : "";
  }
  const oldSkills =
  oldProfile?.skills || [];

  const normalizedOldSkills =
    oldSkills.map((s: any) =>
      typeof s === "string"
        ? s
        : s.skill
    );

  const currentSkills =
    formData.skills || [];


  const oldProjects =
  oldProfile?.projects || [];

  function isNewProject(
    project: any
  ) {

    return !oldProjects.some(
      (p: any) =>
        p.name === project.name
    );
  }

  
  function isNewSkill(skill: string) {

    return !normalizedOldSkills.includes(
      skill
    );
  }
  // =========================
  // SKILLS
  // =========================

  function addSkill() {

    if (!newSkill.trim()) return;

    const updated = [
      ...(formData.skills || []),
      newSkill.trim(),
    ];

    updateField(
      "skills",
      updated
    );

    setNewSkill("");
  }

  function removeSkill(skill: string) {

    updateField(
      "skills",
      formData.skills.filter(
        (s: string) =>
          s !== skill
      )
    );
  }

  // =========================
  // PROJECTS
  // =========================

  function addProject() {

    updateField(
      "projects",
      [
        ...(formData.projects || []),
        {
          id: uid(),
          name: "",
          domain: "",
          description: "",
          skillsUsed: "",
        },
      ]
    );
  }

  function removeProject(index: number) {

    const updated =
      [...formData.projects];

    updated.splice(index, 1);

    updateField(
      "projects",
      updated
    );
  }

  function updateProject(
    index: number,
    field: string,
    value: string
  ) {

    const updated =
      [...formData.projects];

    updated[index][field] =
      value;

    updateField(
      "projects",
      updated
    );
  }

  // =========================
  // OPPORTUNITY PREFERENCES
  // =========================

  function togglePreference(
    preference: string
  ) {

    const current =
      formData.opportunityPreferences || [];

    const exists =
      current.includes(
        preference
      );

    updateField(
      "opportunityPreferences",
      exists
        ? current.filter(
            (p: string) =>
              p !== preference
          )
        : [
            ...current,
            preference,
          ]
    );
  }

  return (
    <div className="space-y-8">

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Learning Profile</h2>
        
        <div>
          <Label>What do you want to learn or achieve?</Label>
          <Input
            value={formData.learningGoal || ""}
            placeholder="e.g. Become a Machine Learning Engineer"
            onChange={(e) => updateField("learningGoal", e.target.value)}
          />
        </div>

        <div>
          <Label>Experience Level</Label>
          <select 
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            value={formData.experienceLevel || "Beginner"}
            onChange={(e) => updateField("experienceLevel", e.target.value)}
          >
            <option value="Beginner">Beginner</option>
            <option value="Intermediate">Intermediate</option>
            <option value="Advanced">Advanced</option>
          </select>
        </div>

        <div>
          <Label>How many hours per week can you study?</Label>
          <Input
            type="number"
            value={formData.weeklyStudyHours || 10}
            onChange={(e) => updateField("weeklyStudyHours", parseInt(e.target.value) || 10)}
          />
        </div>

        <div>
          <Label>Learning Style</Label>
          <select 
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            value={formData.learningStyle || "Mixed"}
            onChange={(e) => updateField("learningStyle", e.target.value)}
          >
            <option value="Visual">Visual</option>
            <option value="Reading">Reading</option>
            <option value="Practice-first">Practice-first</option>
            <option value="Mixed">Mixed</option>
          </select>
        </div>
      </div>

      {/* BASIC INFO */}

      <details className="space-y-4 group">

        <summary className="text-xl font-semibold cursor-pointer list-none flex items-center">
          Academic Background (Optional)
          <span className="ml-2 text-sm text-brand-text group-open:hidden">▼ Show</span>
          <span className="ml-2 text-sm text-brand-text hidden group-open:inline">▲ Hide</span>
        </summary>
        <div className="pt-4 space-y-4">
        <div>
          <Label>Name</Label>

          <Input
            value={formData.name || formData.fullName || ""}
            className={fieldClass("name")}
            onChange={(e) => {
              updateField("name", e.target.value);
              updateField("fullName", e.target.value);
            }}
          />
           {
            changed("name") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.name}
              </p>
            )
          }

        </div>

        <div>
          <Label>College</Label>

          <Input
            value={
              formData.college || ""
            }
            className={fieldClass("college")}
            onChange={(e) =>
              updateField(
                "college",
                e.target.value
              )
            }
          />
           {
            changed("college") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.college}
              </p>
            )
          }

        </div>

        <div>
          <Label>Department</Label>

          <Input
            value={
              formData.department || ""
            }
            className={fieldClass("department")}
            onChange={(e) =>
              updateField(
                "department",
                e.target.value
              )
            }
          />
           {
            changed("department") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.department}
              </p>
            )
          }

        </div>

        <div>
          <Label>
            Graduation Year
          </Label>

          <Input
            type="number"
            value={
              formData.graduation_year || ""
            }
            className={fieldClass(
              "graduation_year"
            )}
            onChange={(e) =>
              updateField(
                "graduation_year",
                e.target.value
              )
            }
          />
           {
            changed("graduation_year") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.graduation_year}
              </p>
            )
          }

        </div>

        <div>
          <Label>CGPA</Label>

          <Input
            type="number"
            value={
              formData.cgpa || ""
            }
            className={fieldClass("cgpa")}
            onChange={(e) =>
              updateField(
                "cgpa",
                e.target.value
              )
            }
          />
           {
            changed("cgpa") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.cgpa}
              </p>
            )
          }

        </div>

      </div>
      </details>

      {/* LINKS */}

      <div className="space-y-4">

        <h2 className="text-xl font-semibold">
          Links
        </h2>

        <div>
          <Label>GitHub</Label>

          <Input
            value={
              formData.github_url || ""
            }
            className={fieldClass(
              "github_url"
            )}
            onChange={(e) =>
              updateField(
                "github_url",
                e.target.value
              )
            }
          />
           {
            changed("github_url") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.github_url}
              </p>
            )
          }

        </div>

        <div>
          <Label>LinkedIn</Label>

          <Input
            value={
              formData.linkedin_url || ""
            }
            className={fieldClass(
              "linkedin_url"
            )}
            onChange={(e) =>
              updateField(
                "linkedin_url",
                e.target.value
              )
            }
          />
           {
            changed("linkedin_url") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {oldProfile?.linkedin_url}
              </p>
            )
          }

        </div>

      </div>

      {/* INTERESTS */}

      <div className="space-y-4">

        <h2 className="text-xl font-semibold">
          Career Interests
        </h2>

        <Textarea
          value={
            Array.isArray(
              formData.career_interests
            )
              ? formData.career_interests.join(", ")
              : formData.career_interests || ""
          }
          onChange={(e) =>
            updateField(
              "career_interests",
              e.target.value
                .split(",")
                .map((s) =>
                  s.trim()
                )
            )
          }
          />
          {
            changed("career_interests") && (
              <p className="text-xs text-brand-text mt-1">
                Previous:
                {" "}
                {
                  oldProfile?.career_interests?.join(", ")
                }
              </p>
            )
          }
      </div>

      {/* OPPORTUNITY PREFERENCES */}

      <div className="space-y-4">

        <h2 className="text-xl font-semibold">
          Opportunity Preferences
        </h2>

        <div className="flex flex-wrap gap-3">

          {[
            "Internship",
            "Full-Time",
            "Hackathon",
            "Fellowship",
          ].map((pref) => {

            const active =
              (
                formData.opportunityPreferences || []
              ).includes(pref);

            return (
              <Button
                key={pref}
                type="button"
                variant={
                  active
                    ? "default"
                    : "outline"
                }
                onClick={() =>
                  togglePreference(
                    pref
                  )
                }
              >
                {pref}
              </Button>
            );
          })}

        </div>

      </div>

      {/* SKILLS */}

      <div className="space-y-4">

        <h2 className="text-xl font-semibold">
          Skills
        </h2>

        <div className="flex gap-2">

          <Input
            value={newSkill}
            onChange={(e) =>
              setNewSkill(
                e.target.value
              )
            }
          />

          <Button
            type="button"
            onClick={addSkill}
          >
            Add
          </Button>

        </div>

        <div className="flex flex-wrap gap-2">

          {(formData.skills || [])
            .map(
              (
                skill: string
              ) => (
                <Badge
                  className={
                    isNewSkill(skill)
                      ? "bg-amber-100 text-amber-800 border border-amber-300"
                      : ""
                  }
                >
                  {skill}

                  {
                    isNewSkill(skill) && (
                      <span className="ml-2 text-[10px] font-bold">
                        NEW
                      </span>
                    )
                  }
                </Badge>
              )
            )}

        </div>

      </div>

      {/* PROJECTS */}

      <div className="space-y-6">

        <div className="flex items-center justify-between">

          <h2 className="text-xl font-semibold">
            Projects
          </h2>

          <Button
            type="button"
            onClick={addProject}
          >
            Add Project
          </Button>

        </div>

        {(formData.projects || [])
          .map(
            (
              p: any,
              index: number
            ) => (
              <div
                key={index}
                className={`border rounded-xl p-5 ${
                  isNewProject(p)
                    ? "border-amber-300 bg-amber-50"
                    : ""
                }`}
              >
               {
                isNewProject(p) && (
                  <div className="mb-3">
                    <span className="text-xs font-semibold bg-amber-200 text-amber-900 px-2 py-1 rounded-full">
                      NEW PROJECT
                    </span>
                  </div>
                )
              }
                <Input
                  placeholder="Project Name"
                  value={
                    p.name || ""
                  }
                  onChange={(e) =>
                    updateProject(
                      index,
                      "name",
                      e.target.value
                    )
                  }
                />

                <Input
                  placeholder="Domain"
                  value={
                    p.domain || ""
                  }
                  onChange={(e) =>
                    updateProject(
                      index,
                      "domain",
                      e.target.value
                    )
                  }
                />

                <Textarea
                  placeholder="Description"
                  value={
                    p.description || ""
                  }
                  onChange={(e) =>
                    updateProject(
                      index,
                      "description",
                      e.target.value
                    )
                  }
                />

                <Input
                  placeholder="Skills Used"
                  value={
                    p.skillsUsed || ""
                  }
                  onChange={(e) =>
                    updateProject(
                      index,
                      "skillsUsed",
                      e.target.value
                    )
                  }
                />

                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    removeProject(
                      index
                    )
                  }
                >
                  Delete Project
                </Button>

              </div>
            )
          )}

      </div>

      {/* SAVE */}

      <Button
        onClick={onSave}
        disabled={loading}
        className="w-full"
      >
        {
          loading
            ? "Saving..."
            : "Save Profile"
        }
      </Button>

    </div>
  );
}