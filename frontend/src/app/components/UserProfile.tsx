import { Footer } from "./Footer";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

/** Must match `Restaurant.CUISINE_CHOICES` / `UserPreferenceForm` values (slugs sent to the API). */
const CUISINE_CHOICES: { value: string; label: string }[] = [
  { value: "american", label: "American" },
  { value: "asian", label: "Asian" },
  { value: "italian", label: "Italian" },
  { value: "mexican", label: "Mexican" },
  { value: "indian", label: "Indian" },
  { value: "french", label: "French" },
  { value: "japanese", label: "Japanese" },
  { value: "chinese", label: "Chinese" },
  { value: "thai", label: "Thai" },
  { value: "mediterranean", label: "Mediterranean" },
  { value: "fusion", label: "Fusion" },
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "other", label: "Other" },
];

const DIETARY_OPTIONS = ["Vegan", "Vegetarian", "Non-vegetarian", "Gluten-Free", "Halal", "Kosher"] as const;

function splitFullName(full: string): { first_name: string; last_name: string } {
  const t = full.trim();
  const i = t.indexOf(" ");
  if (i === -1) return { first_name: t, last_name: "" };
  return { first_name: t.slice(0, i), last_name: t.slice(i + 1).trim() };
}

export function UserProfile({ onBack, onViewMessages, onViewFriendChat, onNavigateMap, onNavigateHome, onLogout, username }: { onBack: () => void; onViewMessages: () => void; onViewFriendChat: () => void; onNavigateMap: () => void; onNavigateHome: () => void; onLogout: () => void; username: string }) {
  const [editingDetails, setEditingDetails] = useState(false);
  const [editingTaste, setEditingTaste] = useState(false);
  const [editingDietaryRestrictions, setEditingDietaryRestrictions] = useState(false);

  const [fullName, setFullName] = useState(username);
  const [email, setEmail] = useState("");
  const [reviewsWritten, setReviewsWritten] = useState(0);

  const [favoriteCuisineSlugs, setFavoriteCuisineSlugs] = useState<string[]>([]);
  const [dietaryRestrictions, setDietaryRestrictions] = useState<string[]>([]);
  const [priceRange, setPriceRange] = useState("$$");
  const [location, setLocation] = useState("Manhattan");
  const [boroughs] = useState(["Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island"]);

  const [prefsLoading, setPrefsLoading] = useState(true);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [prefsError, setPrefsError] = useState<string | null>(null);
  const [accountLoading, setAccountLoading] = useState(true);
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  const cuisineLabel = (slug: string) =>
    CUISINE_CHOICES.find((c) => c.value === slug)?.label ?? slug;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setPrefsLoading(true);
      setAccountLoading(true);
      setPrefsError(null);
      setAccountError(null);
      try {
        const [prefsRes, accountRes] = await Promise.all([
          apiFetch("/api/diner/preferences/"),
          apiFetch("/api/diner/account/"),
        ]);
        if (!prefsRes.ok) {
          if (!cancelled) setPrefsError("Could not load saved preferences.");
        } else {
          const d = await prefsRes.json();
          if (!cancelled) {
            setFavoriteCuisineSlugs(Array.isArray(d.favorite_cuisines) ? d.favorite_cuisines : []);
            setDietaryRestrictions(Array.isArray(d.dietary_restrictions) ? d.dietary_restrictions : []);
            if (typeof d.price_preference === "string" && d.price_preference) {
              setPriceRange(d.price_preference);
            }
            if (typeof d.neighborhood_preference === "string" && d.neighborhood_preference.trim()) {
              setLocation(d.neighborhood_preference.trim());
            }
          }
        }
        if (!accountRes.ok) {
          if (!cancelled) setAccountError("Could not load account details.");
        } else {
          const a = await accountRes.json();
          if (!cancelled) {
            const fn = typeof a.first_name === "string" ? a.first_name : "";
            const ln = typeof a.last_name === "string" ? a.last_name : "";
            const display = [fn, ln].filter(Boolean).join(" ").trim();
            setFullName(display || username);
            setEmail(typeof a.email === "string" ? a.email : "");
            setReviewsWritten(typeof a.reviews_written === "number" ? a.reviews_written : 0);
          }
        }
      } catch {
        if (!cancelled) {
          setPrefsError("Network error loading preferences.");
          setAccountError("Network error loading account.");
        }
      } finally {
        if (!cancelled) {
          setPrefsLoading(false);
          setAccountLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [username]);

  const persistDinerAccount = useCallback(async () => {
    const { first_name, last_name } = splitFullName(fullName);
    setAccountSaving(true);
    setAccountError(null);
    try {
      const r = await apiFetch("/api/diner/account/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          first_name,
          last_name,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setAccountError(typeof data.error === "string" ? data.error : "Could not save profile.");
        return false;
      }
      return true;
    } catch {
      setAccountError("Network error while saving profile.");
      return false;
    } finally {
      setAccountSaving(false);
    }
  }, [fullName, email]);

  const persistDinerPreferences = useCallback(
    async (overrides?: {
      favorite_cuisines?: string[];
      dietary_restrictions?: string[];
      price_preference?: string;
      neighborhood_preference?: string;
    }) => {
      const body = {
        favorite_cuisines: overrides?.favorite_cuisines ?? favoriteCuisineSlugs,
        dietary_restrictions: overrides?.dietary_restrictions ?? dietaryRestrictions,
        price_preference: overrides?.price_preference ?? priceRange,
        neighborhood_preference: overrides?.neighborhood_preference ?? location,
      };
      setPrefsSaving(true);
      setPrefsError(null);
      try {
        const r = await apiFetch("/api/diner/preferences/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
          setPrefsError("Could not save preferences. Check your selections and try again.");
          return false;
        }
        if (data.errors) {
          setPrefsError("Could not save preferences.");
          return false;
        }
        return true;
      } catch {
        setPrefsError("Network error while saving.");
        return false;
      } finally {
        setPrefsSaving(false);
      }
    },
    [favoriteCuisineSlugs, dietaryRestrictions, priceRange, location]
  );

  const toggleCuisine = (slug: string) => {
    setFavoriteCuisineSlugs((prev) =>
      prev.includes(slug) ? prev.filter((c) => c !== slug) : [...prev, slug]
    );
  };

  const toggleDietaryRestriction = (restriction: string) => {
    setDietaryRestrictions((prev) =>
      prev.includes(restriction) ? prev.filter((r) => r !== restriction) : [...prev, restriction]
    );
  };
  
  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      {/* Navigation Bar */}
      <nav className="w-full px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <button
            onClick={onBack}
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
            nomz
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
          <button
            onClick={onNavigateMap}
            className="text-xl transition-all p-2 rounded-lg"
            title="Map"
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
            🗺️
          </button>
          
          <button
            onClick={onViewMessages}
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

          <button
            onClick={onViewFriendChat}
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
      </nav>

      {/* Main Content */}
      <main className="w-full py-12 px-8 flex-1">
        <div className="max-w-7xl mx-auto">
          {(prefsLoading || accountLoading || prefsError || accountError || prefsSaving || accountSaving) && (
            <div
              className="mb-6 px-4 py-3 rounded-lg text-sm"
              style={{
                fontFamily: "Montserrat, sans-serif",
                backgroundColor: prefsError || accountError ? "rgba(220, 38, 38, 0.08)" : "rgba(224, 110, 127, 0.08)",
                color: prefsError || accountError ? "#b91c1c" : "#666",
                border: `1px solid ${prefsError || accountError ? "rgba(220,38,38,0.2)" : "rgba(224,110,127,0.2)"}`,
              }}
            >
              {(prefsLoading || accountLoading) && "Loading your profile…"}
              {!prefsLoading && !accountLoading && (prefsSaving || accountSaving) && "Saving…"}
              {!prefsLoading && !accountLoading && !prefsSaving && !accountSaving && (prefsError || accountError)}
            </div>
          )}
          {/* Profile Header - Compact */}
          <div className="mb-12 p-8 rounded-lg" style={{ 
            backgroundColor: 'white',
            border: '2px solid rgba(224, 110, 127, 0.1)'
          }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div className="w-20 h-20 rounded-full flex items-center justify-center text-3xl" style={{ 
                  backgroundColor: 'rgba(224, 110, 127, 0.15)' 
                }}>
                  👤
                </div>
                {!editingDetails ? (
                  <div>
                    <h2 className="text-2xl mb-1" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#E06E7F'
                    }}>
                      {fullName}
                    </h2>
                    <p className="text-sm" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      {email}
                    </p>
                  </div>
                ) : (
                  <div className="flex gap-4">
                    <div>
                      <input
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Full Name"
                        className="px-4 py-2 border-2 rounded-lg focus:outline-none transition-all text-sm mb-2"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)',
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'white',
                          width: '250px'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Email"
                        className="px-4 py-2 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)',
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'white',
                          width: '250px'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      />
                    </div>
                  </div>
                )}
              </div>
              
              <button
                className="px-5 py-2 rounded-lg transition-all text-sm"
                title={editingDetails ? 'Save' : 'Edit Profile'}
                style={{ 
                  backgroundColor: editingDetails ? '#E06E7F' : 'transparent',
                  color: editingDetails ? 'white' : '#E06E7F',
                  border: '2px solid #E06E7F',
                  fontFamily: 'Montserrat, sans-serif'
                }}
                onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; if (!editingDetails) e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; if (!editingDetails) e.currentTarget.style.backgroundColor = 'transparent'; }}
                disabled={accountSaving || prefsSaving || prefsLoading || accountLoading}
                onClick={async () => {
                  if (!editingDetails) {
                    setEditingDetails(true);
                    return;
                  }
                  const ok = await persistDinerAccount();
                  if (ok) setEditingDetails(false);
                }}
              >
                {editingDetails ? 'Save' : 'Edit Profile'}
              </button>
            </div>
          </div>

          {/* Dashboard Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            
            {/* Favorite Cuisines Card */}
            <div className="p-6 rounded-lg" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Favorite Cuisines
                </h3>
                <span style={{ fontSize: '24px' }}>🍽️</span>
              </div>
              
              {!editingTaste ? (
                <div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-4 min-h-[120px]">
                    {favoriteCuisineSlugs.length === 0 ? (
                      <p className="text-xs col-span-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                        No cuisines selected yet. Edit to choose favorites (saved to your account for recommendations).
                      </p>
                    ) : (
                      favoriteCuisineSlugs.map((slug) => (
                        <span
                          key={slug}
                          className="text-sm"
                          style={{
                            color: '#333',
                            fontFamily: 'Montserrat, sans-serif',
                          }}
                        >
                          {cuisineLabel(slug)}
                        </span>
                      ))
                    )}
                  </div>
                  <button
                    className="text-xs transition-all w-full py-2 rounded-lg"
                    title="Edit favorite cuisines"
                    style={{ 
                      color: '#E06E7F',
                      fontFamily: 'Montserrat, sans-serif',
                      border: '1px solid rgba(224, 110, 127, 0.3)',
                      backgroundColor: 'transparent',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                    onClick={() => setEditingTaste(true)}
                  >
                    Edit
                  </button>
                </div>
              ) : (
                <div>
                  <div className="space-y-2 mb-4 max-h-[180px] overflow-y-auto">
                    {CUISINE_CHOICES.map(({ value, label }) => (
                      <label 
                        key={value}
                        className="flex items-center gap-2 cursor-pointer"
                        style={{ 
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#333'
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={favoriteCuisineSlugs.includes(value)}
                          onChange={() => toggleCuisine(value)}
                          className="w-4 h-4 cursor-pointer"
                          style={{ 
                            accentColor: '#E06E7F'
                          }}
                        />
                        <span className="text-xs">{label}</span>
                      </label>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={prefsSaving}
                    className="text-xs w-full py-2 rounded-lg transition-all"
                    title="Save favorite cuisines"
                    style={{ 
                      backgroundColor: '#E06E7F',
                      color: 'white',
                      fontFamily: 'Montserrat, sans-serif',
                      border: 'none',
                      cursor: prefsSaving ? 'wait' : 'pointer',
                      opacity: prefsSaving ? 0.75 : 1,
                    }}
                    onClick={async () => {
                      const ok = await persistDinerPreferences();
                      if (ok) setEditingTaste(false);
                    }}
                  >
                    Save
                  </button>
                </div>
              )}
            </div>

            {/* Dietary Restrictions Card */}
            <div className="p-6 rounded-lg" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Dietary Restrictions
                </h3>
                <span style={{ fontSize: '24px' }}>🥗</span>
              </div>
              
              {!editingDietaryRestrictions ? (
                <div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-4 min-h-[120px]">
                    {dietaryRestrictions.length > 0 ? (
                      dietaryRestrictions.map((restriction) => (
                        <span 
                          key={restriction}
                          className="text-sm"
                          style={{ 
                            color: '#333',
                            fontFamily: 'Montserrat, sans-serif'
                          }}
                        >
                          {restriction}
                        </span>
                      ))
                    ) : (
                      <p className="text-xs col-span-2" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        No dietary restrictions
                      </p>
                    )}
                  </div>
                  <button
                    className="text-xs transition-all w-full py-2 rounded-lg"
                    title="Edit dietary restrictions"
                    style={{ 
                      color: '#E06E7F',
                      fontFamily: 'Montserrat, sans-serif',
                      border: '1px solid rgba(224, 110, 127, 0.3)',
                      backgroundColor: 'transparent',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                    onClick={() => setEditingDietaryRestrictions(true)}
                  >
                    Edit
                  </button>
                </div>
              ) : (
                <div>
                  <div className="space-y-2 mb-4 max-h-[180px] overflow-y-auto">
                    {DIETARY_OPTIONS.map((restriction) => (
                      <label 
                        key={restriction}
                        className="flex items-center gap-2 cursor-pointer"
                        style={{ 
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#333'
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={dietaryRestrictions.includes(restriction)}
                          onChange={() => toggleDietaryRestriction(restriction)}
                          className="w-4 h-4 cursor-pointer"
                          style={{ 
                            accentColor: '#E06E7F'
                          }}
                        />
                        <span className="text-xs">{restriction}</span>
                      </label>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={prefsSaving}
                    className="text-xs w-full py-2 rounded-lg transition-all"
                    title="Save dietary restrictions"
                    style={{ 
                      backgroundColor: '#E06E7F',
                      color: 'white',
                      fontFamily: 'Montserrat, sans-serif',
                      border: 'none',
                      cursor: prefsSaving ? 'wait' : 'pointer',
                      opacity: prefsSaving ? 0.75 : 1,
                    }}
                    onClick={async () => {
                      const ok = await persistDinerPreferences();
                      if (ok) setEditingDietaryRestrictions(false);
                    }}
                  >
                    Save
                  </button>
                </div>
              )}
            </div>

            {/* Price Range Card */}
            <div className="p-6 rounded-lg" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Price Range
                </h3>
                <span style={{ fontSize: '24px' }}>💰</span>
              </div>
              
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-4 gap-2">
                  {['$', '$$', '$$$', '$$$$'].map((price) => (
                    <button
                      type="button"
                      key={price}
                      disabled={prefsSaving}
                      className="py-3 rounded-lg cursor-pointer transition-all text-center text-sm"
                      style={{ 
                        backgroundColor: price === priceRange ? '#E06E7F' : 'rgba(224, 110, 127, 0.1)',
                        color: price === priceRange ? 'white' : '#E06E7F',
                        fontFamily: 'Montserrat, sans-serif',
                        border: 'none',
                        opacity: prefsSaving ? 0.7 : 1,
                      }}
                      onClick={async () => {
                        setPriceRange(price);
                        await persistDinerPreferences({ price_preference: price });
                      }}
                      onMouseEnter={(e) => {
                        if (price !== priceRange) {
                          e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.2)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (price !== priceRange) {
                          e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                        }
                      }}
                    >
                      {price}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Preferred Location Card */}
            <div className="p-6 rounded-lg" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Preferred Location
                </h3>
                <span style={{ fontSize: '24px' }}>📍</span>
              </div>
              
              <select
                value={location}
                onChange={async (e) => {
                  const v = e.target.value;
                  setLocation(v);
                  await persistDinerPreferences({ neighborhood_preference: v });
                }}
                disabled={prefsSaving}
                className="w-full px-4 py-3 border-2 rounded-lg focus:outline-none transition-all text-sm cursor-pointer"
                style={{ 
                  borderColor: 'rgba(224, 110, 127, 0.2)',
                  fontFamily: 'Montserrat, sans-serif',
                  backgroundColor: 'white',
                  color: '#333'
                }}
                onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
              >
                {boroughs.map((borough) => (
                  <option key={borough} value={borough}>
                    {borough}
                  </option>
                ))}
              </select>
            </div>

            {/* No server-side saved-restaurants list yet */}
            <div className="p-6 rounded-lg" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Saved restaurants
                </h3>
                <span style={{ fontSize: '24px' }}>📌</span>
              </div>
              <p className="text-sm" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#666',
                lineHeight: 1.5,
              }}>
                Nomz does not store a favorites list yet. Use Search or the map to find places again, or message a restaurant from its page.
              </p>
            </div>

            {/* Reviews Written Card */}
            <div className="p-6 rounded-lg" style={{ 
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Reviews Written
                </h3>
                <span style={{ fontSize: '24px' }}>⭐</span>
              </div>
              <p className="text-5xl" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#333'
              }}>
                {reviewsWritten}
              </p>
            </div>

          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}