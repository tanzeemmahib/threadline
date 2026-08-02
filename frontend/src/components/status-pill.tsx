import type { ReactNode } from "react";

export function StatusPill({
  children,
  tone = "slate",
}: {
  children: ReactNode;
  tone?: "cyan" | "teal" | "amber" | "red" | "slate";
}) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}
