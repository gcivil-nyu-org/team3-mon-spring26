import { useCallback, useEffect, useRef, useState } from "react";
import { Footer } from "./Footer";
import { apiFetch, mapSortByToApi } from "../api";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type MapRestaurantPoint = {
  id: number;
  name: string;
  address: string;
  borough?: string;
  cuisine_tags: string[];
  composite_score: number | null;
  composite_score_label: string;
  latitude: number;
  longitude: number;
  phone?: string;
  grade?: string;
};

export function Map({ 
  onNavigateHome, 
  onNavigateMessages, 
  onNavigateFriendChat,
  onNavigateProfile, 
  onLogout,
  isAdmin = false,
  onSelectRestaurant,
}: { 
  onNavigateHome: () => void;
  onNavigateMessages: () => void;
  onNavigateFriendChat?: () => void;
  onNavigateProfile: () => void;
  onLogout: () => void;
  isAdmin?: boolean;
  onSelectRestaurant?: (id: number) => void;
}) {
  const [search, setSearch] = useState('');
  const [borough, setBorough] = useState('all');
  const [cuisine, setCuisine] = useState('all');
  const [minScore, setMinScore] = useState('');
  const [maxScore, setMaxScore] = useState('');
  const [sortBy, setSortBy] = useState('composite-high-low');
  const [onlyVisibleArea, setOnlyVisibleArea] = useState(false);

  const [results, setResults] = useState<MapRestaurantPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);

  // Initialise Leaflet map once
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const map = L.map(mapContainerRef.current).setView([40.7128, -74.006], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);
    markersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    // Near-me geolocation
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => map.setView([pos.coords.latitude, pos.coords.longitude], 14),
        () => { /* permission denied – keep default NYC view */ },
      );
    }

    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Draw markers when results change
  useEffect(() => {
    const group = markersRef.current;
    if (!group) return;
    group.clearLayers();

    for (const r of results) {
      const score = r.composite_score;
      let color = '#D3D3D3';
      if (score !== null) {
        if (score >= 90) color = '#22c55e';
        else if (score >= 80) color = '#eab308';
        else color = '#ef4444';
      }
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,.3)"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });
      const marker = L.marker([r.latitude, r.longitude], { icon });
      marker.bindPopup(
        `<div style="font-family:Montserrat,sans-serif;font-size:13px">
          <strong>${r.name}</strong><br/>
          ${r.address}<br/>
          ${r.grade ? `Grade: ${r.grade} · ` : ''}Score: ${r.composite_score_label}<br/>
          ${r.cuisine_tags?.join(', ') || ''}<br/>
          ${r.phone || ''}
        </div>`,
      );
      if (onSelectRestaurant) {
        marker.on('click', () => onSelectRestaurant(r.id));
      }
      group.addLayer(marker);
    }
  }, [results, onSelectRestaurant]);

  const fetchRestaurants = useCallback(
    async (override?: Partial<{ search: string; borough: string; cuisine: string; minScore: string; maxScore: string; sortBy: string; onlyVisibleArea: boolean }>) => {
      const s = override?.search ?? search;
      const br = override?.borough ?? borough;
      const cu = override?.cuisine ?? cuisine;
      const mn = override?.minScore ?? minScore;
      const mx = override?.maxScore ?? maxScore;
      const so = override?.sortBy ?? sortBy;
      const ov = override?.onlyVisibleArea ?? onlyVisibleArea;

      setLoading(true);
      setLoadError(null);
      try {
        const params = new URLSearchParams();
        if (s.trim()) params.set('search', s.trim());
        if (br !== 'all') {
          const b =
            br === 'staten' ? 'Staten Island' : br.charAt(0).toUpperCase() + br.slice(1);
          params.set('borough', b);
        }
        if (cu !== 'all') params.set('cuisine', cu);
        if (mn.trim()) params.set('min_score', mn.trim());
        if (mx.trim()) params.set('max_score', mx.trim());
        params.set('sort_by', mapSortByToApi(so));
        params.set('limit', '500');
        if (ov && mapRef.current) {
          const bounds = mapRef.current.getBounds();
          params.set('sw_lat', String(bounds.getSouthWest().lat));
          params.set('sw_lng', String(bounds.getSouthWest().lng));
          params.set('ne_lat', String(bounds.getNorthEast().lat));
          params.set('ne_lng', String(bounds.getNorthEast().lng));
        }
        const r = await apiFetch(`/api/restaurants/map-data/?${params.toString()}`);
        if (!r.ok) {
          setLoadError(`Could not load map data (${r.status}).`);
          setResults([]);
          return;
        }
        const data = await r.json();
        const list = (data.results ?? []) as MapRestaurantPoint[];
        setResults(list);
      } catch {
        setLoadError('Network error loading restaurants.');
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [search, borough, cuisine, minScore, maxScore, sortBy, onlyVisibleArea]
  );

  useEffect(() => {
    void fetchRestaurants();
  }, []);

  const handleResetFilters = () => {
    setSearch('');
    setBorough('all');
    setCuisine('all');
    setMinScore('');
    setMaxScore('');
    setSortBy('composite-high-low');
    setOnlyVisibleArea(false);
    void fetchRestaurants({
      search: '',
      borough: 'all',
      cuisine: 'all',
      minScore: '',
      maxScore: '',
      sortBy: 'composite-high-low',
      onlyVisibleArea: false,
    });
  };

  return (
    <div className="w-full flex flex-col" style={{ backgroundColor: '#FFF9F5', minHeight: '100vh' }}>
      {/* Navigation Bar */}
      <nav className="w-full px-8 py-4 flex items-center justify-between">
        {isAdmin ? (
          <>
            <div className="flex items-center gap-6">
              <button
                onClick={onNavigateProfile}
                className="text-xl transition-all p-2 rounded-lg"
                title="Back"
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
                style={{ 
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#E06E7F',
                  fontWeight: 'normal'
                }}
              >
                ←
              </button>
              
              <h1 className="text-2xl" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                nomz Admin
              </h1>
            </div>
            
            <button
              onClick={onLogout}
              className="text-xl transition-all p-2 rounded-lg"
              title="Logout"
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
              style={{ 
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: '#E06E7F',
                fontWeight: 'normal'
              }}
            >
              →
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center gap-6">
              <button
                onClick={onNavigateHome}
                className="text-xl transition-all p-2 rounded-lg"
                title="Home"
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
                style={{ 
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#E06E7F',
                  fontWeight: 'normal'
                }}
              >
                ←
              </button>
              
              <h1 className="text-2xl" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                nomz
              </h1>
            </div>
            
            <div className="flex items-center gap-4">
              <button
                onClick={onNavigateMessages}
                className="text-xl transition-all p-2 rounded-lg"
                title="Messages"
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
                style={{ 
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#E06E7F',
                  fontWeight: 'normal'
                }}
              >
                💬
              </button>

              {onNavigateFriendChat && (
                <button
                  onClick={onNavigateFriendChat}
                  className="text-xl transition-all p-2 rounded-lg"
                  title="Friend Chat"
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                  style={{ 
                    backgroundColor: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#E06E7F',
                    fontWeight: 'normal'
                  }}
                >
                  🤝
                </button>
              )}
              
              <button
                onClick={onNavigateProfile}
                className="text-xl transition-all p-2 rounded-lg"
                title="Profile"
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
                style={{ 
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#E06E7F',
                  fontWeight: 'normal'
                }}
              >
                👤
              </button>
              
              <button
                onClick={onLogout}
                className="text-xl transition-all p-2 rounded-lg"
                title="Logout"
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
                style={{ 
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#E06E7F',
                  fontWeight: 'normal'
                }}
              >
                →
              </button>
            </div>
          </>
        )}
      </nav>

      {/* Main Content */}
      <main className="w-full px-8 pb-8">
        <div className="w-full flex flex-col gap-4">
          {/* Filters Section */}
          <div className="w-full p-6 rounded-lg" style={{ 
            backgroundColor: 'white',
            border: '2px solid rgba(224, 110, 127, 0.1)'
          }}>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
              {/* Search */}
              <div>
                <label className="block text-xs mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Search
                </label>
                <input
                  type="text"
                  placeholder="Name, street, or ZIP"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-xs focus:outline-none transition-all"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                />
              </div>

              {/* Borough */}
              <div>
                <label className="block text-xs mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Borough
                </label>
                <select
                  value={borough}
                  onChange={(e) => setBorough(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-xs focus:outline-none transition-all"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                >
                  <option value="all">All Boroughs</option>
                  <option value="manhattan">Manhattan</option>
                  <option value="brooklyn">Brooklyn</option>
                  <option value="queens">Queens</option>
                  <option value="bronx">The Bronx</option>
                  <option value="staten">Staten Island</option>
                </select>
              </div>

              {/* Cuisine */}
              <div>
                <label className="block text-xs mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Cuisine
                </label>
                <select
                  value={cuisine}
                  onChange={(e) => setCuisine(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-xs focus:outline-none transition-all"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                >
                  <option value="all">All cuisines</option>
                  <option value="italian">Italian</option>
                  <option value="chinese">Chinese</option>
                  <option value="mexican">Mexican</option>
                  <option value="japanese">Japanese</option>
                  <option value="american">American</option>
                </select>
              </div>

              {/* Min Score */}
              <div>
                <label className="block text-xs mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Min Score
                </label>
                <input
                  type="number"
                  placeholder="0"
                  value={minScore}
                  onChange={(e) => setMinScore(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-xs focus:outline-none transition-all"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              {/* Max Score */}
              <div>
                <label className="block text-xs mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Max Score
                </label>
                <input
                  type="number"
                  placeholder="100"
                  value={maxScore}
                  onChange={(e) => setMaxScore(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-xs focus:outline-none transition-all"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                />
              </div>

              {/* Sort By */}
              <div>
                <label className="block text-xs mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Sort by
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full px-3 py-2 border rounded text-xs focus:outline-none transition-all"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                >
                  <option value="composite-high-low">Composite: High → Low</option>
                  <option value="composite-low-high">Composite: Low → High</option>
                  <option value="name-a-z">Name: A → Z</option>
                  <option value="name-z-a">Name: Z → A</option>
                </select>
              </div>

              {/* Map Scope Checkbox */}
              <div>
                <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  <input
                    type="checkbox"
                    checked={onlyVisibleArea}
                    onChange={(e) => setOnlyVisibleArea(e.target.checked)}
                    className="cursor-pointer"
                    style={{ accentColor: '#E06E7F' }}
                  />
                  Only visible map area
                </label>
              </div>
            </div>

            {/* Buttons */}
            {loadError && (
              <p className="text-xs mt-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#b91c1c' }}>
                {loadError}
              </p>
            )}

            <div className="flex gap-4 mt-4">
              <button
                type="button"
                className="flex-1 px-4 py-2 rounded text-xs transition-all"
                style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.7)',
                  color: 'white',
                  border: 'none',
                  fontFamily: 'Montserrat, sans-serif',
                  cursor: 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.9)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.7)';
                }}
                onClick={handleResetFilters}
              >
                Reset
              </button>
              <button
                type="button"
                className="flex-1 px-4 py-2 rounded text-xs transition-all"
                style={{ 
                  backgroundColor: '#5a6c7d',
                  color: 'white',
                  border: 'none',
                  fontFamily: 'Montserrat, sans-serif',
                  cursor: loading ? 'wait' : 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#4a5c6d';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#5a6c7d';
                }}
                onClick={() => void fetchRestaurants()}
                disabled={loading}
              >
                {loading ? 'Loading…' : 'Apply Filters'}
              </button>
            </div>
          </div>

          {/* Map and Restaurant List */}
          <div className="flex gap-4" style={{ height: '500px' }}>
            {/* Map Area */}
            <div className="flex-1 rounded-lg overflow-hidden" style={{ 
              border: '2px solid rgba(224, 110, 127, 0.1)',
              height: '100%'
            }}>
              <div ref={mapContainerRef} className="size-full" />
            </div>

            {/* Restaurant List */}
            <div className="w-96 rounded-lg overflow-hidden flex flex-col" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)',
              height: '100%'
            }}>
              {/* Header */}
              <div className="px-4 py-3 flex items-center justify-between" style={{ 
                borderBottom: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h3 className="text-sm" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Nearby restaurants
                </h3>
                <span className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999'
                }}>
                  {loading ? '…' : `${results.length} results`}
                </span>
              </div>

              {/* Restaurant List */}
              <div className="flex-1 overflow-y-auto">
                <p className="px-4 py-2 text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999'
                }}>
                  Click a row or marker to view details.
                </p>

                {/* Legend */}
                <div className="px-4 py-2 flex gap-3 text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif'
                }}>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#90EE90' }}></span>
                    <span style={{ color: '#666' }}>90+</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#FFD700' }}></span>
                    <span style={{ color: '#666' }}>80-79</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#FFA07A' }}></span>
                    <span style={{ color: '#666' }}>&lt;80</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#D3D3D3' }}></span>
                    <span style={{ color: '#666' }}>no score</span>
                  </span>
                </div>

                {results.map((restaurant) => {
                  const cuisineStr =
                    restaurant.borough && restaurant.cuisine_tags?.length
                      ? `${restaurant.borough} · ${restaurant.cuisine_tags.join(', ')}`
                      : restaurant.cuisine_tags?.join(', ') || '';
                  return (
                    <div
                      key={restaurant.id}
                      className="px-4 py-3 cursor-pointer transition-all"
                      style={{
                        borderBottom: '1px solid rgba(224, 110, 127, 0.1)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                      onClick={() => {
                        if (mapRef.current && restaurant.latitude && restaurant.longitude) {
                          mapRef.current.flyTo([restaurant.latitude, restaurant.longitude], 16);
                        }
                        onSelectRestaurant?.(restaurant.id);
                      }}
                    >
                      <div className="flex items-start justify-between mb-1">
                        <h4
                          className="text-xs"
                          style={{
                            fontFamily: 'Montserrat, sans-serif',
                            color: '#333',
                          }}
                        >
                          {restaurant.name}
                        </h4>
                        <span
                          className="text-xs ml-2"
                          style={{
                            fontFamily: 'Montserrat, sans-serif',
                            color: '#E06E7F',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {restaurant.composite_score_label}
                        </span>
                      </div>
                      <p
                        className="text-xs mb-1"
                        style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#666',
                        }}
                      >
                        {restaurant.address}
                      </p>
                      <p
                        className="text-xs"
                        style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#999',
                        }}
                      >
                        {cuisineStr}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}