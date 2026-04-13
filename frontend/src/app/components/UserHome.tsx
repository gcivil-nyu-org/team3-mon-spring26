import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import { Footer } from "./Footer";

type RecRow = {
  id: number;
  name: string;
  cuisine: string;
  price_label: string;
  neighborhood: string;
};

export function UserHome({
  onLogout,
  onViewProfile,
  onViewMessages,
  onViewFriendChat,
  onNavigateMap,
  onSearch,
  onOpenRecommendations,
  onSelectRestaurant,
  username,
}: {
  onLogout: () => void;
  onViewProfile: () => void;
  onViewMessages: () => void;
  onViewFriendChat: () => void;
  onNavigateMap: () => void;
  onSearch: (q: string, neighborhood?: string) => void;
  onOpenRecommendations: () => void;
  onSelectRestaurant: (id: number) => void;
  username: string;
}) {
  const [showLogoutText, setShowLogoutText] = useState(false);
  const [showMapTooltip, setShowMapTooltip] = useState(false);
  const [showMessagesTooltip, setShowMessagesTooltip] = useState(false);
  const [showFriendChatTooltip, setShowFriendChatTooltip] = useState(false);
  const [showProfileTooltip, setShowProfileTooltip] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [cuisineFilter, setCuisineFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [recs, setRecs] = useState<RecRow[]>([]);
  const [recMessage, setRecMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await apiFetch("/api/recommendations/");
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (cancelled) return;
        if (d.requires_preferences) {
          setRecs([]);
          setRecMessage("Set your preferences in your profile to see personalized picks here.");
          return;
        }
        setRecMessage(typeof d.message === "string" && d.message ? d.message : null);
        const list = Array.isArray(d.restaurants) ? d.restaurants.slice(0, 3) : [];
        setRecs(list);
      } catch {
        if (!cancelled) setRecMessage(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parts = [searchInput.trim(), cuisineFilter].filter(Boolean).join(' ');
    onSearch(parts, locationFilter || undefined);
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      <nav className="w-full px-8 py-4 flex items-center justify-between">
        <h1 className="text-2xl" style={{ 
          fontFamily: 'Montserrat, sans-serif',
          color: '#E06E7F'
        }}>
          nomz
        </h1>
        
        <div className="flex items-center gap-6">
          <div className="relative">
            <button
              onClick={onNavigateMap}
              className="text-xl transition-all p-2 rounded-lg"
              title="Map"
              onMouseEnter={(e) => {
                setShowMapTooltip(true);
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                setShowMapTooltip(false);
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
              🗺️
            </button>
            {showMapTooltip && (
              <div 
                className="absolute top-full mt-1 left-1/2 transform -translate-x-1/2 px-2 py-1 rounded text-xs whitespace-nowrap"
                style={{ 
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                map
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={onViewMessages}
              className="text-xl transition-all p-2 rounded-lg"
              title="Messages"
              onMouseEnter={(e) => {
                setShowMessagesTooltip(true);
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                setShowMessagesTooltip(false);
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
            {showMessagesTooltip && (
              <div 
                className="absolute top-full mt-1 left-1/2 transform -translate-x-1/2 px-2 py-1 rounded text-xs whitespace-nowrap"
                style={{ 
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                messages
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={onViewFriendChat}
              className="text-xl transition-all p-2 rounded-lg"
              title="Friend Chat"
              onMouseEnter={(e) => {
                setShowFriendChatTooltip(true);
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                setShowFriendChatTooltip(false);
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
            {showFriendChatTooltip && (
              <div 
                className="absolute top-full mt-1 left-1/2 transform -translate-x-1/2 px-2 py-1 rounded text-xs whitespace-nowrap"
                style={{ 
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                friends
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={onViewProfile}
              className="text-xl transition-all p-2 rounded-lg"
              title="Profile"
              onMouseEnter={(e) => {
                setShowProfileTooltip(true);
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                setShowProfileTooltip(false);
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
            {showProfileTooltip && (
              <div 
                className="absolute top-full mt-1 left-1/2 transform -translate-x-1/2 px-2 py-1 rounded text-xs whitespace-nowrap"
                style={{ 
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                profile
              </div>
            )}
          </div>

          <div className="relative">
            <button
              onClick={onLogout}
              className="text-xl transition-all p-2 rounded-lg"
              title="Logout"
              onMouseEnter={(e) => {
                setShowLogoutText(true);
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                setShowLogoutText(false);
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
            {showLogoutText && (
              <div 
                className="absolute top-full mt-1 right-0 px-2 py-1 rounded text-xs whitespace-nowrap"
                style={{ 
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                logout
              </div>
            )}
          </div>
        </div>
      </nav>

      <main className="w-full py-20 px-8">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl mb-4 text-center" style={{ 
            fontFamily: 'Montserrat, sans-serif',
            color: '#E06E7F'
          }}>
            Welcome, {username}! 🍽️
          </h2>
          
          <p className="text-sm text-center mb-16" style={{ 
            fontFamily: 'Montserrat, sans-serif',
            color: '#666'
          }}>
            Discover amazing restaurants and delicious food near you
          </p>

          <form onSubmit={handleSearchSubmit} className="mb-16 max-w-3xl mx-auto">
            <div className="relative flex gap-2 mb-3">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search for restaurants, cuisines, or dishes..."
                className="flex-1 px-6 py-4 border-2 rounded-lg focus:outline-none transition-all text-sm"
                style={{ 
                  borderColor: 'rgba(224, 110, 127, 0.2)', 
                  fontFamily: 'Montserrat, sans-serif',
                  backgroundColor: 'white'
                }}
                onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
              />
              <button
                type="submit"
                className="px-6 py-4 rounded-lg text-sm text-white shrink-0"
                style={{ backgroundColor: '#E06E7F', border: 'none', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                Search
              </button>
            </div>
            <div className="flex flex-col md:flex-row gap-3">
              <select
                value={cuisineFilter}
                onChange={(e) => setCuisineFilter(e.target.value)}
                className="flex-1 px-4 py-3 border-2 rounded-lg text-sm"
                style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif', backgroundColor: 'white' }}
              >
                <option value="">All Cuisines</option>
                {["American","Asian","Italian","Mexican","Indian","French","Japanese","Chinese","Thai","Mediterranean","Fusion","Vegetarian","Vegan"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
              <select
                value={locationFilter}
                onChange={(e) => setLocationFilter(e.target.value)}
                className="flex-1 px-4 py-3 border-2 rounded-lg text-sm"
                style={{ borderColor: 'rgba(224, 110, 127, 0.25)', fontFamily: 'Montserrat, sans-serif', backgroundColor: 'white' }}
              >
                <option value="">All Locations</option>
                {["Manhattan","Brooklyn","Queens","The Bronx","Staten Island"].map((b) => (
                  <option key={b} value={b}>{b}</option>
                ))}
              </select>
            </div>
            <p className="text-xs mt-2 text-center" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
              Opens full results with neighborhood and sort, matching the server search page.
            </p>
          </form>

          <div className="mb-12">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
              <h3 className="text-xl" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                Recommended for you
              </h3>
              <button
                type="button"
                onClick={onOpenRecommendations}
                className="text-sm px-4 py-2 rounded-lg text-white"
                style={{ backgroundColor: '#E06E7F', border: 'none', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                See all recommendations
              </button>
            </div>
            
            {recMessage && (
              <p className="text-sm mb-4" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                {recMessage}
              </p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {recs.length === 0 && !recMessage
                ? [1, 2, 3].map((item) => (
                    <div
                      key={item}
                      className="rounded-lg overflow-hidden"
                      style={{
                        backgroundColor: 'white',
                        border: '2px solid rgba(224, 110, 127, 0.1)',
                        minHeight: '200px',
                      }}
                    />
                  ))
                : recs.map((row) => (
                    <button
                      key={row.id}
                      type="button"
                      onClick={() => onSelectRestaurant(row.id)}
                      className="rounded-lg overflow-hidden transition-all text-left"
                      style={{ 
                        backgroundColor: 'white',
                        border: '2px solid rgba(224, 110, 127, 0.1)',
                        cursor: 'pointer',
                        fontFamily: 'Montserrat, sans-serif',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'translateY(-4px)';
                        e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.3)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
                      }}
                    >
                      <div className="h-32 w-full" style={{ backgroundColor: 'rgba(224, 110, 127, 0.1)' }} />
                      <div className="p-5">
                        <h4 className="text-base mb-2" style={{ color: '#333' }}>
                          {row.name}
                        </h4>
                        <p className="text-xs mb-3" style={{ color: '#666' }}>
                          {row.cuisine} • {row.price_label}
                          {row.neighborhood ? ` • ${row.neighborhood}` : ''}
                        </p>
                      </div>
                    </button>
                  ))}
            </div>
          </div>

          <div>
            <h3 className="text-xl mb-8" style={{ 
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F'
            }}>
              Popular Cuisines
            </h3>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Italian 🍝', q: 'Italian' },
                { label: 'Japanese 🍣', q: 'Japanese' },
                { label: 'Mexican 🌮', q: 'Mexican' },
                { label: 'Indian 🍛', q: 'Indian' },
              ].map(({ label, q }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => onSearch(q)}
                  className="p-6 rounded-lg text-center transition-all"
                  style={{ 
                    backgroundColor: 'rgba(224, 110, 127, 0.08)',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.15)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.08)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <p className="text-sm" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#E06E7F'
                  }}>
                    {label}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
