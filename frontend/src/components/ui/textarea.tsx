import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea =
  React.forwardRef<
    HTMLTextAreaElement,
    React.ComponentProps<"textarea">
  >(
    (
      {
        className,
        ...props
      },
      ref
    ) => {
      return (
        <textarea
          className={cn(
            "flex min-h-[80px] w-full rounded-md border border-brand-border bg-brand-card px-3 py-2 text-sm",
            className
          )}
          ref={ref}
          {...props}
        />
      );
    }
  );

Textarea.displayName =
  "Textarea";

export { Textarea };