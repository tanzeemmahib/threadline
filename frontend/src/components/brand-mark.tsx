import { ThreadLink } from "@/components/thread-motion";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <ThreadLink variant="bare" motion="quiet" bridge className="brand" href="/" aria-label="THREADLINE home">
      <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
        <path d="M7 10C15 10 14 20 21 20s6 10 12 10" fill="none" stroke="var(--brass)" strokeLinecap="round" strokeWidth="1.35" />
        <circle cx="7" cy="10" r="2.4" fill="var(--background)" stroke="var(--brass)" strokeWidth="1.25" />
        <circle cx="21" cy="20" r="2.4" fill="var(--background)" stroke="var(--brass)" strokeWidth="1.25" />
        <circle cx="33" cy="30" r="2.4" fill="var(--background)" stroke="var(--brass)" strokeWidth="1.25" />
      </svg>
      {!compact && <span>THREADLINE</span>}
    </ThreadLink>
  );
}
