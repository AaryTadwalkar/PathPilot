import * as React from "react";
import { cn } from "@/lib/utils";

interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "outline" | "secondary";
}

export function Badge({
  className,
  variant = "default",
  ...props
}: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",

        variant === "default" &&
          "bg-brand-primary text-white border-transparent",

        variant === "outline" &&
          "border-brand-border text-brand-text",

        variant === "secondary" &&
          "bg-brand-secondary text-brand-text border-transparent",

        className
      )}
      {...props}
    />
  );
}