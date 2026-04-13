import { Footer } from "./Footer";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

type Choice = { value: string; label: string };

export function RestaurantProfile({ onLogout, username, onNavigateMessages, onPhotoManagement, onNavigateMap, onNavigateRestaurantMap, onBack, onManageActivation, onClaimListing, onRestaurantForm }: { onLogout: () => void; username: string; onNavigateMessages: () => void; onPhotoManagement: () => void; onNavigateMap: () => void; onNavigateRestaurantMap?: () => void; onBack: () => void; onManageActivation?: () => void; onClaimListing?: () => void; onRestaurantForm?: () => void }) {
  const [showLogoutText, setShowLogoutText] = useState(false);
  const [showMapTooltip, setShowMapTooltip] = useState(false);
  const [showMessagesTooltip, setShowMessagesTooltip] = useState(false);
  const [showProfileTooltip, setShowProfileTooltip] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'performance' | 'details' | 'reviews'>('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [showCommunicationSettings, setShowCommunicationSettings] = useState(false);
  const [showAvailabilitySettings, setShowAvailabilitySettings] = useState(false);

  const [profileLoading, setProfileLoading] = useState(true);
  const [hasRestaurant, setHasRestaurant] = useState(false);
  const [cuisineChoices, setCuisineChoices] = useState<Choice[]>([]);
  const [priceChoices, setPriceChoices] = useState<Choice[]>([]);
  const [cuisineTypeLabel, setCuisineTypeLabel] = useState("");
  const [priceRangeLabel, setPriceRangeLabel] = useState("");

  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [website, setWebsite] = useState("");
  const [description, setDescription] = useState("");
  const [cuisineType, setCuisineType] = useState("other");
  const [priceRange, setPriceRange] = useState("$$");
  const [hoursOpen, setHoursOpen] = useState("09:00");
  const [hoursClose, setHoursClose] = useState("21:00");
  const [operatingHours, setOperatingHours] = useState("");
  const [messagingHours, setMessagingHours] = useState("");

  const [messagingEnabled, setMessagingEnabled] = useState(true);
  const [responseHoursStart, setResponseHoursStart] = useState("");
  const [responseHoursEnd, setResponseHoursEnd] = useState("");

  const [isTemporarilyUnavailable, setIsTemporarilyUnavailable] = useState(false);
  const [unavailabilityReason, setUnavailabilityReason] = useState("");
  const [availableAgainDate, setAvailableAgainDate] = useState("");

  const [profileSaveError, setProfileSaveError] = useState<string | null>(null);
  const [communicationSaveError, setCommunicationSaveError] = useState<string | null>(null);
  const [availabilitySaveError, setAvailabilitySaveError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingCommunication, setSavingCommunication] = useState(false);
  const [savingAvailability, setSavingAvailability] = useState(false);

  const [ownerCompositeScore, setOwnerCompositeScore] = useState<number | null>(null);
  const [ownerInspectionRating, setOwnerInspectionRating] = useState<number | null>(null);
  const [ownerReviewCount, setOwnerReviewCount] = useState(0);
  const [ownerCitywideRank, setOwnerCitywideRank] = useState<number | null>(null);
  const [ownerCitywideTotal, setOwnerCitywideTotal] = useState(0);

  // Reviews state for restaurant owner
  interface OwnerReview {
    id: number;
    username: string;
    rating: number;
    comment: string;
    created_at: string;
    owner_response: { response_text: string; responder_username: string; updated_at: string } | null;
  }
  const [ownerReviews, setOwnerReviews] = useState<OwnerReview[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [respondingToReviewId, setRespondingToReviewId] = useState<number | null>(null);
  const [responseText, setResponseText] = useState("");
  const [respondError, setRespondError] = useState<string | null>(null);
  const [respondSaving, setRespondSaving] = useState(false);
  const [restaurantId, setRestaurantId] = useState<number | null>(null);

  const applyRestaurantPayload = useCallback((r: Record<string, unknown>, cuisines: Choice[], prices: Choice[]) => {
    setRestaurantId(typeof r.id === "number" ? r.id : null);
    setBusinessName(String(r.name ?? ""));
    setEmail(String(r.email ?? ""));
    setPhone(String(r.phone ?? ""));
    setAddress(String(r.address ?? ""));
    setWebsite(String(r.website ?? ""));
    setDescription(String(r.description ?? ""));
    const ct = String(r.cuisine_type ?? "other");
    setCuisineType(ct);
    setCuisineTypeLabel(cuisines.find((c) => c.value === ct)?.label ?? ct);
    const pr = String(r.price_range ?? "$$");
    setPriceRange(pr);
    setPriceRangeLabel(prices.find((p) => p.value === pr)?.label ?? pr);
    const ho = String(r.hours_open ?? "09:00").slice(0, 5);
    const hc = String(r.hours_close ?? "21:00").slice(0, 5);
    setHoursOpen(ho);
    setHoursClose(hc);
    setOperatingHours(`${ho} – ${hc}`);
    setMessagingEnabled(Boolean(r.messaging_enabled));
    const rs = String(r.response_hours_start ?? "");
    const re = String(r.response_hours_end ?? "");
    setResponseHoursStart(rs);
    setResponseHoursEnd(re);
    if (rs || re) {
      setMessagingHours(`${rs || "—"} – ${re || "—"}`);
    } else {
      setMessagingHours("Not set (always available)");
    }
    setIsTemporarilyUnavailable(Boolean(r.is_temporarily_unavailable));
    setUnavailabilityReason(String(r.unavailable_reason ?? ""));
    setAvailableAgainDate(String(r.unavailable_until ?? ""));
    const cs = r.composite_score;
    const csNum = typeof cs === "number" ? cs : cs != null && cs !== "" ? Number(cs) : NaN;
    setOwnerCompositeScore(Number.isFinite(csNum) ? csNum : null);
    const ir = r.inspection_rating;
    const irNum = typeof ir === "number" ? ir : ir != null && ir !== "" ? Number(ir) : NaN;
    setOwnerInspectionRating(Number.isFinite(irNum) ? irNum : null);
    const rc = r.review_count;
    setOwnerReviewCount(typeof rc === "number" ? rc : Number(rc) || 0);
    const cr = r.citywide_rank;
    setOwnerCitywideRank(typeof cr === "number" ? cr : cr != null && cr !== "" ? Number(cr) : null);
    const cwt = r.citywide_total;
    setOwnerCitywideTotal(typeof cwt === "number" ? cwt : Number(cwt) || 0);
  }, []);

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    try {
      const res = await apiFetch("/api/restaurant/profile/");
      if (!res.ok) return;
      const d = await res.json();
      const cuisines: Choice[] = Array.isArray(d.cuisine_choices) ? d.cuisine_choices : [];
      const prices: Choice[] = Array.isArray(d.price_choices) ? d.price_choices : [];
      setCuisineChoices(cuisines);
      setPriceChoices(prices);
      setHasRestaurant(Boolean(d.has_restaurant));
      if (d.has_restaurant && d.restaurant) {
        applyRestaurantPayload(d.restaurant, cuisines, prices);
      } else {
        setOwnerCompositeScore(null);
        setOwnerInspectionRating(null);
        setOwnerReviewCount(0);
        setOwnerCitywideRank(null);
        setOwnerCitywideTotal(0);
      }
    } catch {
      /* keep placeholders */
    } finally {
      setProfileLoading(false);
    }
  }, [applyRestaurantPayload]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const loadReviews = useCallback(async () => {
    if (!restaurantId) return;
    setReviewsLoading(true);
    try {
      const r = await apiFetch(`/api/restaurants/${restaurantId}/`);
      if (!r.ok) return;
      const d = await r.json();
      setOwnerReviews(Array.isArray(d.reviews) ? d.reviews : []);
    } catch { /* ignore */ } finally {
      setReviewsLoading(false);
    }
  }, [restaurantId]);

  useEffect(() => {
    if (activeTab === 'reviews' && restaurantId) void loadReviews();
  }, [activeTab, restaurantId, loadReviews]);

  const handleRespondToReview = async (reviewId: number) => {
    if (!responseText.trim()) return;
    setRespondError(null);
    setRespondSaving(true);
    try {
      const r = await apiFetch(`/api/reviews/${reviewId}/respond/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response_text: responseText }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setRespondError(d.error || "Could not save response."); return; }
      setRespondingToReviewId(null);
      setResponseText("");
      void loadReviews();
    } catch { setRespondError("Network error."); } finally { setRespondSaving(false); }
  };

  const handleSave = async () => {
    if (!hasRestaurant) {
      onRestaurantForm?.();
      return;
    }
    setProfileSaveError(null);
    setSavingProfile(true);
    try {
      const body = {
        name: businessName,
        description,
        cuisine_type: cuisineType,
        price_range: priceRange,
        hours_open: hoursOpen.length > 5 ? hoursOpen.slice(0, 5) : hoursOpen,
        hours_close: hoursClose.length > 5 ? hoursClose.slice(0, 5) : hoursClose,
        address,
        phone,
        website,
        email,
      };
      const r = await apiFetch("/api/restaurant/profile/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setProfileSaveError("Could not save profile.");
        setSavingProfile(false);
        return;
      }
      if (data.restaurant) {
        applyRestaurantPayload(data.restaurant, cuisineChoices, priceChoices);
      }
      setIsEditing(false);
    } catch {
      setProfileSaveError("Network error.");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    loadProfile();
  };

  const saveCommunication = async () => {
    setCommunicationSaveError(null);
    setSavingCommunication(true);
    try {
      const r = await apiFetch("/api/restaurant/communication/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messaging_enabled: messagingEnabled,
          response_hours_start: responseHoursStart,
          response_hours_end: responseHoursEnd,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.success) {
        setCommunicationSaveError("Could not save communication settings.");
        setSavingCommunication(false);
        return;
      }
      setMessagingEnabled(Boolean(data.messaging_enabled));
      setResponseHoursStart(String(data.response_hours_start ?? ""));
      setResponseHoursEnd(String(data.response_hours_end ?? ""));
      const rs = String(data.response_hours_start ?? "");
      const re = String(data.response_hours_end ?? "");
      if (rs || re) setMessagingHours(`${rs} – ${re}`);
      else setMessagingHours("Not set (always available)");
      setShowCommunicationSettings(false);
    } catch {
      setCommunicationSaveError("Network error.");
    } finally {
      setSavingCommunication(false);
    }
  };

  const saveAvailability = async () => {
    setAvailabilitySaveError(null);
    setSavingAvailability(true);
    try {
      const r = await apiFetch("/api/restaurant/availability/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          is_temporarily_unavailable: isTemporarilyUnavailable,
          unavailable_reason: unavailabilityReason,
          unavailable_until: availableAgainDate,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.success) {
        setAvailabilitySaveError("Could not save availability.");
        setSavingAvailability(false);
        return;
      }
      setIsTemporarilyUnavailable(Boolean(data.is_temporarily_unavailable));
      setUnavailabilityReason(String(data.unavailable_reason ?? ""));
      setAvailableAgainDate(String(data.unavailable_until ?? ""));
      setShowAvailabilitySettings(false);
    } catch {
      setAvailabilitySaveError("Network error.");
    } finally {
      setSavingAvailability(false);
    }
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
        
        <div className="flex items-center gap-6">
          {/* Map Button */}
          <div className="relative">
            <button
              onClick={onNavigateRestaurantMap || onNavigateMap}
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

          {/* Messages Button */}
          <div className="relative">
            <button
              onClick={onNavigateMessages}
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

          {/* Logout Button */}
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

      {/* Main Content */}
      <main className="w-full py-8 px-8">
        <div className="max-w-7xl mx-auto">
          {!hasRestaurant && !profileLoading && (
            <div className="mb-8 p-5 rounded-lg flex items-start gap-4" style={{ 
              backgroundColor: 'rgba(224, 110, 127, 0.08)',
              border: '2px solid rgba(224, 110, 127, 0.2)'
            }}>
              <span className="text-2xl">🏪</span>
              <div className="flex-1">
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Create your restaurant profile
                </h3>
                <p className="text-sm mb-3" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  You do not have a listing yet. Use the full form (same fields as the server create-restaurant flow).
                </p>
                {onRestaurantForm && (
                  <button
                    type="button"
                    onClick={onRestaurantForm}
                    className="px-5 py-2 rounded-lg text-sm transition-all"
                    style={{
                      fontFamily: 'Montserrat, sans-serif',
                      backgroundColor: '#E06E7F',
                      color: 'white',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    Create restaurant profile
                  </button>
                )}
              </div>
            </div>
          )}

          {hasRestaurant && (
          <div className="mb-8 p-5 rounded-lg flex items-start gap-4" style={{ 
            backgroundColor: 'rgba(224, 110, 127, 0.08)',
            border: '2px solid rgba(224, 110, 127, 0.2)'
          }}>
            <span className="text-2xl">⏳</span>
            <div className="flex-1">
              <h3 className="text-base mb-2" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                Account Pending Approval
              </h3>
              <p className="text-sm" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Your restaurant business account is undergoing security review. Most accounts are verified within 24-48 hours.
              </p>
              {onClaimListing && (
                <button
                  type="button"
                  onClick={onClaimListing}
                  className="mt-4 px-5 py-2 rounded-lg text-sm transition-all"
                  style={{
                    fontFamily: 'Montserrat, sans-serif',
                    backgroundColor: '#E06E7F',
                    color: 'white',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  Claim an existing listing
                </button>
              )}
            </div>
          </div>
          )}

          {/* Hero Section */}
          <div className="mb-8 p-8 rounded-lg" style={{ 
            backgroundColor: 'white',
            border: '2px solid rgba(224, 110, 127, 0.1)'
          }}>
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="text-3xl mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  {profileLoading ? '…' : (businessName || 'Your restaurant')}
                </h2>
                <p className="text-sm mb-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  {profileLoading ? '…' : `${cuisineTypeLabel || cuisineType} • ${priceRangeLabel || priceRange} • ${operatingHours || '—'}`}
                </p>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999'
                }}>
                  {profileLoading ? '…' : `${email || '—'}${hasRestaurant ? '' : ' • add a listing to get started'}`}
                </p>
              </div>
              <div className="flex gap-3">
              </div>
            </div>

            {/* Quick Stats (from GET /api/restaurant/profile/) */}
            <div className="grid grid-cols-4 gap-6">
              <div className="p-4 rounded-lg text-center" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.05)'
              }}>
                <p className="text-2xl mb-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  {profileLoading ? '…' : ownerCompositeScore != null ? ownerCompositeScore.toFixed(1) : '—'}
                </p>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Composite Score
                </p>
              </div>
              <div className="p-4 rounded-lg text-center" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.05)'
              }}>
                <p className="text-2xl mb-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  {profileLoading ? '…' : ownerInspectionRating != null ? ownerInspectionRating.toFixed(1) : '—'}
                </p>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Inspection rating
                </p>
              </div>
              <div className="p-4 rounded-lg text-center" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.05)'
              }}>
                <p className="text-2xl mb-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  {profileLoading ? '…' : ownerCitywideRank != null && ownerCitywideTotal > 0 ? `#${ownerCitywideRank}` : '—'}
                </p>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Citywide rank ({ownerCitywideTotal || '—'} listed)
                </p>
              </div>
              <div className="p-4 rounded-lg text-center" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.05)'
              }}>
                <p className="text-2xl mb-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  {profileLoading ? '…' : ownerReviewCount}
                </p>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Nomz reviews
                </p>
              </div>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="mb-6 flex gap-2">
            <button
              onClick={() => setActiveTab('overview')}
              title="Overview"
              className="py-3 px-6 rounded-lg text-sm transition-all"
              style={{ 
                backgroundColor: activeTab === 'overview' ? '#E06E7F' : 'white',
                color: activeTab === 'overview' ? 'white' : '#666',
                border: activeTab === 'overview' ? 'none' : '2px solid rgba(224, 110, 127, 0.2)',
                fontFamily: 'Montserrat, sans-serif'
              }}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              title="Performance metrics"
              className="py-3 px-6 rounded-lg text-sm transition-all"
              style={{ 
                backgroundColor: activeTab === 'performance' ? '#E06E7F' : 'white',
                color: activeTab === 'performance' ? 'white' : '#666',
                border: activeTab === 'performance' ? 'none' : '2px solid rgba(224, 110, 127, 0.2)',
                fontFamily: 'Montserrat, sans-serif'
              }}
            >
              Performance Metrics
            </button>
            <button
              onClick={() => setActiveTab('details')}
              title="Business details"
              className="py-3 px-6 rounded-lg text-sm transition-all"
              style={{ 
                backgroundColor: activeTab === 'details' ? '#E06E7F' : 'white',
                color: activeTab === 'details' ? 'white' : '#666',
                border: activeTab === 'details' ? 'none' : '2px solid rgba(224, 110, 127, 0.2)',
                fontFamily: 'Montserrat, sans-serif'
              }}
            >
              Business Details
            </button>
            <button
              onClick={() => setActiveTab('reviews')}
              title="Reviews"
              className="py-3 px-6 rounded-lg text-sm transition-all"
              style={{ 
                backgroundColor: activeTab === 'reviews' ? '#E06E7F' : 'white',
                color: activeTab === 'reviews' ? 'white' : '#666',
                border: activeTab === 'reviews' ? 'none' : '2px solid rgba(224, 110, 127, 0.2)',
                fontFamily: 'Montserrat, sans-serif'
              }}
            >
              Reviews
            </button>
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {hasRestaurant ? (
              <div className="grid grid-cols-4 gap-4">
                <button
                  type="button"
                  onClick={onPhotoManagement}
                  className="p-5 rounded-lg text-center transition-all"
                  title="Manage photos"
                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    e.currentTarget.style.borderColor = '#E06E7F';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                    e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.2)';
                  }}
                >
                  <span className="text-3xl mb-2 block">📸</span>
                  <p className="text-sm" style={{ color: '#666' }}>Manage Profile</p>
                </button>
                <button
                  type="button"
                  onClick={() => setShowAvailabilitySettings(true)}
                  className="p-5 rounded-lg text-center transition-all"
                  title="Manage availability"
                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    e.currentTarget.style.borderColor = '#E06E7F';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                    e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.2)';
                  }}
                >
                  <span className="text-3xl mb-2 block">{isTemporarilyUnavailable ? '🟡' : '🟢'}</span>
                  <p className="text-sm" style={{ color: '#666' }}>Availability</p>
                </button>
                <button
                  type="button"
                  onClick={() => setShowCommunicationSettings(true)}
                  className="p-5 rounded-lg text-center transition-all"
                  title="Messaging settings"
                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    e.currentTarget.style.borderColor = '#E06E7F';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                    e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.2)';
                  }}
                >
                  <span className="text-3xl mb-2 block">⚙️</span>
                  <p className="text-sm" style={{ color: '#666' }}>Settings</p>
                </button>
                <button
                  type="button"
                  onClick={onManageActivation}
                  className="p-5 rounded-lg text-center transition-all"
                  title="Manage activation status"
                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    e.currentTarget.style.borderColor = '#E06E7F';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                    e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.2)';
                  }}
                >
                  <span className="text-3xl mb-2 block">⚡</span>
                  <p className="text-sm" style={{ color: '#666' }}>Activation</p>
                </button>
              </div>
              ) : (
                <p className="text-sm px-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  After you create a listing, you can manage photos, temporary availability, messaging settings, and activation here (same behavior as the Django restaurant dashboard links).
                </p>
              )}

              {/* Account Status */}
              <div className="p-6 rounded-lg" style={{ 
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h3 className="text-lg mb-4" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Account Status
                </h3>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Verification Status
                    </p>
                    <span className="inline-block py-1 px-3 rounded text-xs" style={{ 
                      backgroundColor: '#FFD700',
                      color: '#333',
                      fontFamily: 'Montserrat, sans-serif'
                    }}>
                      Pending approval
                    </span>
                  </div>
                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Profile Completion
                    </p>
                    <p className="text-sm" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#E06E7F'
                    }}>
                      65% Complete
                    </p>
                  </div>
                </div>
              </div>

              {/* Recent Activity */}
              <div className="p-6 rounded-lg" style={{ 
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h3 className="text-lg mb-4" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Recent Activity
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-3 p-3 rounded" style={{ backgroundColor: 'rgba(224, 110, 127, 0.05)' }}>
                    <span className="text-xl">✨</span>
                    <div className="flex-1">
                      <p className="text-sm mb-1" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        Account created successfully
                      </p>
                      <p className="text-xs" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        March 23, 2028
                      </p>
                    </div>
                  </div>
                  <div className="text-center py-8">
                    <p className="text-sm" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      No additional activity yet
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'performance' && (
            <div className="space-y-6">
              {/* Performance Overview */}
              <div className="grid grid-cols-2 gap-6">
                {/* Composite Score */}
                <div className="p-6 rounded-lg" style={{ 
                  backgroundColor: 'white',
                  border: '2px solid rgba(224, 110, 127, 0.1)'
                }}>
                  <h4 className="text-base mb-4" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#333'
                  }}>
                    Composite Score
                  </h4>
                  <p className="text-5xl mb-4" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#E06E7F'
                  }}>
                    {ownerCompositeScore != null ? ownerCompositeScore.toFixed(1) : '—'}<span className="text-2xl text-gray-400">/100</span>
                  </p>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      <span>Inspection-based rating:</span>
                      <span style={{ color: '#999' }}>{ownerInspectionRating != null ? ownerInspectionRating.toFixed(1) : '—'}</span>
                    </div>
                    <div className="flex justify-between text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      <span>Nomz reviews:</span>
                      <span style={{ color: '#999' }}>{ownerReviewCount}</span>
                    </div>
                  </div>
                </div>

                {/* Neighborhood Comparison */}
                <div className="p-6 rounded-lg" style={{ 
                  backgroundColor: 'white',
                  border: '2px solid rgba(224, 110, 127, 0.1)'
                }}>
                  <h4 className="text-base mb-4" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#333'
                  }}>
                    Citywide comparison
                  </h4>
                  <p className="text-xs mb-3" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#666'
                  }}>
                    Among active listings visible in search (same pool as map/search APIs).
                  </p>
                  <p className="text-4xl mb-4" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#E06E7F'
                  }}>
                    {ownerCitywideRank != null && ownerCitywideTotal > 0 ? (
                      <>#{ownerCitywideRank} <span className="text-xl text-gray-400">/ {ownerCitywideTotal}</span></>
                    ) : (
                      '—'
                    )}
                  </p>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      <span>Approx. percentile (by score rank):</span>
                      <span style={{ color: '#333' }}>
                        {ownerCitywideRank != null && ownerCitywideTotal > 1
                          ? `${Math.round(((ownerCitywideTotal - ownerCitywideRank + 1) / ownerCitywideTotal) * 1000) / 10}%`
                          : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Composite Factor Breakdown */}
              <div className="p-6 rounded-lg" style={{ 
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h4 className="text-lg mb-6" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Composite Factor Breakdown
                </h4>

                <div className="space-y-6">
                  {/* User Experience Signal */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        User Experience Signal (20%)
                      </p>
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#E06E7F'
                      }}>
                        80.0
                      </p>
                    </div>
                    <div className="w-full h-3 rounded-full mb-2" style={{ backgroundColor: 'rgba(224, 110, 127, 0.1)' }}>
                      <div className="h-full rounded-full" style={{ 
                        width: '80%',
                        backgroundColor: '#E06E7F'
                      }}></div>
                    </div>
                    <p className="text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      {ownerReviewCount} review(s) on Nomz (detail breakdown is maintained server-side for the composite score).
                    </p>
                  </div>

                  {/* Inspection & Hygiene */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        Inspection & Hygiene (20%)
                      </p>
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#E06E7F'
                      }}>
                        48.8
                      </p>
                    </div>
                    <div className="w-full h-3 rounded-full mb-2" style={{ backgroundColor: 'rgba(224, 110, 127, 0.1)' }}>
                      <div className="h-full rounded-full" style={{ 
                        width: '48.8%',
                        backgroundColor: '#E06E7F'
                      }}></div>
                    </div>
                    <p className="text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Grade N/A | Critical 0 | Non-critical 0 | Weighted contribution: 8.75
                    </p>
                  </div>

                  {/* Price-to-Value Fit */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        Price-to-Value Fit (20%)
                      </p>
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#E06E7F'
                      }}>
                        58.0
                      </p>
                    </div>
                    <div className="w-full h-3 rounded-full mb-2" style={{ backgroundColor: 'rgba(224, 110, 127, 0.1)' }}>
                      <div className="h-full rounded-full" style={{ 
                        width: '58%',
                        backgroundColor: '#E06E7F'
                      }}></div>
                    </div>
                    <p className="text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Derived from value ratings against expected value for price tier. | Weighted contribution: 11.60
                    </p>
                  </div>

                  {/* Operational Reliability */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        Operational Reliability (40%)
                      </p>
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#E06E7F'
                      }}>
                        93.0
                      </p>
                    </div>
                    <div className="w-full h-3 rounded-full mb-2" style={{ backgroundColor: 'rgba(224, 110, 127, 0.1)' }}>
                      <div className="h-full rounded-full" style={{ 
                        width: '93%',
                        backgroundColor: '#E06E7F'
                      }}></div>
                    </div>
                    <p className="text-xs" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Based on profile status, temporary availability, and metadata quality. | Weighted contribution: 37.20
                    </p>
                  </div>
                </div>
              </div>

              {/* Review & Historical Sections */}
              <div className="grid grid-cols-2 gap-6">
                <div className="p-6 rounded-lg" style={{ 
                  backgroundColor: 'white',
                  border: '2px solid rgba(224, 110, 127, 0.1)'
                }}>
                  <h4 className="text-base mb-4" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#333'
                  }}>
                    Review Parameter Breakdown
                  </h4>
                  <div className="text-center py-8">
                    <span className="text-4xl mb-3 block">📊</span>
                    <p className="text-sm" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      No published reviews yet
                    </p>
                  </div>
                </div>

                <div className="p-6 rounded-lg" style={{ 
                  backgroundColor: 'white',
                  border: '2px solid rgba(224, 110, 127, 0.1)'
                }}>
                  <h4 className="text-base mb-4" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#333'
                  }}>
                    Historical Trend
                  </h4>
                  <div className="text-center py-8">
                    <span className="text-4xl mb-3 block">📈</span>
                    <p className="text-sm" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      No historical data available
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'details' && (
            <div className="space-y-6">
              {/* Business Information */}
              <div className="p-6 rounded-lg" style={{ 
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#333'
                  }}>
                    Business Information
                  </h3>
                  {!isEditing && (
                    <div className="flex flex-wrap gap-2 justify-end">
                      {hasRestaurant && (
                        <button
                          type="button"
                          className="py-2 px-6 rounded-lg text-sm transition-all"
                          style={{ 
                            backgroundColor: '#E06E7F',
                            color: 'white',
                            fontFamily: 'Montserrat, sans-serif',
                            border: 'none',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#C85B6D'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#E06E7F'}
                          onClick={() => setIsEditing(true)}
                        >
                          Edit Information
                        </button>
                      )}
                      {onRestaurantForm && (
                        <button
                          type="button"
                          className="py-2 px-6 rounded-lg text-sm transition-all"
                          style={{ 
                            backgroundColor: 'white',
                            color: '#E06E7F',
                            fontFamily: 'Montserrat, sans-serif',
                            border: '2px solid rgba(224, 110, 127, 0.35)',
                            cursor: 'pointer',
                          }}
                          onClick={onRestaurantForm}
                        >
                          {hasRestaurant ? 'Full profile form' : 'Create profile'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-x-12 gap-y-6">
                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Business Name
                    </p>
                    {isEditing ? (
                      <input
                        type="text"
                        value={businessName}
                        onChange={(e) => setBusinessName(e.target.value)}
                        className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)', 
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'transparent',
                          color: '#333'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      />
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {businessName}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Username
                    </p>
                    <p className="text-sm py-2.5" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      {username}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Email
                    </p>
                    {isEditing ? (
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)', 
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'transparent',
                          color: '#333'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      />
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {email}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Phone
                    </p>
                    {isEditing ? (
                      <input
                        type="text"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="Enter phone number"
                        className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)', 
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'transparent',
                          color: '#333'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      />
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: phone ? '#333' : '#999'
                      }}>
                        {phone || "Not provided"}
                      </p>
                    )}
                  </div>

                  <div className="col-span-2">
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Address
                    </p>
                    {isEditing ? (
                      <input
                        type="text"
                        value={address}
                        onChange={(e) => setAddress(e.target.value)}
                        placeholder="Enter business address"
                        className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)', 
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'transparent',
                          color: '#333'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      />
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: address ? '#333' : '#999'
                      }}>
                        {address || "Not provided"}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Member Since
                    </p>
                    <p className="text-sm py-2.5" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      March 23, 2028
                    </p>
                  </div>
                </div>
              </div>

              {/* Restaurant Details */}
              <div className="p-6 rounded-lg" style={{ 
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h3 className="text-lg mb-6" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Restaurant Details
                </h3>
                <div className="grid grid-cols-2 gap-x-12 gap-y-6">
                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Cuisine Type
                    </p>
                    {isEditing ? (
                      <select
                        value={cuisineType}
                        onChange={(e) => {
                          const v = e.target.value;
                          setCuisineType(v);
                          setCuisineTypeLabel(cuisineChoices.find((c) => c.value === v)?.label ?? v);
                        }}
                        className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)', 
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'transparent',
                          color: '#333'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      >
                        {cuisineChoices.map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {cuisineTypeLabel || cuisineType}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Price Range
                    </p>
                    {isEditing ? (
                      <select
                        value={priceRange}
                        onChange={(e) => {
                          const v = e.target.value;
                          setPriceRange(v);
                          setPriceRangeLabel(priceChoices.find((p) => p.value === v)?.label ?? v);
                        }}
                        className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                        style={{ 
                          borderColor: 'rgba(224, 110, 127, 0.2)', 
                          fontFamily: 'Montserrat, sans-serif',
                          backgroundColor: 'transparent',
                          color: '#333'
                        }}
                        onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                      >
                        {priceChoices.map((p) => (
                          <option key={p.value} value={p.value}>{p.label}</option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {priceRangeLabel || priceRange}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Operating Hours
                    </p>
                    {isEditing ? (
                      <div className="flex flex-wrap gap-3 items-center">
                        <input
                          type="time"
                          value={hoursOpen.length > 5 ? hoursOpen.slice(0, 5) : hoursOpen}
                          onChange={(e) => {
                            const v = e.target.value;
                            setHoursOpen(v);
                            setOperatingHours(`${v} – ${hoursClose.length > 5 ? hoursClose.slice(0, 5) : hoursClose}`);
                          }}
                          className="px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                          style={{ 
                            borderColor: 'rgba(224, 110, 127, 0.2)', 
                            fontFamily: 'Montserrat, sans-serif',
                            backgroundColor: 'transparent',
                            color: '#333'
                          }}
                        />
                        <span className="text-xs" style={{ color: '#999' }}>to</span>
                        <input
                          type="time"
                          value={hoursClose.length > 5 ? hoursClose.slice(0, 5) : hoursClose}
                          onChange={(e) => {
                            const v = e.target.value;
                            setHoursClose(v);
                            setOperatingHours(`${hoursOpen.length > 5 ? hoursOpen.slice(0, 5) : hoursOpen} – ${v}`);
                          }}
                          className="px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                          style={{ 
                            borderColor: 'rgba(224, 110, 127, 0.2)', 
                            fontFamily: 'Montserrat, sans-serif',
                            backgroundColor: 'transparent',
                            color: '#333'
                          }}
                        />
                      </div>
                    ) : (
                      <p className="text-sm" style={{ 
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {operatingHours}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Messaging Hours
                    </p>
                    <p className="text-sm" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#333'
                    }}>
                      {messagingHours}
                    </p>
                    {isEditing && (
                      <p className="text-xs mt-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                        Edit response hours under Overview → Settings (same fields as the Django communication page).
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Account Status
                    </p>
                    <span className="inline-block py-1 px-3 rounded text-xs" style={{ 
                      backgroundColor: '#FFD700',
                      color: '#333',
                      fontFamily: 'Montserrat, sans-serif'
                    }}>
                      Pending approval
                    </span>
                  </div>

                  <div>
                    <p className="text-xs mb-2" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Account Type
                    </p>
                    <p className="text-sm py-2.5" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      Restaurant
                    </p>
                  </div>
                </div>
              </div>

              {profileSaveError && (
                <p className="text-sm px-2" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>
                  {profileSaveError}
                </p>
              )}
              {/* Action Buttons */}
              {isEditing && (
                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    disabled={savingProfile}
                    className="py-3 px-8 rounded-lg text-sm transition-all"
                    style={{ 
                      backgroundColor: 'white',
                      color: '#E06E7F',
                      border: '2px solid rgba(224, 110, 127, 0.3)',
                      fontFamily: 'Montserrat, sans-serif',
                      cursor: savingProfile ? 'wait' : 'pointer',
                      opacity: savingProfile ? 0.7 : 1,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                      e.currentTarget.style.borderColor = '#E06E7F';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'white';
                      e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.3)';
                    }}
                    onClick={handleCancel}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={savingProfile}
                    className="py-3 px-8 rounded-lg text-sm transition-all"
                    style={{ 
                      backgroundColor: '#E06E7F',
                      color: 'white',
                      fontFamily: 'Montserrat, sans-serif',
                      border: 'none',
                      cursor: savingProfile ? 'wait' : 'pointer',
                      opacity: savingProfile ? 0.7 : 1,
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#C85B6D'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#E06E7F'}
                    onClick={() => void handleSave()}
                  >
                    {savingProfile ? 'Saving…' : 'Save Changes'}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Reviews Tab */}
          {activeTab === 'reviews' && (
            <div className="space-y-4">
              <h3 className="text-lg" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>Customer Reviews</h3>
              {reviewsLoading ? (
                <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>Loading reviews…</p>
              ) : ownerReviews.length === 0 ? (
                <div className="rounded-lg p-6 text-center" style={{ backgroundColor: 'rgba(224,110,127,0.03)', border: '2px solid rgba(224,110,127,0.1)' }}>
                  <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>No reviews yet.</p>
                </div>
              ) : (
                ownerReviews.map((rev) => (
                  <div key={rev.id} className="rounded-lg p-5" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <strong className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>{rev.username}</strong>
                        <span style={{ color: '#eab308', letterSpacing: '1px' }}>
                          {'★'.repeat(rev.rating)}{'☆'.repeat(5 - rev.rating)}
                        </span>
                      </div>
                      <span className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                        {new Date(rev.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                    </div>
                    {rev.comment && (
                      <p className="text-sm mb-3" style={{ fontFamily: 'Montserrat, sans-serif', color: '#555', lineHeight: 1.6 }}>{rev.comment}</p>
                    )}
                    {rev.owner_response ? (
                      <div className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(224,110,127,0.05)', borderLeft: '3px solid #E06E7F' }}>
                        <p className="text-xs mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F', fontWeight: 600 }}>Your Response</p>
                        <p className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#555' }}>{rev.owner_response.response_text}</p>
                        <p className="text-xs mt-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                          Updated {new Date(rev.owner_response.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </p>
                        <button
                          className="text-xs mt-2 px-3 py-1 rounded transition-all"
                          style={{ color: '#E06E7F', border: '1px solid rgba(224,110,127,0.3)', backgroundColor: 'transparent', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                          onClick={() => { setRespondingToReviewId(rev.id); setResponseText(rev.owner_response!.response_text); setRespondError(null); }}
                        >
                          Edit Response
                        </button>
                      </div>
                    ) : (
                      respondingToReviewId !== rev.id && (
                        <button
                          className="text-xs px-3 py-1 rounded transition-all"
                          style={{ color: '#E06E7F', border: '1px solid rgba(224,110,127,0.3)', backgroundColor: 'transparent', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                          onClick={() => { setRespondingToReviewId(rev.id); setResponseText(""); setRespondError(null); }}
                        >
                          Respond
                        </button>
                      )
                    )}
                    {respondingToReviewId === rev.id && (
                      <div className="mt-3 space-y-2">
                        <textarea
                          value={responseText}
                          onChange={(e) => setResponseText(e.target.value)}
                          rows={3}
                          className="w-full p-3 rounded-lg text-sm"
                          style={{ fontFamily: 'Montserrat, sans-serif', border: '2px solid rgba(224,110,127,0.2)', outline: 'none' }}
                          placeholder="Thank the customer, clarify concerns, or explain next steps."
                        />
                        {respondError && <p className="text-xs" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>{respondError}</p>}
                        <div className="flex gap-2">
                          <button
                            disabled={respondSaving}
                            className="text-xs px-4 py-2 rounded text-white"
                            style={{ backgroundColor: '#E06E7F', border: 'none', cursor: respondSaving ? 'wait' : 'pointer', fontFamily: 'Montserrat, sans-serif', opacity: respondSaving ? 0.7 : 1 }}
                            onClick={() => void handleRespondToReview(rev.id)}
                          >
                            {respondSaving ? 'Saving…' : 'Submit Response'}
                          </button>
                          <button
                            disabled={respondSaving}
                            className="text-xs px-4 py-2 rounded"
                            style={{ backgroundColor: 'white', color: '#666', border: '1px solid rgba(224,110,127,0.2)', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                            onClick={() => { setRespondingToReviewId(null); setResponseText(""); setRespondError(null); }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <Footer />

      {/* Communication Settings Modal */}
      {showCommunicationSettings && (
        <div 
          className="fixed inset-0 flex items-center justify-center p-8"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 1000 }}
          onClick={() => setShowCommunicationSettings(false)}
        >
          <div 
            className="w-full max-w-4xl rounded-lg overflow-hidden"
            style={{ backgroundColor: 'white' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-6" style={{ backgroundColor: '#E06E7F' }}>
              <h2 className="text-xl flex items-center gap-2" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: 'white'
              }}>
                <span>📧</span> Communication Settings
              </h2>
            </div>

            {/* Content */}
            <div className="p-8">
              <p className="text-sm mb-6" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Control when and how diners can reach you through the Nomz messaging system.
              </p>

              {/* Status Banner */}
              <div className="mb-8 p-4 rounded-lg" style={{ 
                backgroundColor: messagingEnabled ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `2px solid ${messagingEnabled ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
              }}>
                <p className="text-sm flex items-center gap-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  <span>{messagingEnabled ? '✅' : '❌'}</span>
                  Messaging is currently <strong>{messagingEnabled ? 'Enabled' : 'Disabled'}</strong> 
                  {messagingEnabled ? ' — diners can send you messages.' : ' — diners cannot send you messages.'}
                </p>
              </div>

              {/* Messaging Toggle */}
              <div className="mb-8 p-6 rounded-lg" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.05)',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-base" style={{ 
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#333'
                  }}>
                    Messaging Toggle
                  </h3>
                  <button
                    onClick={() => setMessagingEnabled(!messagingEnabled)}
                    className="relative inline-block w-14 h-8 rounded-full transition-all"
                    style={{ 
                      backgroundColor: messagingEnabled ? '#E06E7F' : '#D1D5DB'
                    }}
                  >
                    <span
                      className="absolute top-1 left-1 w-6 h-6 bg-white rounded-full transition-all"
                      style={{ 
                        transform: messagingEnabled ? 'translateX(24px)' : 'translateX(0)'
                      }}
                    />
                  </button>
                </div>
                <p className="text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  When disabled, diners will not be able to send you new messages.
                </p>
              </div>

              {/* Response Hours */}
              <div className="mb-8">
                <h3 className="text-base mb-2" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Response Hours <span style={{ color: '#999' }}>(optional)</span>
                </h3>
                <p className="text-xs mb-4" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Let diners know what time window you typically respond. This is informational only.
                </p>

                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="text-xs mb-2 block" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      Response Hours Start
                    </label>
                    <input
                      type="text"
                      value={responseHoursStart}
                      onChange={(e) => setResponseHoursStart(e.target.value)}
                      placeholder="e.g. 11:00 AM or 11pm"
                      className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                      style={{ 
                        borderColor: 'rgba(224, 110, 127, 0.2)', 
                        fontFamily: 'Montserrat, sans-serif',
                        backgroundColor: 'transparent',
                        color: '#333'
                      }}
                      onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                      onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                    />
                    <p className="text-xs mt-1" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Earliest time you typically respond to messages (optional).
                    </p>
                  </div>

                  <div>
                    <label className="text-xs mb-2 block" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      Response Hours End
                    </label>
                    <input
                      type="text"
                      value={responseHoursEnd}
                      onChange={(e) => setResponseHoursEnd(e.target.value)}
                      placeholder="e.g. 4:00 PM or 4pm"
                      className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                      style={{ 
                        borderColor: 'rgba(224, 110, 127, 0.2)', 
                        fontFamily: 'Montserrat, sans-serif',
                        backgroundColor: 'transparent',
                        color: '#333'
                      }}
                      onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                      onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                    />
                    <p className="text-xs mt-1" style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Latest time you typically respond to messages (optional).
                    </p>
                  </div>
                </div>
              </div>

              {communicationSaveError && (
                <p className="text-sm mb-3" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>
                  {communicationSaveError}
                </p>
              )}
              <div className="flex justify-start gap-3">
                <button
                  type="button"
                  disabled={savingCommunication}
                  className="py-3 px-8 rounded-lg text-sm transition-all"
                  style={{ 
                    backgroundColor: '#E06E7F',
                    color: 'white',
                    fontFamily: 'Montserrat, sans-serif',
                    border: 'none',
                    cursor: savingCommunication ? 'wait' : 'pointer',
                    opacity: savingCommunication ? 0.7 : 1,
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#C85B6D'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#E06E7F'}
                  onClick={() => void saveCommunication()}
                >
                  {savingCommunication ? 'Saving…' : 'Save Settings'}
                </button>
                <button
                  type="button"
                  disabled={savingCommunication}
                  className="py-3 px-8 rounded-lg text-sm transition-all"
                  style={{
                    backgroundColor: 'white',
                    color: '#666',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    e.currentTarget.style.borderColor = '#E06E7F';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                    e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.2)';
                  }}
                  onClick={() => {
                    setCommunicationSaveError(null);
                    setShowCommunicationSettings(false);
                    void loadProfile();
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Availability Settings Modal */}
      {showAvailabilitySettings && (
        <div 
          className="fixed inset-0 flex items-center justify-center p-8"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 1000 }}
          onClick={() => setShowAvailabilitySettings(false)}
        >
          <div 
            className="w-full max-w-4xl rounded-lg overflow-hidden max-h-[90vh] flex flex-col"
            style={{ backgroundColor: 'white' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-6" style={{ backgroundColor: '#E06E7F' }}>
              <h2 className="text-xl" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: 'white'
              }}>
                Manage Restaurant Availability
              </h2>
            </div>

            {/* Content */}
            <div className="p-8 overflow-y-auto">
              <p className="text-sm mb-6" style={{ 
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Use this page to temporarily mark your restaurant as unavailable for a period of time. This allows you to inform customers of closures, renovations, or special events.
              </p>

              {/* Unavailable Toggle */}
              <div className="mb-6 p-6 rounded-lg" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.05)',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="unavailable-checkbox"
                    checked={isTemporarilyUnavailable}
                    onChange={(e) => setIsTemporarilyUnavailable(e.target.checked)}
                    className="w-5 h-5 rounded"
                    style={{ 
                      accentColor: '#E06E7F',
                      cursor: 'pointer'
                    }}
                  />
                  <label 
                    htmlFor="unavailable-checkbox"
                    className="text-base cursor-pointer"
                    style={{ 
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#333'
                    }}
                  >
                    Mark as Temporarily Unavailable
                  </label>
                </div>
                <p className="text-xs mt-2 ml-8" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Check this box if your restaurant is temporarily closed or unavailable.
                </p>
              </div>

              {/* Reason for Unavailability */}
              <div className="mb-6">
                <label className="text-sm mb-2 block" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Reason for Unavailability
                </label>
                <textarea
                  value={unavailabilityReason}
                  onChange={(e) => setUnavailabilityReason(e.target.value)}
                  placeholder="e.g., Renovations, Special Event, Staffing Issues..."
                  rows={4}
                  className="w-full px-4 py-3 border-2 rounded-lg focus:outline-none transition-all text-sm resize-none"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)', 
                    fontFamily: 'Montserrat, sans-serif',
                    backgroundColor: 'transparent',
                    color: '#333'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                />
                <p className="text-xs mt-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  This message will be displayed to customers.
                </p>
              </div>

              {/* Available Again On */}
              <div className="mb-8">
                <label className="text-sm mb-2 block" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Available Again On
                </label>
                <input
                  type="datetime-local"
                  value={availableAgainDate}
                  onChange={(e) => setAvailableAgainDate(e.target.value)}
                  className="w-full px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                  style={{ 
                    borderColor: 'rgba(224, 110, 127, 0.2)', 
                    fontFamily: 'Montserrat, sans-serif',
                    backgroundColor: 'transparent',
                    color: '#333'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#E06E7F'}
                  onBlur={(e) => e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)'}
                />
                <p className="text-xs mt-1" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  Select when your restaurant will be available again.
                </p>
              </div>

              {/* Common Reasons */}
              <div className="mb-8 p-6 rounded-lg" style={{ 
                backgroundColor: 'rgba(224, 110, 127, 0.03)',
                border: '1px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h3 className="text-sm mb-3" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Common Reasons for Unavailability:
                </h3>
                <ul className="space-y-1.5 text-xs" style={{ 
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666'
                }}>
                  <li>• Renovations and maintenance</li>
                  <li>• Equipment repairs or replacement</li>
                  <li>• Staff training or reorganization</li>
                  <li>• Special event or private catering</li>
                  <li>• Temporary staffing shortage</li>
                  <li>• Inventory replenishment</li>
                  <li>• Holiday or seasonal closure</li>
                </ul>
              </div>

              {availabilitySaveError && (
                <p className="text-sm mb-3" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>
                  {availabilitySaveError}
                </p>
              )}
              <div className="flex justify-start gap-3">
                <button
                  type="button"
                  disabled={savingAvailability}
                  className="py-3 px-8 rounded-lg text-sm transition-all"
                  style={{ 
                    backgroundColor: '#E06E7F',
                    color: 'white',
                    fontFamily: 'Montserrat, sans-serif',
                    border: 'none',
                    cursor: savingAvailability ? 'wait' : 'pointer',
                    opacity: savingAvailability ? 0.7 : 1,
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#C85B6D'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#E06E7F'}
                  onClick={() => void saveAvailability()}
                >
                  {savingAvailability ? 'Saving…' : 'Save Changes'}
                </button>
                <button
                  type="button"
                  disabled={savingAvailability}
                  className="py-3 px-8 rounded-lg text-sm transition-all"
                  style={{ 
                    backgroundColor: 'white',
                    color: '#666',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                    e.currentTarget.style.borderColor = '#E06E7F';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                    e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.2)';
                  }}
                  onClick={() => {
                    setAvailabilitySaveError(null);
                    setShowAvailabilitySettings(false);
                    void loadProfile();
                  }}
                >
                  Back to Profile
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}