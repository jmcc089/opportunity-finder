import { useEffect, useState } from 'react';

// Messages mirror the real pipeline stages (scraping → Python filter →
// Stage 1 DeepSeek → Stage 2 DeepSeek). Honest and concrete: they describe
// what actually happens, no inflated language. This is a "fake sequential"
// loader: messages rotate on a timer (~2.2s), not on real backend events.
const MESSAGES = [
  'Gathering events from sources…',
  'Filtering by city, date, and fit…',
  'Evaluating candidate events…',
  'Refining the best results for you…',
];

const STEP_MS = 2200;

export function LoadingScreen() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    // Advance through the messages and stop on the last one (no loop): if the
    // pipeline takes longer than expected, it stays on "Refining…" instead of
    // jumping back to "Gathering…", which would look incoherent.
    const id = setInterval(() => {
      setIndex((prev) => Math.min(prev + 1, MESSAGES.length - 1));
    }, STEP_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="bg-card rounded-[14px] border border-sage-line shadow-md p-12 text-center">
      <div className="inline-block w-10 h-10 border-4 border-sage-line border-t-sage rounded-full animate-spin mb-4" />
      <p className="text-ink font-semibold text-base mb-1">Finding opportunities…</p>
      <p className="text-ink-soft text-sm transition-opacity duration-300">
        {MESSAGES[index]}
      </p>
    </div>
  );
}
