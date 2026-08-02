"use client";

export function PrintButton() {
  return <button className="button-primary" type="button" onClick={() => window.print()}>Print / save packet</button>;
}

