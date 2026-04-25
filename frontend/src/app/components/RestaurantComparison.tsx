import { useEffect, useState } from 'react';
import { apiFetch } from '../api';
import { Footer } from './Footer';
import { useAppContext } from '../AppContext';
import { NOMZ_THEME } from '../constants';

const T = NOMZ_THEME;
const sans = T.fontSans;
const redRgb = '212, 43, 43';

interface RestaurantData {
  id: number;
  name: string;
  cuisine: string;
  cuisine_tags: string[];
  neighborhood: string;
  address: string;
  description: string;
  phone: string;
  price_range: string;
  hours_open: string;
  hours_close: string;
  is_flagged: boolean;
  is_owner_flagged: boolean;
  owner_id: number | null;
  messaging_enabled: boolean;
  composite_score: number | null;
  grade: string;
  reviews: any[];
}

export function RestaurantComparison({
  onBack,
  onSelectRestaurant,
}: {
  onBack: () => void;
  onSelectRestaurant: (id: number) => void;
}) {
  const { selectedRestaurants, clearSelectedRestaurants } = useAppContext();
  const [restaurants, setRestaurants] = useState<RestaurantData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const promises = selectedRestaurants.map(id =>
          apiFetch(`/api/restaurants/${id}/`).then(r => r.json())
        );
        const results = await Promise.all(promises);
        if (!cancelled) {
          setRestaurants(results);
        }
      } catch {
        if (!cancelled) {
          setError('Failed to load restaurant data.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [selectedRestaurants]);

  if (loading) {
    return (
      <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: T.paper }}>
        <div className="flex-1 flex items-center justify-center">
          <p style={{ color: T.mid, fontFamily: sans }}>Loading comparison...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: T.paper }}>
        <div className="flex-1 flex items-center justify-center">
          <p style={{ color: T.red, fontFamily: sans }}>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: T.paper }}>
      <nav className="w-full px-8 py-4 flex items-center justify-between shrink-0 border-b-2" style={{ borderColor: T.ink }}>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onBack}
            className="text-xl p-2 transition-all"
            title="Back"
            style={{ border: 'none', background: 'transparent', color: T.red, cursor: 'pointer' }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = `rgba(${redRgb}, 0.1)`; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            ←
          </button>
          <h1 className="text-2xl font-black" style={{ fontFamily: T.fontSerif, color: T.ink }}>
            Compare Restaurants
          </h1>
        </div>
        <button
          type="button"
          onClick={() => {
            clearSelectedRestaurants();
            onBack();
          }}
          className="px-4 py-2 text-sm uppercase tracking-widest font-bold"
          style={{ backgroundColor: T.red, color: T.paper, fontFamily: sans, border: 'none', cursor: 'pointer' }}
        >
          Clear Selection
        </button>
      </nav>

      <main className="flex-1 px-8 py-8 overflow-x-auto">
        <div className="min-w-max">
          <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)` }}>
            <div className="font-bold text-xs uppercase tracking-widest" style={{ color: T.mid, fontFamily: sans }}>
              Attribute
            </div>
            {restaurants.map(restaurant => (
              <div key={restaurant.id} className="text-center">
                <button
                  type="button"
                  onClick={() => onSelectRestaurant(restaurant.id)}
                  className="block w-full p-3 transition-all text-left"
                  style={{
                    backgroundColor: T.paper,
                    border: `1px solid rgba(${redRgb}, 0.2)`,
                    fontFamily: sans,
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = `rgba(${redRgb}, 0.08)`;
                    e.currentTarget.style.borderColor = `rgba(${redRgb}, 0.45)`;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = T.paper;
                    e.currentTarget.style.borderColor = `rgba(${redRgb}, 0.2)`;
                  }}
                >
                  <h3 className="font-bold text-sm mb-1" style={{ color: T.ink, fontFamily: T.fontSerif }}>
                    {restaurant.name}
                  </h3>
                  <p className="text-xs uppercase tracking-wide" style={{ color: T.mid, fontFamily: sans }}>
                    {restaurant.cuisine}
                  </p>
                </button>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="grid gap-4 py-3" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)` }}>
              <div className="font-medium text-sm" style={{ color: T.mid, fontFamily: sans }}>
                Cuisine
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm" style={{ color: T.ink, fontFamily: sans }}>
                  {restaurant.cuisine || 'N/A'}
                </div>
              ))}
            </div>

            <div className="grid gap-4 py-3 rounded-sm" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)`, border: '1px solid rgba(28,18,9,0.12)', background: 'rgba(200,169,110,0.06)' }}>
              <div className="font-medium text-sm pl-3" style={{ color: T.mid, fontFamily: sans }}>
                Price Range
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm" style={{ color: T.ink, fontFamily: sans }}>
                  {restaurant.price_range || 'N/A'}
                </div>
              ))}
            </div>

            <div className="grid gap-4 py-3" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)` }}>
              <div className="font-medium text-sm" style={{ color: T.mid, fontFamily: sans }}>
                Hours
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm" style={{ color: T.ink, fontFamily: sans }}>
                  {restaurant.hours_open && restaurant.hours_close
                    ? `${restaurant.hours_open} - ${restaurant.hours_close}`
                    : 'N/A'
                  }
                </div>
              ))}
            </div>

            <div className="grid gap-4 py-3 rounded-sm" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)`, border: '1px solid rgba(28,18,9,0.12)', background: 'rgba(200,169,110,0.06)' }}>
              <div className="font-medium text-sm pl-3" style={{ color: T.mid, fontFamily: sans }}>
                Composite Score
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm font-bold" style={{ color: T.red, fontFamily: sans }}>
                  {restaurant.composite_score != null ? restaurant.composite_score.toFixed(1) : 'N/A'}
                </div>
              ))}
            </div>

            <div className="grid gap-4 py-3" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)` }}>
              <div className="font-medium text-sm" style={{ color: T.mid, fontFamily: sans }}>
                Health Grade
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm" style={{ color: T.ink, fontFamily: sans }}>
                  {restaurant.grade || 'N/A'}
                </div>
              ))}
            </div>

            <div className="grid gap-4 py-3 rounded-sm" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)`, border: '1px solid rgba(28,18,9,0.12)', background: 'rgba(200,169,110,0.06)' }}>
              <div className="font-medium text-sm pl-3" style={{ color: T.mid, fontFamily: sans }}>
                Neighborhood
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm" style={{ color: T.ink, fontFamily: sans }}>
                  {restaurant.neighborhood || 'N/A'}
                </div>
              ))}
            </div>

            <div className="grid gap-4 py-3" style={{ gridTemplateColumns: `200px repeat(${restaurants.length}, 1fr)` }}>
              <div className="font-medium text-sm" style={{ color: T.mid, fontFamily: sans }}>
                Address
              </div>
              {restaurants.map(restaurant => (
                <div key={restaurant.id} className="text-center text-sm" style={{ color: T.ink, fontFamily: sans }}>
                  {restaurant.address || 'N/A'}
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
