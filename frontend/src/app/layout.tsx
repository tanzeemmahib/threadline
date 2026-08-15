import type { Metadata } from "next";
import { ThreadlineInteractionLayer } from "@/components/threadline-interaction-layer";
import { threadMotionCssVariables } from "@/lib/thread-motion";
import "@fontsource/ibm-plex-sans/300.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./globals.css";
import "./landing.css";
import "./workspace.css";
import "./evaluation.css";
import "./methodology.css";
import "./research.css";
import "./trials.css";
import "./archive-theme.css";
import "./thread-motion.css";
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
    <html lang="en" style={threadMotionCssVariables}>
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <ThreadlineInteractionLayer />
        {children}
      </body>
    </html>
  );
}
