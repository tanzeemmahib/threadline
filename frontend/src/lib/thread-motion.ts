import type { CSSProperties } from "react";

export const threadMotion = {
  micro: 160,
  fast: 240,
  signal: 300,
  standard: 420,
  trace: 580,
  resolve: 720,
  route: 320,
  arrowDelay: 70,
  magneticControl: 4,
  magneticContent: 5,
  proximityRadius: 60,
  easeOut: "cubic-bezier(0.16, 1, 0.3, 1)",
  easeTrace: "cubic-bezier(0.22, 1, 0.36, 1)",
  easeResolve: "cubic-bezier(0.65, 0, 0.35, 1)",
} as const;

export type ThreadConnectionState =
  | "fragmented"
  | "searching"
  | "partial"
  | "connected"
  | "interrupted";

export type ThreadResolutionPhase = "fragmented" | "resolving" | "resolved";

export const threadMotionCssVariables = {
  "--thread-motion-micro": `${threadMotion.micro}ms`,
  "--thread-motion-fast": `${threadMotion.fast}ms`,
  "--thread-motion-signal": `${threadMotion.signal}ms`,
  "--thread-motion-standard": `${threadMotion.standard}ms`,
  "--thread-motion-trace": `${threadMotion.trace}ms`,
  "--thread-motion-resolve": `${threadMotion.resolve}ms`,
  "--thread-motion-route": `${threadMotion.route}ms`,
  "--thread-arrow-delay": `${threadMotion.arrowDelay}ms`,
  "--thread-ease-out": threadMotion.easeOut,
  "--thread-ease-trace": threadMotion.easeTrace,
  "--thread-ease-resolve": threadMotion.easeResolve,
} as CSSProperties;
