import { useState } from 'react';
import { SearchForm } from './components/SearchForm';
import type { SearchQuery } from './components/SearchForm';
import { ResultCard } from './components/ResultCard';
import type { EventResult } from './components/ResultCard';
import { LoadingScreen } from './components/LoadingScreen';

type AppState = 'form' | 'loading' | 'results' | 'empty';

// The Python backend (/api/search) and the UI use different field names and
// shapes. This adapts the real API response into the EventResult shape the
// cards render. The mock fixture is already in EventResult shape, so it skips
// this path.
interface RawApiResult {
  name?: string;
  city?: string;
  start_date?: string | null;
  end_date?: string | null;
  stand_cost?: number | null;
  tag_indoor?: boolean | null;
  tag_outdoor?: boolean | null;
  deadline_date?: string | null;
  detail_url?: string | null;
  source?: string;
  final_score?: number | null;
  explanation?: string;
  estimated_attendance?: string | number | null;
  likely_permits?: string[];
  recommendation?: string;
  estimated_fields?: string[];
}

const RECOMMENDATION_MAP: Record<string, EventResult['recommendation']> = {
  worth_it: 'worth it',
  with_reservations: 'with reservations',
  better_not: 'better not',
};

// estimated_fields uses backend field names; remap the ones the UI checks by key.
const ESTIMATED_FIELD_MAP: Record<string, string> = {
  stand_cost: 'booth_cost',
  deadline_date: 'application_deadline',
  tag_indoor: 'setting',
  tag_outdoor: 'setting',
};

const SOURCE_LABELS: Record<string, string> = {
  thecraftmap: 'TheCraftMap',
  festivalguides: 'FestivalGuides',
};

function deriveSetting(raw: RawApiResult): string | null {
  if (raw.tag_outdoor) return 'outdoor';
  if (raw.tag_indoor) return 'indoor';
  return null;
}

function adaptResult(raw: RawApiResult, index: number): EventResult {
  const estimated = (raw.estimated_fields ?? []).map((f) => ESTIMATED_FIELD_MAP[f] ?? f);
  return {
    rank: index + 1,
    score: raw.final_score ?? 0,
    event_name: raw.name ?? 'Untitled event',
    city: raw.city ?? '',
    date_start: raw.start_date ?? '',
    date_end: raw.end_date ?? '',
    recommendation: RECOMMENDATION_MAP[raw.recommendation ?? ''] ?? 'with reservations',
    explanation: raw.explanation ?? '',
    booth_cost: raw.stand_cost ?? null,
    estimated_attendance: raw.estimated_attendance ?? null,
    application_deadline: raw.deadline_date ?? null,
    setting: deriveSetting(raw),
    likely_permits: raw.likely_permits ?? [],
    source_name: SOURCE_LABELS[raw.source ?? ''] ?? raw.source ?? '',
    source_url: raw.detail_url ?? '',
    estimated_fields: estimated,
  };
}

async function (query: SearchQuery): Promise<{ results: EventResult[]; warnings: string[] }> {

  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(query),
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();
  const results = (data.results ?? []).map(adaptResult);
  return { results, warnings: data.meta?.warnings ?? [] };
}

export default function App() {
  const [state, setState] = useState<AppState>('form');
  const [results, setResults] = useState<EventResult[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(query: SearchQuery) {
    setState('loading');
    setError(null);
    try {
      const { results: res, warnings: w } = await fetchResults(query);
      res.sort((a, b) => b.score - a.score); // highest score first
      setResults(res);
      setWarnings(w);
      setState(res.length === 0 ? 'empty' : 'results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setState('form');
    }
  }

  function handleReset() {
    setState('form');
    setResults([]);
    setWarnings([]);
    setError(null);
  }

  return (
    <div className="min-h-screen bg-page py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Logo / brand */}
        <div className="text-center mb-8">
          <h1 className="text-6xl text-ink tracking-wide" style={{ fontFamily: "'Bebas Neue', sans-serif" }}>Opportunity Finder</h1>
          <p className="text-ink-soft text-sm mt-2">California events for mobile businesses</p>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-[10px]">
            {error}
          </div>
        )}

        {state === 'form' && (
          <SearchForm onSearch={handleSearch} loading={false} />
        )}

        {state === 'loading' && <LoadingScreen />}

        {state === 'results' && (
          <>
            {warnings.length > 0 && (
              <div className="mb-4 bg-amber-50 border border-amber-200 text-amber-700 text-xs px-4 py-2.5 rounded-[10px]">
                {warnings.join(' ')}
              </div>
            )}
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-ink font-semibold text-lg">{results.length} Events Found</h2>
              <button onClick={handleReset} className="text-sage-mid text-sm hover:underline">
                &larr; New search
              </button>
            </div>
            <div className="flex flex-col gap-4">
              {results.map((r) => (
                <ResultCard key={r.rank} result={r} />
              ))}
            </div>
            {/* Legend */}
            <div className="mt-6 bg-card rounded-[12px] border border-sage-line px-5 py-4 flex flex-wrap gap-6 text-sm">
              <div className="flex items-center gap-1.5">
                <span className="text-sage-mid font-bold">&#10003;</span>
                <span className="text-ink-soft"><strong className="text-ink">real</strong> &mdash; sourced directly from event listing</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-muted">&#10086;</span>
                <span className="text-ink-soft"><strong className="text-ink">estimate</strong> &mdash; AI-generated from available context</span>
              </div>
            </div>
          </>
        )}

        {state === 'empty' && (
          <div className="bg-card rounded-[14px] border border-sage-line shadow-md p-10 text-center">
            <div className="text-4xl mb-4">🔍</div>
            <h2 className="text-ink font-semibold text-lg mb-2">No matching events found</h2>
            <p className="text-ink-soft text-sm mb-4">
              No events matched those filters. Try widening your date range or selecting a different city.
            </p>
            <button onClick={handleReset} className="bg-sage text-white text-sm font-semibold px-5 py-2 rounded-[8px] hover:bg-sage-mid transition">
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
