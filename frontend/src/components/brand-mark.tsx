import Link from "next/link";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <Link className="brand" href="/" aria-label="THREADLINE home">
      <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
        <path d="M7 9h26M20 9v22" fill="none" stroke="#415a67" strokeWidth="1.2" />
        <path d="M8 10C15 10 14 20 21 20s6 10 12 10" fill="none" stroke="var(--cyan)" strokeLinecap="round" strokeWidth="1.8" />
        <circle cx="8" cy="10" r="2.7" fill="var(--background)" stroke="var(--cyan)" strokeWidth="1.5" />
        <circle cx="21" cy="20" r="2.7" fill="var(--background)" stroke="var(--teal)" strokeWidth="1.5" />
        <circle cx="33" cy="30" r="2.7" fill="var(--background)" stroke="var(--amber)" strokeWidth="1.5" />
      </svg>
      {!compact && <span>THREADLINE</span>}
    </Link>
  );
}

