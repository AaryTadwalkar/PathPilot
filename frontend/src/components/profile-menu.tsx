"use client";

import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Pencil, Sparkles, FileUp, LogOut } from "lucide-react";

interface ProfileMenuProps {
  name: string;
  email: string;
}

export default function ProfileMenu({ name, email }: ProfileMenuProps) {
  const router = useRouter();
  const goEdit = () => router.push("/profile/edit");
  const goSkills = () =>
    router.push("/skills-projects");

  const goResume = () =>
    router.push("/resume-upload");
  const handleLogout = () => {
    localStorage.removeItem("access_token");
    router.push("/auth");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label="Open profile menu"
          className="h-9 w-9 rounded-full bg-gradient-to-br from-brand-primary to-brand-primary-hover text-white flex items-center justify-center text-sm font-semibold shadow-sm ring-offset-2 ring-offset-white hover:ring-2 hover:ring-brand-primary transition-all"
        >
          {name ? name.charAt(0).toUpperCase() : "U"}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 mt-2 border-brand-border">
        <DropdownMenuLabel className="px-3 py-2.5">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-brand-primary to-brand-primary-hover text-white flex items-center justify-center text-sm font-semibold">
              {name ? name.charAt(0).toUpperCase() : "U"}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-brand-heading truncate">{name}</p>
              <p className="text-xs font-normal text-brand-text truncate">{email}</p>
            </div>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/profile/edit")} className="cursor-pointer gap-2 text-brand-text">
          <Pencil className="h-4 w-4 text-brand-text" /> Edit Profile
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => router.push("/skills-projects")} className="cursor-pointer gap-2 text-brand-text">
          <Sparkles className="h-4 w-4 text-brand-text" /> Manage Skills & Projects
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={goResume} className="cursor-pointer gap-2 text-brand-text">
          <FileUp className="h-4 w-4 text-brand-text" /> Upload New Resume
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={handleLogout}
          className="cursor-pointer gap-2 text-red-600 focus:bg-red-50 focus:text-red-700"
        >
          <LogOut className="h-4 w-4" /> Sign Out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}