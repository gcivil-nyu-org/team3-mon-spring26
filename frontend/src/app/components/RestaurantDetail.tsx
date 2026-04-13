import { useEffect, useState } from 'react';
import { apiFetch } from '../api';
import { Footer } from './Footer';

interface OwnerResponse {
  response_text: string;
  responder_username: string;
  created_at: string;
  updated_at: string;
}

interface ReviewData {
  id: number;
  username: string;
  rating: number;
  food_quality_rating: number;
  service_quality_rating: number;
  ambience_rating: number;
  location_rating: number;
  value_rating: number;
  dietary_accommodation_rating: number;
  cleanliness_rating: number;
  comment: string;
  created_at: string;
  is_flagged: boolean;
  owner_response: OwnerResponse | null;
}

interface RestaurantData {
  id: number;
  name: string;
  cuisine: string;
  cuisine_tags: string[];
  neighborhood: string;
  address: string;
  description: string;
  phone: string;
  is_flagged: boolean;
  is_owner_flagged: boolean;
  owner_id: number | null;
  messaging_enabled: boolean;
  composite_score: number | null;
  grade: string;
  reviews: ReviewData[];
}

function Stars({ rating }: { rating: number }) {
  return (
    <span style={{ color: '#eab308', letterSpacing: '1px' }}>
      {'★'.repeat(rating)}{'☆'.repeat(5 - rating)}
    </span>
  );
}

