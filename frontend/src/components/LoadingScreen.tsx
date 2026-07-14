import { useEffect, useState } from 'react';

// Mensajes que espejan las etapas reales del pipeline (scraping → filtro Python →
// Stage 1 DeepSeek → Stage 2 DeepSeek). Honestos y concretos: describen lo que
// realmente pasa, sin lenguaje inflado. Loading "falso secuencial": rotan por
// tiempo (~2.2s), no por eventos reales del backend.
const MESSAGES = [
  'Recopilando eventos de las fuentes…',
  'Filtrando por ciudad, fecha y afinidad…',
  'Evaluando los eventos candidatos…',
  'Afinando los mejores resultados para ti…',
];

const STEP_MS = 2200;

export function LoadingScreen() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    // Avanza por los mensajes y se detiene en el último (no hace loop): si el
    // pipeline tarda más de lo esperado, se queda en "Afinando…" en vez de
    // volver a "Recopilando…", que se vería incoherente.
    const id = setInterval(() => {
      setIndex((prev) => Math.min(prev + 1, MESSAGES.length - 1));
    }, STEP_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="bg-card rounded-[14px] border border-sage-line shadow-md p-12 text-center">
      <div className="inline-block w-10 h-10 border-4 border-sage-line border-t-sage rounded-full animate-spin mb-4" />
      <p className="text-ink font-semibold text-base mb-1">Buscando oportunidades…</p>
      <p className="text-ink-soft text-sm transition-opacity duration-300">
        {MESSAGES[index]}
      </p>
    </div>
  );
}
