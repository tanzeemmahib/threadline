import { StatusPill } from "@/components/status-pill";

const records = [
  {
    id: "FAMILY-018",
    type: "Family report / Arabic",
    fields: [
      ["Name", "يوسف الحسن"],
      ["Age", "14 / exact"],
      ["Last seen", "Al Noor School · 16:30 approx."],
    ],
  },
  {
    id: "SHELTER-204",
    type: "Shelter record / English",
    fields: [
      ["Name", "Yusuf Hasan"],
      ["Age", "15 / estimated"],
      ["Arrival", "North Gate · 19:10"],
    ],
  },
  {
    id: "HOSPITAL-031",
    type: "Hospital intake / French",
    fields: [
      ["Name", "Not recorded"],
      ["Age", "14–16 / estimated"],
      ["Clothing", "Veste bleu foncé"],
    ],
  },
];

export function LandingEvidenceThread() {
  return (
    <figure className="evidence-thread" aria-labelledby="evidence-thread-caption">
      <div className="evidence-thread__topline">
        <span>INCIDENT-NDE-001</span>
        <StatusPill tone="teal">Synthetic data</StatusPill>
      </div>
      <div className="evidence-thread__records">
        {records.map((record, index) => (
          <article className={`evidence-record evidence-record--${index + 1}`} key={record.id}>
            <header>
              <span>{record.id}</span>
              <span>{record.type}</span>
            </header>
            <dl>
              {record.fields.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd lang={label === "Name" && index === 0 ? "ar" : undefined} dir={label === "Name" && index === 0 ? "rtl" : undefined}>{value}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
        <svg className="thread-lines" viewBox="0 0 700 560" role="img" aria-label="Evidence paths connect compatible fields from three source records to one candidate connection.">
          <path className="thread-line thread-line--one" d="M195 89 C340 89 320 180 455 180" />
          <path className="thread-line thread-line--two" d="M195 150 C350 150 310 245 455 245" />
          <path className="thread-line thread-line--three" d="M195 375 C355 375 340 310 455 310" />
          <path className="thread-spine" d="M455 180 L455 350 C455 400 500 410 548 410" />
          <circle cx="195" cy="89" r="4" />
          <circle cx="195" cy="150" r="4" />
          <circle cx="195" cy="375" r="4" />
          <circle cx="455" cy="180" r="4" />
          <circle cx="455" cy="245" r="4" />
          <circle cx="455" cy="310" r="4" />
        </svg>
      </div>
      <figcaption className="evidence-thread__outcome" id="evidence-thread-caption">
        <span className="evidence-thread__index">01</span>
        <div>
          <strong>Candidate connection</strong>
          <span>Human verification required</span>
        </div>
        <span className="evidence-thread__arrow" aria-hidden="true">↗</span>
      </figcaption>
    </figure>
  );
}

