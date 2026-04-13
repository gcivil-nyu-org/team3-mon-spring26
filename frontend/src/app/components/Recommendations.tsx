import { useEffect, useState } from 'react';
import { apiFetch } from '../api';
import { Footer } from './Footer';

type RecRow = {
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

export function Recommendations({
  onBack,
  onSelectRestaurant,
  onNavigateMap,
  onNavigateMessages,
  onNavigateProfile,
  onOpenPreferences,
  onLogout,
  username,
}: {
  onBack: () => void;
  onSelectRestaurant: (id: number) => void;
  onNavigateMap: () => void;
  onNavigateMessages: () => void;
  onNavigateProfile: () => void;
  onOpenPreferences?: () => void;
  onLogout: () => void;
  username: string;
}) {
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [requiresPreferences, setRequiresPreferences] = useState(false);
  const [restaurants, setRestaurants] = useState<RecRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await apiFetch('/api/recommendations/');
        if (!r.ok) {
          if (!cancelled) setError('Could not load recommendations.');
          return;
        }
        const d = await r.json();
        if (cancelled) return;
        setRequiresPreferences(Boolean(d.requires_preferences));
        setMessage(typeof d.message === 'string' ? d.message : '');
        setRestaurants(Array.isArray(d.restaurants) ? d.restaurants : []);
      } catch {
        if (!cancelled) setError('Network error.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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
        <h2 className="text-2xl mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>
          Recommendations for you
        </h2>
        <p className="text-sm mb-8" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
          Based on your saved dining preferences (same logic as the full recommendations page on the server).
        </p>

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

        {!loading && requiresPreferences && (
          <div
            className="p-6 rounded-lg mb-6"
            style={{ backgroundColor: 'rgba(224, 110, 127, 0.08)', border: '2px solid rgba(224, 110, 127, 0.2)' }}
          >
            <p className="text-sm mb-4" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>
              Please set your preferences first so we can suggest restaurants for you.
            </p>
            {onOpenPreferences && (
              <button
                type="button"
                onClick={onOpenPreferences}
                className="px-5 py-2 rounded-lg text-sm text-white"
                title="Open dining preferences"
                style={{ backgroundColor: '#E06E7F', border: 'none', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                Open preferences
              </button>
            )}
          </div>
        )}

        {!loading && !requiresPreferences && message && (
          <p className="text-sm mb-6" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
            {message}
          </p>
        )}

        <ul className="space-y-4">
          {restaurants.map((row) => (
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
                <h3 className="text-lg mb-1" style={{ color: '#333' }}>
                  {row.name}
                </h3>
                <p className="text-xs mb-2" style={{ color: '#666' }}>
                  {row.cuisine} • {row.price_label}
                  {row.neighborhood ? ` • ${row.neighborhood}` : ''}
                </p>
                {row.description && (
                  <p className="text-xs line-clamp-3" style={{ color: '#888' }}>
                    {row.description}
                  </p>
                )}
              </button>
            </li>
          ))}
        </ul>
      </main>
      <Footer />
    </div>
  );
}
