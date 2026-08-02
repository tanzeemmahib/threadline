"use client";

import { createContext, useContext, useMemo, useState } from "react";
import type { BackendBenchmarkDataset, BackendBenchmarkRunResponse } from "@/types";

interface EvaluationSessionValue {
  dataset: BackendBenchmarkDataset | null;
  benchmark: BackendBenchmarkRunResponse | null;
  setDataset: (dataset: BackendBenchmarkDataset | null) => void;
  setBenchmark: (benchmark: BackendBenchmarkRunResponse | null) => void;
}

const EvaluationSessionContext = createContext<EvaluationSessionValue | null>(null);

export function EvaluationSession({ children }: { children: React.ReactNode }) {
  const [dataset, setDataset] = useState<BackendBenchmarkDataset | null>(null);
  const [benchmark, setBenchmark] = useState<BackendBenchmarkRunResponse | null>(null);
  const value = useMemo(() => ({ dataset, benchmark, setDataset, setBenchmark }), [benchmark, dataset]);
  return <EvaluationSessionContext.Provider value={value}>{children}</EvaluationSessionContext.Provider>;
}

export function useEvaluationSession() {
  const value = useContext(EvaluationSessionContext);
  if (!value) throw new Error("Evaluation components must be rendered inside EvaluationSession.");
  return value;
}
