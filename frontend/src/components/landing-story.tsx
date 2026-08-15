"use client";

import { ThreadLink } from "@/components/thread-motion";
import { useEffect, useRef, useState } from "react";
import { LandingEvidenceThread } from "@/components/landing-evidence-thread";
import { WorkflowStrip } from "@/components/workflow-strip";

const evidenceRows = [
  {
    id: "name",
    label: "Name",
    values: ["Amira Saleh", "Ameera Salih", "Amira Salah"],
    result: "Comparable form",
    note: "The family-report value is translated; all three observed spellings remain visible.",
  },
  {
    id: "dob",
    label: "Date of birth",
    values: ["14 FEB 2010", "12 APR 2010", "14 FEB 2010"],
    result: "Soft conflict",
    note: "The shelter value came from an unverified handwritten card.",
  },
  {
    id: "phone",
    label: "Emergency contact",
    values: ["+999 555 0142", "+999 555 0142", "+999 555 0142"],
    result: "Not distinguishing",
    note: "The rival copied this contact from a wrist card, so it is not independent evidence.",
  },
] as const;

const auditEvents = [
  ["04:16:22.014", "Ingest", "FAMILY-042 / source retained"],
  ["04:16:22.193", "Extract", "7 evidence spans"],
  ["04:16:22.247", "Validate", "source integrity verified"],
  ["04:16:22.319", "Retrieve", "2 candidate threads"],
  ["04:16:22.461", "Policy", "material conflict retained"],
  ["04:16:22.487", "Disposition", "human review"],
] as const;

function ArchiveDocument({
  className = "",
  source,
  record,
  name,
  detail,
  language,
}: {
  className?: string;
  source: string;
  record: string;
  name: string;
  detail: string;
  language?: "Arabic" | "English";
}) {
  return (
    <article className={`archive-document ${className}`}>
      <span className="archive-document__crop archive-document__crop--tl" aria-hidden="true" />
      <span className="archive-document__crop archive-document__crop--br" aria-hidden="true" />
      <header>
        <span>{source}</span>
        <span className="archive-document__stamp">SOURCE / RECEIVED</span>
      </header>
      <p className="archive-document__record">RECORD {record}</p>
      <h3 lang={language === "Arabic" ? "ar" : undefined} dir={language === "Arabic" ? "rtl" : undefined}>{name}</h3>
      <p className="archive-document__detail">{detail}</p>
      <footer>
        <span>SYNTHETIC FIELD RECORD</span>
        <span>CHAIN / INTACT</span>
      </footer>
    </article>
  );
}

