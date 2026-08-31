"use client";

import * as React from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";

export const DropdownMenu =
  DropdownMenuPrimitive.Root;

export const DropdownMenuTrigger =
  DropdownMenuPrimitive.Trigger;

export const DropdownMenuContent = ({
  className = "",
  ...props
}: any) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      sideOffset={4}
      className={`z-50 min-w-[8rem] overflow-hidden rounded-md border bg-brand-card p-1 shadow-md ${className}`}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
);

export const DropdownMenuItem = ({
  className = "",
  ...props
}: any) => (
  <DropdownMenuPrimitive.Item
    className={`
      relative flex cursor-pointer
      select-none items-center
      rounded-sm px-2 py-1.5 text-sm
      outline-none hover:bg-brand-secondary
      ${className}
    `}
    {...props}
  />
);

export const DropdownMenuLabel = ({
  className = "",
  ...props
}: any) => (
  <div
    className={`px-2 py-1.5 text-sm font-semibold ${className}`}
    {...props}
  />
);

export const DropdownMenuSeparator = ({
  className = "",
  ...props
}: any) => (
  <div
    className={`-mx-1 my-1 h-px bg-brand-border ${className}`}
    {...props}
  />
);