export function RestaurantDetail({
  restaurantId,
  onBack,
  onWriteReview,
  onReportReview,
  onReportOwner,
  onStartConversation,
}: {
  restaurantId: number;
  onBack: () => void;
  onWriteReview: (restaurantId: number) => void;
  onReportReview?: (reviewId: number) => void;
  onReportOwner?: (userId: number) => void;
  onStartConversation?: (restaurantId: number, restaurantName: string) => void;
}) {
  const [data, setData] = useState<RestaurantData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionUserId, setSessionUserId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await apiFetch('/api/auth/session/');
        const d = await r.json();
        if (!cancelled && d.authenticated && typeof d.user_id === 'number') {
          setSessionUserId(d.user_id);
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await apiFetch(`/api/restaurants/${restaurantId}/`);
        if (!r.ok) { setError(`Error ${r.status}`); return; }
        const d = await r.json();
        if (!cancelled) setData(d);
      } catch {
        if (!cancelled) setError('Network error.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [restaurantId]);

  if (loading) {
    return (
      <div className="size-full flex items-center justify-center" style={{ backgroundColor: '#FFF9F5' }}>
        <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>Loading…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="size-full flex flex-col items-center justify-center gap-4" style={{ backgroundColor: '#FFF9F5' }}>
        <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#b91c1c' }}>{error || 'Restaurant not found.'}</p>
        <button onClick={onBack} style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
          ← Back
        </button>
      </div>
    );
  }

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      {/* Nav */}
      <nav className="w-full px-8 py-4 flex items-center gap-4">
        <button
          onClick={onBack}
          className="text-xl transition-all p-2 rounded-lg"
          title="Back"
          style={{ backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: '#E06E7F' }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
        >
          ←
        </button>
        <h1 className="text-2xl" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>nomz</h1>
      </nav>

      <main className="flex-1 w-full max-w-5xl mx-auto px-8 pb-8">
        {/* Flagging alerts */}
        {data.is_owner_flagged && (
          <div className="mb-4 p-4 rounded-lg" style={{ backgroundColor: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.2)' }}>
            <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#dc2626', fontSize: '14px', margin: 0 }}>
              ⚠️ <strong>Owner Flagged for Fraud</strong> — The owner of this account has been flagged for fraudulent activity. Proceed with caution.
            </p>
          </div>
        )}
        {data.is_flagged && !data.is_owner_flagged && (
          <div className="mb-4 p-4 rounded-lg" style={{ backgroundColor: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.2)' }}>
            <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#a16207', fontSize: '14px', margin: 0 }}>
              ⚠️ <strong>Profile Flagged</strong> — This restaurant has been flagged for suspicious activity. Proceed with caution.
            </p>
          </div>
        )}

        <div className="flex gap-8">
          {/* Left: details + reviews */}
          <div className="flex-1 min-w-0">
            {/* Restaurant Card */}
            <div className="rounded-lg p-6 mb-6" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
              <h2 className="text-2xl mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>{data.name}</h2>
              {data.cuisine && (
                <span className="inline-block px-3 py-1 rounded-full text-xs mb-3" style={{ backgroundColor: '#E06E7F', color: 'white', fontFamily: 'Montserrat, sans-serif' }}>
                  {data.cuisine}
                </span>
              )}
              {data.cuisine_tags.length > 0 && !data.cuisine && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {data.cuisine_tags.map((t) => (
                    <span key={t} className="inline-block px-2 py-0.5 rounded-full text-xs" style={{ backgroundColor: 'rgba(224,110,127,0.1)', color: '#E06E7F', fontFamily: 'Montserrat, sans-serif' }}>
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <p className="text-sm mb-3" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                📍 {data.neighborhood ? `${data.neighborhood} | ` : ''}{data.address}
              </p>
              {data.phone && <p className="text-sm mb-3" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>📞 {data.phone}</p>}
              {data.composite_score !== null && (
                <p className="text-sm mb-3" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Composite Score: <strong style={{ color: '#E06E7F' }}>{data.composite_score.toFixed(1)}</strong>
                  {data.grade ? ` · Grade: ${data.grade}` : ''}
                </p>
              )}
              {data.description && (
                <>
                  <hr style={{ border: 'none', borderTop: '1px solid rgba(224,110,127,0.1)', margin: '12px 0' }} />
                  <h5 className="text-sm mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333', fontWeight: 600 }}>Description</h5>
                  <p className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#555', lineHeight: 1.6 }}>{data.description}</p>
                </>
              )}
            </div>

            {/* Reviews header */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>Customer Reviews</h3>
              <button
                onClick={() => onWriteReview(data.id)}
                className="px-4 py-2 rounded-lg text-sm text-white transition-all"
                title="Write a Review"
                style={{ backgroundColor: '#E06E7F', border: 'none', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-1px)'}
                onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
              >
                Write a Review
              </button>
            </div>

            {/* Review list */}
            {data.reviews.length === 0 ? (
              <div className="rounded-lg p-6 text-center" style={{ backgroundColor: 'rgba(224,110,127,0.03)', border: '2px solid rgba(224,110,127,0.1)' }}>
                <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>No reviews yet. Be the first to review!</p>
              </div>
            ) : (
              data.reviews.map((review) => (
                <div key={review.id} className="rounded-lg p-5 mb-3" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <strong className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>{review.username}</strong>
                      <Stars rating={review.rating} />
                    </div>
                    <span className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                      {new Date(review.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  </div>
                  {review.comment && (
                    <p className="text-sm mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#555', lineHeight: 1.6 }}>{review.comment}</p>
                  )}
                  <p className="text-xs mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                    Food {review.food_quality_rating}/5 · Service {review.service_quality_rating}/5 · Ambience {review.ambience_rating}/5 · Location {review.location_rating}/5 · Value {review.value_rating}/5 · Dietary {review.dietary_accommodation_rating}/5 · Cleanliness {review.cleanliness_rating}/5
                  </p>
                  {review.owner_response && (
                    <div className="mt-3 p-3 rounded-lg" style={{ backgroundColor: 'rgba(224,110,127,0.05)', borderLeft: '3px solid #E06E7F' }}>
                      <p className="text-xs mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F', fontWeight: 600 }}>
                        Owner Response
                      </p>
                      <p className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#555', lineHeight: 1.6 }}>
                        {review.owner_response.response_text}
                      </p>
                      <p className="text-xs mt-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                        — {review.owner_response.responder_username}, {new Date(review.owner_response.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </p>
                    </div>
                  )}
                  {onReportReview && sessionUserId != null && data.owner_id === sessionUserId && (
                    <div className="flex justify-end">
                      <button
                        onClick={() => onReportReview(review.id)}
                        className="text-xs px-3 py-1 rounded transition-all"
                        title="Report this review"
                        style={{ color: '#dc2626', border: '1px solid rgba(220,38,38,0.2)', backgroundColor: 'transparent', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(220,38,38,0.05)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        🚩 Report
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Right sidebar */}
          <div className="w-64 flex-shrink-0">
            <div className="rounded-lg p-5 sticky top-4" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
              <h5 className="text-sm mb-3" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333', fontWeight: 600 }}>About this Restaurant</h5>
              <p className="text-xs mb-4" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>Verified restaurant on Nomz.</p>
              <hr style={{ border: 'none', borderTop: '1px solid rgba(224,110,127,0.1)', margin: '0 0 12px' }} />
              <div className="flex flex-col gap-2">
                {data.owner_id && data.messaging_enabled && (
                  <button
                    type="button"
                    onClick={() => onStartConversation?.(data.id, data.name)}
                    className="w-full py-2 rounded text-xs text-white"
                    title="Message this restaurant"
                    style={{ backgroundColor: '#E06E7F', border: 'none', cursor: onStartConversation ? 'pointer' : 'not-allowed', fontFamily: 'Montserrat, sans-serif', opacity: onStartConversation ? 1 : 0.6 }}
                    disabled={!onStartConversation}
                  >
                    ✉️ Message Restaurant
                  </button>
                )}
                {data.owner_id && !data.messaging_enabled && (
                  <button className="w-full py-2 rounded text-xs" style={{ backgroundColor: '#e5e7eb', border: 'none', cursor: 'not-allowed', fontFamily: 'Montserrat, sans-serif', color: '#999' }} disabled>
                    🔕 Messaging Unavailable
                  </button>
                )}
                {data.owner_id && onReportOwner ? (
                  <button
                    onClick={() => onReportOwner(data.owner_id!)}
                    className="w-full py-2 rounded text-xs transition-all"
                    title="Report owner or account"
                    style={{ border: '1px solid rgba(234,179,8,0.3)', backgroundColor: 'transparent', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif', color: '#a16207' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(234,179,8,0.05)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    Report Owner / Account
                  </button>
                ) : !data.owner_id && (
                  <button className="w-full py-2 rounded text-xs" style={{ backgroundColor: '#e5e7eb', border: 'none', cursor: 'not-allowed', fontFamily: 'Montserrat, sans-serif', color: '#999' }} disabled>
                    No owner info
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
