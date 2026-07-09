import { useState } from 'react';
import { SearchForm } from './components/SearchForm';
import type { SearchQuery } from './components/SearchForm';
import { ResultCard } from './components/ResultCard';
import type { EventResult } from './components/ResultCard';
import sampleData from '../../fixtures/sample_api_response.json';

type AppState = 'form' | 'loading' | 'results' | 'empty';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

async function fetchResults(query: SearchQuery): Promise<{ results: EventResult[]; warnings: string[] }> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 800));
    const data = sampleData as { results: EventResult[]; meta: { warnings: string[] } };
    return { results: data.results, warnings: data.meta.warnings };
  }

  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(query),
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();
  return { results: data.results, warnings: data.meta?.warnings ?? [] };
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

        {state === 'loading' && (
          <div className="bg-card rounded-[14px] border border-sage-line shadow-md p-12 text-center">
            <div className="inline-block w-10 h-10 border-4 border-sage-line border-t-sage rounded-full animate-spin mb-4" />
            <p className="text-ink-soft text-sm">Finding the best events for your business...</p>
          </div>
        )}

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
