import type { Metadata } from "next";
import "./globals.css";
import "./landing.css";
import "./workspace.css";
import "./evaluation.css";
import "./methodology.css";
import "./research.css";
import "./trials.css";
import "./print.css";

export const metadata: Metadata = {
  title: {
    default: "THREADLINE — Humanitarian record reconciliation",
    template: "%s — THREADLINE",
  },
  description:
    "An uncertainty-aware workflow for tracing possible connections across synthetic multilingual humanitarian records.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
