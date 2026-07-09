import { FieldRow } from './FieldRow';

export interface EventResult {
  rank: number;
  score: number;
  event_name: string;
  city: string;
  date_start: string;
  date_end: string;
  recommendation: 'worth it' | 'with reservations' | 'better not';
  explanation: string;
  booth_cost: number;
  estimated_attendance: number;
  application_deadline: string;
  setting: string;
  likely_permits: string[];
  source_name: string;
  source_url: string;
  estimated_fields: string[];
}

const recommendationStyles: Record<string, string> = {
  'worth it': 'bg-sage-bg text-sage font-semibold',
  'with reservations': 'bg-amber-50 text-amber-700 font-semibold',
  'better not': 'bg-red-50 text-red-600 font-semibold',
};

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function ResultCard({ result }: { result: EventResult }) {
  const { estimated_fields } = result;
  const isExplanationEstimate = estimated_fields.includes('explanation');

  return (
    <div className="bg-card rounded-[14px] border border-[0.5px] border-sage-line shadow-sm p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start gap-4">
        {/* Score tile */}
        <div className="bg-sage-bg rounded-[10px] px-3 py-2 text-center min-w-[56px] flex-shrink-0">
          <div className="text-2xl font-bold text-sage">{result.score}</div>
          <div className="text-xs text-ink-soft leading-tight">/ 100</div>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-ink font-semibold text-base leading-snug">{result.event_name}</h3>
          <div className="text-ink-soft text-sm mt-0.5">{result.city} · {formatDate(result.date_start)} – {formatDate(result.date_end)}</div>
        </div>
        {/* Recommendation pill */}
        <span className={`text-xs px-2.5 py-1 rounded-full capitalize flex-shrink-0 ${recommendationStyles[result.recommendation]}`}>
          {result.recommendation}
        </span>
      </div>

      {/* AI Explanation */}
      <div className="bg-page rounded-[10px] px-4 py-3">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span className="text-muted text-xs">✦</span>
          <span className="text-muted text-xs font-medium">AI summary{isExplanationEstimate ? ' · estimate' : ''}</span>
        </div>
        <p className="text-ink-soft text-sm leading-relaxed">{result.explanation}</p>
      </div>

      {/* Data grid */}
      <div className="bg-page rounded-[10px] px-4 py-2">
        <FieldRow label="Booth cost" value={`$${result.booth_cost}`} fieldKey="booth_cost" estimatedFields={estimated_fields} />
        <FieldRow label="Est. attendance" value={result.estimated_attendance.toLocaleString()} fieldKey="estimated_attendance" estimatedFields={estimated_fields} />
        <FieldRow label="Application deadline" value={formatDate(result.application_deadline)} fieldKey="application_deadline" estimatedFields={estimated_fields} />
        <FieldRow label="Setting" value={result.setting} fieldKey="setting" estimatedFields={estimated_fields} />
      </div>

      {/* Permits */}
      <div>
        <div className="text-xs font-medium text-ink-soft mb-2">Likely permits needed</div>
        <div className="flex flex-wrap gap-1.5">
          {result.likely_permits.slice(0, 3).map((permit) => (
            <span key={permit} className="bg-sage-bg text-ink text-xs px-2.5 py-1 rounded-full border border-sage-line">
              {permit}
            </span>
          ))}
        </div>
        <p className="text-xs text-muted mt-2 leading-relaxed">
          Permit estimates are AI-generated and not legal advice. Verify with the county environmental health department.
        </p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-sage-line">
        <span className="text-xs text-muted">{result.source_name}</span>
        <a
          href={result.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-sage-mid hover:underline font-medium"
        >
          View event →
        </a>
      </div>
    </div>
  );
}
