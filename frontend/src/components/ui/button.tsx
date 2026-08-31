import * as React from "react";
import { cn } from "@/lib/utils";

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:
  | "default"
  | "outline"
  | "ghost"
  | "secondary";
  size?: "default" | "icon" | "sm";
}

export function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",

        variant === "default" &&
          "bg-brand-primary text-white hover:bg-brand-primary-hover",

        variant === "outline" &&
          "border border-brand-border bg-brand-card hover:bg-brand-secondary",

        variant === "ghost" &&
          "hover:bg-brand-secondary",
        variant === "secondary" &&
        "bg-brand-secondary text-brand-heading hover:bg-brand-border",
        size === "default" && "h-10 px-4 py-2",
        size === "sm" && "h-9 px-3",
        size === "icon" && "h-10 w-10",

        className
      )}
      {...props}
    />
  );
}