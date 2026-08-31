"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";

export const Tabs = TabsPrimitive.Root;

export const TabsList = ({
  className = "",
  ...props
}: any) => (
  <TabsPrimitive.List
    className={`inline-flex h-10 items-center justify-center rounded-md bg-brand-secondary p-1 ${className}`}
    {...props}
  />
);

export const TabsTrigger = ({
  className = "",
  ...props
}: any) => (
  <TabsPrimitive.Trigger
    className={`inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium data-[state=active]:bg-brand-card ${className}`}
    {...props}
  />
);

export const TabsContent =
  TabsPrimitive.Content;