export function LandingStory() {
  const rootRef = useRef<HTMLDivElement>(null);
  const threadDrawnRef = useRef<SVGPathElement>(null);
  const ambientVideoRef = useRef<HTMLVideoElement>(null);
  const [activeScene, setActiveScene] = useState(-1);
  const [activeEvidence, setActiveEvidence] = useState<(typeof evidenceRows)[number]["id"]>("name");
  const [allowAmbientMotion, setAllowAmbientMotion] = useState(false);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    let animationFrame = 0;
    let storyTop = 0;
    let distance = 1;
    let scrollBound = false;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const entranceFrame = requestAnimationFrame(() => setActiveScene(0));
    const measure = () => {
      storyTop = window.scrollY + root.getBoundingClientRect().top;
      distance = Math.max(root.offsetHeight - window.innerHeight, 1);
    };
    const updateProgress = () => {
      if (reducedMotion.matches) {
        if (threadDrawnRef.current) threadDrawnRef.current.style.strokeDashoffset = "0";
        return;
      }
      cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(() => {
        const progress = Math.min(1, Math.max(0, (window.scrollY - storyTop) / distance));
        if (threadDrawnRef.current) threadDrawnRef.current.style.strokeDashoffset = String(1 - progress);
      });
    };
    const syncScrollBinding = () => {
      if (reducedMotion.matches && scrollBound) {
        window.removeEventListener("scroll", updateProgress);
        scrollBound = false;
      } else if (!reducedMotion.matches && !scrollBound) {
        window.addEventListener("scroll", updateProgress, { passive: true });
        scrollBound = true;
      }
      measure();
      updateProgress();
    };

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActiveScene(Number((visible.target as HTMLElement).dataset.storyScene ?? 0));
      },
      { threshold: [0.25, 0.5, 0.72], rootMargin: "-8% 0px -8% 0px" },
    );

    const resizeObserver = new ResizeObserver(() => {
      measure();
      updateProgress();
    });
    root.querySelectorAll<HTMLElement>("[data-story-scene]").forEach((scene) => observer.observe(scene));
    resizeObserver.observe(root);
    reducedMotion.addEventListener("change", syncScrollBinding);
    window.addEventListener("resize", syncScrollBinding);
    syncScrollBinding();

    return () => {
      cancelAnimationFrame(entranceFrame);
      cancelAnimationFrame(animationFrame);
      observer.disconnect();
      resizeObserver.disconnect();
      if (scrollBound) window.removeEventListener("scroll", updateProgress);
      reducedMotion.removeEventListener("change", syncScrollBinding);
      window.removeEventListener("resize", syncScrollBinding);
    };
  }, []);

  useEffect(() => {
    const video = ambientVideoRef.current;
    if (!video) return;
    if (allowAmbientMotion && activeScene === 0) void video.play().catch(() => undefined);
    else video.pause();
  }, [activeScene, allowAmbientMotion]);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const compactViewport = window.matchMedia("(max-width: 760px)");
    const syncAmbientMotion = () => setAllowAmbientMotion(!reducedMotion.matches && !compactViewport.matches);
    reducedMotion.addEventListener("change", syncAmbientMotion);
    compactViewport.addEventListener("change", syncAmbientMotion);
    syncAmbientMotion();
    return () => {
      reducedMotion.removeEventListener("change", syncAmbientMotion);
      compactViewport.removeEventListener("change", syncAmbientMotion);
    };
  }, []);

  return (
    <div className="documentary-story" ref={rootRef}>
      <svg className="documentary-thread" viewBox="0 0 1440 900" preserveAspectRatio="none" aria-hidden="true">
        <path
          className="documentary-thread__ghost"
          d="M74 900 C74 780 150 754 150 656 S74 530 204 472 S356 388 356 290 S520 208 684 248 S890 356 1012 306 S1214 178 1368 108"
        />
        <path
          ref={threadDrawnRef}
          className="documentary-thread__drawn"
          pathLength="1"
          style={{ strokeDashoffset: 1 }}
          d="M74 900 C74 780 150 754 150 656 S74 530 204 472 S356 388 356 290 S520 208 684 248 S890 356 1012 306 S1214 178 1368 108"
        />
      </svg>

      <section className={`story-scene story-opening ${activeScene === 0 ? "is-active" : ""}`} data-story-scene="0" id="case" aria-labelledby="opening-title">
        <div className="story-opening__atmosphere" aria-hidden="true">
          <span className="story-opening__poster" />
          {allowAmbientMotion ? (
            <video
              autoPlay
              className="story-opening__video"
              loop
              muted
              onCanPlay={(event) => event.currentTarget.classList.add("is-ready")}
              onError={() => setAllowAmbientMotion(false)}
              playsInline
              poster="/media/threadline/hero-archive-poster.webp"
              preload="metadata"
              ref={ambientVideoRef}
            >
              <source src="/media/threadline/hero-archive-loop.webm" type="video/webm" />
            </video>
          ) : null}
          <span className="story-opening__veil" />
        </div>
        <LandingEvidenceThread />
        <div className="story-opening__index mono-label">ARCHIVE / CASE 0042</div>
        <h1 className="story-opening__title editorial-title" id="opening-title">
          <span>A person</span>
          <span>can disappear</span>
          <span>between records.</span>
        </h1>
        <div className="story-opening__statement">
          <p className="mono-label">RECORDS FRAGMENT.</p>
          <h2>Identity shouldn’t.</h2>
          <p>THREADLINE investigates possible record connections while preserving every source, contradiction, and unresolved gap.</p>
          <div>
            <ThreadLink variant="bare" motion="signature" arrow="forward" bridge magnetic proximity className="editorial-button" data-threadline-cta href="/demo?demo=guided">Run the evidence challenge<span className="sr-only">Trace a Synthetic Case</span></ThreadLink>
            <ThreadLink variant="text" arrow="external" bridge href="/workspace">Explore the technical workspace</ThreadLink>
          </div>
        </div>
        <dl className="story-opening__metadata mono-label">
          <div><dt>Case</dt><dd>0042</dd></div>
          <div><dt>Incident</dt><dd>CYCLONE ILYRA</dd></div>
          <div><dt>Source status</dt><dd>FRAGMENTED</dd></div>
        </dl>
        <span className="story-opening__registration" aria-hidden="true">+</span>
      </section>

      <section className={`story-scene story-record ${activeScene === 1 ? "is-active" : ""}`} data-story-scene="1" aria-labelledby="first-record-title">
        <div className="story-shadow story-shadow--single" aria-hidden="true" />
        <div className="story-record__caption">
          <p className="mono-label">01 / SOURCE MATERIAL</p>
          <h2 className="editorial-title" id="first-record-title">One record survives.</h2>
          <p>Not a profile. Not a verdict. A fragment with custody, language, and uncertainty still attached.</p>
        </div>
        <ArchiveDocument
          className="archive-document--hero"
          source="Shelter intake"
          record="SHELTER-118"
          name="Ameera Salih"
          detail="DOB / 12 APR 2010 · HILLCREST SCHOOL · 18:40"
        />
      </section>

      <section className={`story-scene story-silence ${activeScene === 2 ? "is-active" : ""}`} data-story-scene="2" aria-labelledby="silence-title">
        <div>
          <p className="mono-label">SOURCE CONTINUITY / LOST</p>
          <h2 className="editorial-title" id="silence-title">And then, nothing.</h2>
        </div>
      </section>

      <section className={`story-scene story-discovery ${activeScene === 3 ? "is-active" : ""}`} data-story-scene="3" aria-labelledby="discovery-title">
        <header className="story-discovery__header">
          <p className="mono-label">02 / DISTRIBUTED ARCHIVE</p>
          <h2 className="editorial-title" id="discovery-title">
            <span>Records surface.</span>
            <span>Systems diverge.</span>
            <span>One candidate thread.</span>
            <span className="story-discovery__doubt">One credible rival.</span>
          </h2>
        </header>
        <div className="story-discovery__archive">
          <div className="archive-table" role="group" aria-label="Six fictional records inspected across separate systems: two leading records, three contextual records, and one credible rival">
            <svg className="archive-table__thread" viewBox="0 0 1000 720" preserveAspectRatio="none" aria-hidden="true">
              <path className="archive-table__thread-support" pathLength="1" d="M142 128 C315 130 304 288 490 288 S694 452 838 454" />
              <path className="archive-table__thread-rival" pathLength="1" d="M490 288 C616 248 708 166 866 172" />
              <circle cx="142" cy="128" r="5" /><circle cx="490" cy="288" r="5" /><circle cx="838" cy="454" r="5" /><circle className="is-rival" cx="866" cy="172" r="5" />
            </svg>
            <ArchiveDocument className="archive-document--fragment archive-document--fragment-1" source="Family tracing report" record="FAMILY-042" name="Amira Saleh" detail="NARIN QUAY · 18:20 · TRANSLATED" />
            <ArchiveDocument className="archive-document--fragment archive-document--fragment-2" source="Shelter intake" record="SHELTER-118" name="Ameera Salih" detail="HILLCREST SCHOOL · 18:40 · DIRECT" />
            <ArchiveDocument className="archive-document--fragment archive-document--fragment-3" source="Field clinic register" record="CLINIC-077" name="A. Salih" detail="EAST LEVEE CLINIC · 08:15" />
            <ArchiveDocument className="archive-document--fragment archive-document--fragment-4 archive-document--peripheral" source="Evacuation manifest" record="EVAC-031" name="A. Salih" detail="NARIN QUAY · 13:20 · WATER-DAMAGED" />
            <ArchiveDocument className="archive-document--fragment archive-document--fragment-5 archive-document--peripheral" source="Witness note" record="WITNESS-064" name="Ameera Salih" detail="SOUTH CANAL · 17:00 · TRANSLATED" />
            <ArchiveDocument className="archive-document--fragment archive-document--fragment-rival" source="Aid registration" record="AID-209" name="Amira Salah" detail="RIVERBEND DEPOT · 17:55 · RIVAL" />
          </div>
          <div className="story-discovery__resolution" aria-label="Six records are inspected; two form a candidate thread routed to human review">
            <span><strong>6</strong> inspected</span>
            <i aria-hidden="true">→</i>
            <span><strong>2</strong> evidence-linked</span>
            <i aria-hidden="true">→</i>
            <span className="is-review">Human review</span>
          </div>
        </div>
      </section>

      <section className={`story-scene story-alignment ${activeScene === 4 ? "is-active" : ""}`} data-story-scene="4" id="method" aria-labelledby="alignment-title">
        <header className="story-section-heading">
          <p className="mono-label">03 / EVIDENCE ALIGNMENT</p>
          <h2 className="editorial-title" id="alignment-title">A similar record<br />is not the same person.</h2>
          <p>Select a field to inspect what the system may compare—and what it refuses to conclude.</p>
        </header>
        <div className="alignment-workbench">
          <svg className="alignment-thread" viewBox="0 0 1200 620" preserveAspectRatio="none" aria-hidden="true">
            <path className="alignment-thread__support" pathLength="1" d="M238 112 C416 112 408 114 572 114 S802 112 1058 112 M238 300 C410 300 462 306 628 306 S836 306 1058 306" />
            <path className="alignment-thread__rival" pathLength="1" d="M238 494 C436 494 472 438 616 438 S824 502 1058 502" />
          </svg>
          <div className="alignment-workbench__sources" role="group" aria-label="Source records">
            <ArchiveDocument source="Family report" record="FAMILY-042" name="Amira Saleh" detail="ORIGINAL / ARABIC + TRANSLATED" />
            <ArchiveDocument source="Shelter intake" record="SHELTER-118" name="Ameera Salih" detail="ORIGINAL / ENGLISH" />
            <ArchiveDocument className="archive-document--rival" source="Rival record" record="AID-209" name="Amira Salah" detail="CREDIBLE RIVAL / RETAINED" />
          </div>
          <div className="story-evidence-matrix" role="group" aria-labelledby="story-evidence-matrix-title">
            <h3 className="sr-only" id="story-evidence-matrix-title">Interactive evidence matrix</h3>
            <div className="evidence-matrix__head mono-label"><span>Field</span><span>Observed evidence</span><span>Result</span></div>
            {evidenceRows.map((row) => (
              <button
                className="evidence-matrix__row"
                type="button"
                key={row.id}
                aria-pressed={activeEvidence === row.id}
                aria-expanded={activeEvidence === row.id}
                onClick={() => setActiveEvidence(row.id)}
              >
                <strong>{row.label}</strong>
                <span>{row.values.join(" / ")}</span>
                <span>{row.result}</span>
                <small>{activeEvidence === row.id ? row.note : null}</small>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className={`story-scene story-consequence ${activeScene === 5 ? "is-active" : ""}`} data-story-scene="5" aria-labelledby="consequence-title">
        <div className="story-shadow story-shadow--pair" aria-hidden="true"><span /><span /></div>
        <h2 className="editorial-title" id="consequence-title">
          <span>Behind every row<br />is someone’s history.</span>
          <span>Behind every decision<br />is a consequence.</span>
        </h2>
      </section>

      <section className={`story-scene story-reveal ${activeScene === 6 ? "is-active" : ""}`} data-story-scene="6" aria-labelledby="reveal-title">
        <svg className="story-reveal__mark" viewBox="0 0 160 90" aria-hidden="true">
          <path d="M16 18 C48 18 47 45 80 45 S112 72 144 72" />
          <circle cx="16" cy="18" r="5" /><circle cx="80" cy="45" r="5" /><circle cx="144" cy="72" r="5" />
        </svg>
        <h2 id="reveal-title">THREADLINE</h2>
        <p>An experimental safety and review layer<br />for possible record connections.</p>
      </section>

      <section className={`story-scene story-product ${activeScene === 7 ? "is-active" : ""}`} data-story-scene="7" aria-labelledby="product-title">
        <header className="story-product__intro">
          <p className="mono-label">04 / THE ARCHIVE BECOMES THE WORKBENCH</p>
          <h2 className="editorial-title" id="product-title">The records align.<br />The uncertainty remains.</h2>
        </header>
        <section className="story-process" aria-labelledby="story-process-title">
          <header>
            <p className="mono-label">TRACEABLE PROCESS / SOURCE TO REVIEW</p>
            <h3 id="story-process-title">Evidence moves. Provenance stays attached.</h3>
          </header>
          <WorkflowStrip />
          <span className="story-process__handoff" aria-hidden="true" />
        </section>
        <div className="product-workbench" role="group" aria-label="THREADLINE forensic workbench preview">
          <section className="product-workbench__column product-workbench__source" aria-labelledby="source-material-title">
            <div className="product-workbench__label"><span>01</span><h3 id="source-material-title">Source material</h3></div>
            <ArchiveDocument source="Family report" record="FAMILY-042" name="Amira Saleh" detail="ARABIC · TRANSLATED · 18:20" />
            <ArchiveDocument source="Shelter intake" record="SHELTER-118" name="Ameera Salih" detail="ENGLISH · DIRECT INTAKE · 18:40" />
          </section>
          <section className="product-workbench__column product-workbench__matrix" aria-labelledby="matrix-title">
            <div className="product-workbench__label"><span>02</span><h3 id="matrix-title">Evidence matrix</h3></div>
            {evidenceRows.map((row) => (
              <dl className="product-evidence-row" key={row.id}>
                <div><dt>{row.label}</dt><dd>{row.values[0]}</dd></div>
                <div><dt>Compared with</dt><dd>{row.values[1]}</dd></div>
                <div><dt>Result</dt><dd>{row.result}</dd></div>
              </dl>
            ))}
          </section>
          <section className="product-workbench__column product-workbench__disposition" aria-labelledby="disposition-preview-title">
            <div className="product-workbench__label"><span>03</span><h3 id="disposition-preview-title">Disposition</h3></div>
            <p className="mono-label">RELEASE STATE / WITHHELD</p>
            <h4>Human review</h4>
            <p>A material location contradiction remains unresolved. No candidate classification leaves the evidence boundary.</p>
            <ThreadLink variant="text" motion="quiet" arrow="external" bridge data-threadline-cta href="/demo?demo=guided">Inspect the complete case</ThreadLink>
          </section>
        </div>
      </section>

      <section className={`story-scene story-safety ${activeScene === 8 ? "is-active" : ""}`} data-story-scene="8" id="safety" aria-labelledby="safety-title">
        <div className="story-safety__content">
          <p className="mono-label">05 / DETERMINISTIC SAFETY GATE</p>
          <h2 className="editorial-title" id="safety-title">Not enough evidence<br />is still an answer.</h2>
          <div className="safety-rule" aria-hidden="true" />
          <dl className="safety-findings">
            <div><dt>Source span integrity</dt><dd>Verified</dd></div>
            <div><dt>Date of birth</dt><dd>Soft conflict</dd></div>
            <div><dt>Shared contact</dt><dd>Insufficient independent evidence</dd></div>
            <div><dt>Location</dt><dd>Material contradiction retained</dd></div>
            <div className="safety-findings__decision"><dt>Disposition</dt><dd>Human review</dd></div>
          </dl>
        </div>
      </section>

      <section className={`story-scene story-gap ${activeScene === 9 ? "is-active" : ""}`} data-story-scene="9" aria-labelledby="gap-title">
        <p className="mono-label">06 / TIMELINE INTEGRITY</p>
        <div className="missing-interval" aria-label="A verified timeline with a 34-hour undocumented interval">
          <span className="missing-interval__line" />
          <span className="missing-interval__empty"><strong>NO VERIFIED RECORD</strong><small>13 JUN 08:15 — 14 JUN 17:55</small></span>
          <span className="missing-interval__line" />
        </div>
        <h2 className="editorial-title" id="gap-title">We do not fill<br />what we cannot prove.</h2>
      </section>

      <section className={`story-scene story-audit ${activeScene === 10 ? "is-active" : ""}`} data-story-scene="10" id="audit" aria-labelledby="audit-title">
        <header className="story-section-heading">
          <p className="mono-label">07 / AUDIT</p>
          <h2 className="editorial-title" id="audit-title">Every transformation<br />leaves a trace.</h2>
        </header>
        <div className="typeset-audit-shell">
          <span className="typeset-audit__current" aria-hidden="true" />
          <ol className="typeset-audit">
            {auditEvents.map(([time, action, detail]) => (
              <li key={time}>
                <time>{time}</time>
                <div><strong>{action}</strong><span>{detail}</span></div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className={`story-scene story-final ${activeScene === 11 ? "is-active" : ""}`} data-story-scene="11" aria-labelledby="final-title">
        <div className="story-final__broken-thread" aria-hidden="true"><span /><i /><span /></div>
        <p className="mono-label">THREADLINE / EVIDENCE BEFORE CONCLUSION</p>
        <h2 className="editorial-title" id="final-title">Some connections<br />should not be made.</h2>
        <p>THREADLINE preserves the evidence<br />and the uncertainty around it.</p>
        <div className="story-final__actions">
          <ThreadLink variant="bare" motion="signature" arrow="forward" bridge magnetic className="editorial-button" data-threadline-cta href="/demo?demo=guided">Run the evidence challenge<span className="sr-only">Trace a Synthetic Case</span></ThreadLink>
          <ThreadLink variant="text" arrow="external" bridge href="/workspace">Explore the technical workspace</ThreadLink>
        </div>
      </section>
    </div>
  );
}
