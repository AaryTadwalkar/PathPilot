"use client";

import {
  useEffect,
  useState,
} from "react";

import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { Input } from "@/components/ui/input";

import { Label } from "@/components/ui/label";

import { Button } from "@/components/ui/button";

import {
  getProfile,
  saveProfile,
} from "@/services/profile.service";

export default function EditProfilePage() {

  const router = useRouter();

  const [loading, setLoading] =
    useState(true);

  const [saving, setSaving] =
    useState(false);

  const [userId, setUserId] =
    useState<number | null>(null);

  const [form, setForm] = useState({
    name: "",
    email: "",
    college: "",
    department: "",
    graduation_year: 2028,
    cgpa: 0,
    github_url: "",
    linkedin_url: "",
    career_interests: [] as string[],
    experience: [] as string[],
    experience_duration: "",
    skills: [],
    projects: [],
    // Preserve certifications when editing so re-save doesn't wipe them
    certifications: [] as string[],
  });

  useEffect(() => {

    async function loadProfile() {

      try {

        const token =
          localStorage.getItem(
            "access_token"
          );

        if (!token) {
          router.push("/auth");
          return;
        }

        const payload = JSON.parse(
          atob(token.split(".")[1])
        );

        setUserId(payload.id);

        const data: any =
          await getProfile(payload.id);

        setForm(data);

      } catch (err) {
        console.error(err);
        alert("Failed to load profile");
      } finally {
        setLoading(false);
      }
    }

    loadProfile();

  }, [router]);

  async function handleSave() {
    try {
      setSaving(true);
      await saveProfile(form);
      alert("Profile updated successfully!");
      router.push("/");
    } catch (err: any) {
      alert("Save failed: " + (err?.message || "Unknown error. Check browser console."));
    } finally {
      setSaving(false);
    }
  }


  if (loading) {
    return (
      <div className="p-10">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-brand-bg p-6">
      <div className="max-w-3xl mx-auto mb-4">

        <Link
            href="/"
            className="text-sm text-brand-primary hover:text-brand-primary"
        >
            ← Back to Dashboard
        </Link>

        </div>  
      <div className="max-w-3xl mx-auto">

        <Card>

          <CardHeader>
            <CardTitle>
              Edit Academic Profile
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-5">

            <div>
              <Label>Name</Label>

              <Input
                value={form.name}
                onChange={(e) =>
                  setForm({
                    ...form,
                    name: e.target.value,
                  })
                }
              />
            </div>

            <div>
              <Label>Email</Label>

              <Input
                disabled
                value={form.email}
              />
            </div>

            <div>
              <Label>College</Label>

              <Input
                value={form.college}
                onChange={(e) =>
                  setForm({
                    ...form,
                    college: e.target.value,
                  })
                }
              />
            </div>

            <div>
              <Label>Department</Label>

              <Input
                value={form.department}
                onChange={(e) =>
                  setForm({
                    ...form,
                    department:
                      e.target.value,
                  })
                }
              />
            </div>

            <div>
              <Label>Graduation Year</Label>

              <Input
                type="number"
                value={form.graduation_year}
                onChange={(e) =>
                  setForm({
                    ...form,
                    graduation_year:
                      Number(e.target.value),
                  })
                }
              />
            </div>

            <div>
              <Label>CGPA</Label>

              <Input
                type="number"
                step="0.1"
                value={form.cgpa}
                onChange={(e) =>
                  setForm({
                    ...form,
                    cgpa:
                      Number(e.target.value),
                  })
                }
              />
            </div>

            <div>
              <Label>GitHub URL</Label>

              <Input
                value={form.github_url || ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    github_url:
                      e.target.value,
                  })
                }
              />
            </div>

            <div>
              <Label>LinkedIn URL</Label>

              <Input
                value={form.linkedin_url || ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    linkedin_url:
                      e.target.value,
                  })
                }
              />
            </div>

            <Button
              onClick={handleSave}
              disabled={saving}
            >
              {saving
                ? "Saving..."
                : "Save Changes"}
            </Button>

          </CardContent>

        </Card>

      </div>

    </div>
  );
}