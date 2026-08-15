import type { BenchmarkMetric, BenchmarkSystemResult } from "@/types";

const colors = ["#8f887d", "#9a4d36", "#b79552", "#87947b"];

export function BenchmarkChart({
  metric,
  systems,
  summary,
}: {
  metric: BenchmarkMetric;
  systems: BenchmarkSystemResult[];
  summary: string;
}) {
  const max = metric.unit === "percent" ? 100 : Math.max(...systems.map((system) => system.values[metric.metric_id] ?? 0));
  const axisMax = metric.unit === "percent" ? 100 : Math.ceil(max / 1000) * 1000;
  const unitLabel = metric.unit === "percent" ? "%" : metric.unit === "milliseconds" ? "ms" : "calls";

  return (
    <figure className="benchmark-chart" aria-labelledby={`chart-${metric.metric_id}-title`}>
      <div className="benchmark-chart__heading">
        <div><span>Illustrative values</span><h3 id={`chart-${metric.metric_id}-title`}>{metric.label}</h3></div>
        <span>{metric.higher_is_better ? "Higher is better" : "Lower is better"}</span>
      </div>
      <svg viewBox="0 0 680 260" role="img" aria-label={`${metric.label} comparison`} aria-describedby={`chart-${metric.metric_id}-desc`}>
        <desc id={`chart-${metric.metric_id}-desc`}>{summary} Values are illustrative and are not measured results.</desc>
        <line className="chart-axis" x1="145" x2="640" y1="212" y2="212" />
        {[0, 0.5, 1].map((tick) => (
          <g key={tick}>
            <line className="chart-grid" x1={145 + tick * 495} x2={145 + tick * 495} y1="20" y2="212" />
            <text className="chart-tick" x={145 + tick * 495} y="235" textAnchor={tick === 0 ? "start" : tick === 1 ? "end" : "middle"}>{Math.round(axisMax * tick)}{unitLabel === "%" ? "%" : ""}</text>
          </g>
        ))}
        {systems.map((system, index) => {
          const value = system.values[metric.metric_id] ?? 0;
          const width = axisMax === 0 ? 0 : (value / axisMax) * 495;
          const y = 28 + index * 45;
          return (
            <g key={system.system_id}>
              <text className="chart-label" x="136" y={y + 14} textAnchor="end">{system.system_name}</text>
              <rect className="chart-track" x="145" y={y} width="495" height="20" rx="3" />
              <rect x="145" y={y} width={Math.max(2, width)} height="20" rx="3" fill={colors[index]} />
              <text className="chart-value" x={Math.min(620, 154 + width)} y={y + 14}>{value}{unitLabel === "%" ? "%" : ` ${unitLabel}`}</text>
            </g>
          );
        })}
        <text className="chart-axis-label" x="392" y="256" textAnchor="middle">{metric.label} ({unitLabel}) · axis starts at zero</text>
      </svg>
      <ul className="chart-legend" aria-label="Chart legend">
        {systems.map((system, index) => <li key={system.system_id}><span style={{ background: colors[index] }} aria-hidden="true" />{system.system_name}</li>)}
      </ul>
      <figcaption><strong>Text summary</strong><p>{summary}</p><span>Illustrative interface — awaiting measured benchmark output</span></figcaption>
    </figure>
  );
}
