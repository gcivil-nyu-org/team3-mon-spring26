import { useEffect, useState } from 'react';
import { apiFetch, mapSortByToApi } from '../api';
import { Footer } from './Footer';

export type SearchResultRow = {
  id: number;
  name: string;
  description: string;
  cuisine: string;
  neighborhood: string;
  composite_score: number | null;
  price_label: string;
  rating_score: number | null;
  is_flagged: boolean;
};

type SearchPayload = {
  results: SearchResultRow[];
  query: string;
  neighborhood: string;
  sort_by: string;
  all_neighborhoods: string[];
};

export function SearchResults({
  initialQuery,
  initialNeighborhood = '',
  onBack,
  onSelectRestaurant,
  onNavigateMap,
  onNavigateMessages,
  onNavigateProfile,
  onLogout,
  username,
}: {
  initialQuery: string;
  initialNeighborhood?: string;
  onBack: () => void;
  onSelectRestaurant: (id: number) => void;
  onNavigateMap: () => void;
  onNavigateMessages: () => void;
  onNavigateProfile: () => void;
  onLogout: () => void;
  username: string;
}) {
  const [q, setQ] = useState(initialQuery);
  const [committedQuery, setCommittedQuery] = useState(initialQuery);
  const [neighborhood, setNeighborhood] = useState(initialNeighborhood);
  const [sortUi, setSortUi] = useState('composite-high-low');
  const [data, setData] = useState<SearchPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setQ(initialQuery);
    setCommittedQuery(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (committedQuery.trim()) params.set('q', committedQuery.trim());
      if (neighborhood) params.set('neighborhood', neighborhood);
      params.set('sort_by', mapSortByToApi(sortUi));
      try {
        const r = await apiFetch(`/api/search/?${params.toString()}`);
        if (cancelled) return;
        if (!r.ok) {
          setError('Could not load search results.');
          setData(null);
          return;
        }
        const json = (await r.json()) as SearchPayload;
        setData(json);
      } catch {
        if (!cancelled) {
          setError('Network error.');
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [committedQuery, neighborhood, sortUi]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCommittedQuery(q.trim());
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      <nav className="w-full px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onBack}
            className="text-xl p-2 rounded-lg transition-all"
            title="Back"
            style={{ border: 'none', background: 'transparent', color: '#E06E7F', cursor: 'pointer' }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            ←
          </button>
          <h1 className="text-2xl" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>
            nomz
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <button type="button" onClick={onNavigateMap} title="Map" className="text-xl transition-all p-2 rounded-lg" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#E06E7F' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
            🗺️
          </button>
          <button type="button" onClick={onNavigateMessages} title="Messages" className="text-xl transition-all p-2 rounded-lg" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#E06E7F' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
            💬
          </button>
          <button type="button" onClick={onNavigateProfile} title="Profile" className="text-xl transition-all p-2 rounded-lg" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#E06E7F' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
            👤
          </button>
          <button type="button" onClick={onLogout} title="Logout" className="text-xl transition-all p-2 rounded-lg" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#E06E7F' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
            →
          </button>
        </div>
      </nav>

      <main className="flex-1 px-8 py-8 max-w-5xl mx-auto w-full">
        <h2 className="text-2xl mb-6" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>
          Search restaurants
        </h2>

        <form onSubmit={handleSubmit} className="mb-8 space-y-4">
          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Name, cuisine, description…"
              className="flex-1 px-4 py-3 border-2 rounded-lg text-sm"
              style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
            />
            <select
              value={neighborhood}
              onChange={(e) => setNeighborhood(e.target.value)}
              className="px-4 py-3 border-2 rounded-lg text-sm md:min-w-[200px]"
              style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
            >
              <option value="">All neighborhoods</option>
              {(data?.all_neighborhoods ?? []).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <select
              value={sortUi}
              onChange={(e) => setSortUi(e.target.value)}
              className="px-4 py-3 border-2 rounded-lg text-sm md:min-w-[200px]"
              style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif' }}
            >
              <option value="composite-high-low">Score (high → low)</option>
              <option value="composite-low-high">Score (low → high)</option>
              <option value="name-a-z">Name A–Z</option>
              <option value="name-z-a">Name Z–A</option>
            </select>
            <button
              type="submit"
              className="px-6 py-3 rounded-lg text-sm text-white"
              title="Search restaurants"
              style={{ backgroundColor: '#E06E7F', fontFamily: 'Montserrat, sans-serif', border: 'none', cursor: 'pointer' }}
            >
              Search
            </button>
          </div>
        </form>

        {error && (
          <p className="text-sm mb-4" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>
            {error}
          </p>
        )}
        {loading && (
          <p className="text-sm" style={{ color: '#666', fontFamily: 'Montserrat, sans-serif' }}>
            Loading…
          </p>
        )}

        {!loading && data && (
          <p className="text-sm mb-4" style={{ color: '#666', fontFamily: 'Montserrat, sans-serif' }}>
            {data.results.length} result{data.results.length === 1 ? '' : 's'}
            {data.query ? ` for “${data.query}”` : ''}
            {data.neighborhood ? ` in ${data.neighborhood}` : ''}
          </p>
        )}

        {!loading && data && data.results.length === 0 && (
          <p className="text-sm" style={{ color: '#666', fontFamily: 'Montserrat, sans-serif' }}>
            No restaurants match your filters. Try a different search or neighborhood.
          </p>
        )}

        <ul className="space-y-4">
          {(data?.results ?? []).map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => onSelectRestaurant(row.id)}
                className="w-full text-left p-5 rounded-lg transition-all"
                title={`View ${row.name}`}
                style={{
                  backgroundColor: 'white',
                  border: '2px solid rgba(224, 110, 127, 0.15)',
                  fontFamily: 'Montserrat, sans-serif',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.3)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'white'; e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.15)'; }}
              >
                <div className="flex justify-between gap-4">
                  <div>
                    <h3 className="text-lg mb-1" style={{ color: '#333' }}>
                      {row.name}
                      {row.is_flagged && (
                        <span className="ml-2 text-xs" style={{ color: '#b45309' }}>
                          flagged
                        </span>
                      )}
                    </h3>
                    <p className="text-xs mb-2" style={{ color: '#666' }}>
                      {row.cuisine} • {row.price_label}
                      {row.neighborhood ? ` • ${row.neighborhood}` : ''}
                    </p>
                    {row.description && (
                      <p className="text-xs line-clamp-2" style={{ color: '#888' }}>
                        {row.description}
                      </p>
                    )}
                  </div>
                  <div className="text-right text-xs shrink-0" style={{ color: '#888' }}>
                    {row.composite_score != null && <div>Score {Number(row.composite_score).toFixed(1)}</div>}
                    {row.rating_score != null && <div>Rating {Number(row.rating_score).toFixed(1)}</div>}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </main>
      <Footer />
    </div>
  );
}
