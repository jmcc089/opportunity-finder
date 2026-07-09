import { useState } from 'react';

export interface SearchQuery {
  category: string;
  city: string;
  date_from: string;
  date_to: string;
  permits: string[];
}

const CATEGORY_OPTIONS = [
  { value: 'hot_food', label: 'Hot Food' },
  { value: 'drinks_desserts', label: 'Drinks & Desserts' },
  { value: 'souvenirs_merch', label: 'Souvenirs & Merch' },
];

const CITY_OPTIONS = [
  'Los Angeles', 'San Francisco', 'San Diego', 'Sacramento',
  'San Jose', 'Oakland', 'Fresno', 'Long Beach', 'Bakersfield', 'Anaheim',
];

const PERMIT_OPTIONS: Record<string, string[]> = {
  hot_food: ['MFF', "Seller's Permit", 'Food Handler Card', 'Commissary'],
  drinks_desserts: ['CMFO', 'CFO', "Seller's Permit"],
  souvenirs_merch: ["Seller's Permit", 'Business License', 'Insurance'],
};

interface SearchFormProps {
  onSearch: (query: SearchQuery) => void;
  loading: boolean;
}

export function SearchForm({ onSearch, loading }: SearchFormProps) {
  const [category, setCategory] = useState('hot_food');
  const [city, setCity] = useState('Los Angeles');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [permits, setPermits] = useState<string[]>([]);

  const availablePermits = PERMIT_OPTIONS[category] || [];

  function togglePermit(permit: string) {
    setPermits((prev) =>
      prev.includes(permit) ? prev.filter((p) => p !== permit) : [...prev, permit]
    );
  }

  function handleCategoryChange(val: string) {
    setCategory(val);
    setPermits([]);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch({ category, city, date_from: dateFrom, date_to: dateTo, permits });
  }

  const inputClass =
    'w-full rounded-[8px] border border-sage-line bg-page px-3 py-2 text-sm text-ink placeholder-muted focus:outline-none focus:ring-2 focus:ring-sage-mid transition';

  return (
    <div className="bg-card rounded-[14px] border border-[0.5px] border-sage-line shadow-md p-8 max-w-xl w-full mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl text-ink mb-1 uppercase tracking-wide" style={{ fontFamily: "'Bebas Neue', sans-serif" }}>Find Your Next Event</h1>
        <p className="text-ink-soft text-sm">Discover which California events are worth attending for your mobile business.</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Category */}
        <div>
          <label className="block text-xs font-semibold text-ink-soft uppercase tracking-wider mb-1.5">Business Category</label>
          <select
            value={category}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className={inputClass}
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* City */}
        <div>
          <label className="block text-xs font-semibold text-ink-soft uppercase tracking-wider mb-1.5">City / Region</label>
          <select
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className={inputClass}
          >
            {CITY_OPTIONS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-ink-soft uppercase tracking-wider mb-1.5">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className={inputClass}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-soft uppercase tracking-wider mb-1.5">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className={inputClass}
              required
            />
          </div>
        </div>

        {/* Permits checklist */}
        <div>
          <label className="block text-xs font-semibold text-ink-soft uppercase tracking-wider mb-2">Permits You Have</label>
          <div className="flex flex-wrap gap-2">
            {availablePermits.map((permit) => {
              const checked = permits.includes(permit);
              return (
                <button
                  key={permit}
                  type="button"
                  onClick={() => togglePermit(permit)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition ${
                    checked
                      ? 'bg-sage text-white border-sage'
                      : 'bg-sage-bg text-ink-soft border-sage-line hover:border-sage-mid'
                  }`}
                >
                  {permit}
                </button>
              );
            })}
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="bg-sage text-white font-semibold py-2.5 px-6 rounded-[8px] hover:bg-sage-mid disabled:opacity-60 transition mt-1"
        >
          {loading ? 'Searching…' : 'Search Opportunities'}
        </button>
        <p className="text-xs text-muted text-center -mt-2">
          Analysis is generated live and may take a few seconds.
        </p>
      </form>
    </div>
  );
}
