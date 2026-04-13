import { useState } from 'react';
import { apiFetch } from '../api';
import { Footer } from './Footer';

const RATING_FIELDS = [
  { key: 'rating', label: 'Overall rating' },
  { key: 'food_quality_rating', label: 'Food quality' },
  { key: 'service_quality_rating', label: 'Service quality' },
  { key: 'ambience_rating', label: 'Ambience' },
  { key: 'location_rating', label: 'Location & accessibility' },
  { key: 'value_rating', label: 'Price-to-value' },
  { key: 'dietary_accommodation_rating', label: 'Dietary accommodation' },
  { key: 'cleanliness_rating', label: 'Cleanliness' },
] as const;

function StarSelector({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHover(star)}
          onMouseLeave={() => setHover(0)}
          title={`Rate ${star} star${star > 1 ? 's' : ''}`}
          style={{
            fontSize: '22px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: star <= (hover || value) ? '#eab308' : '#d1d5db',
            transition: 'color 0.15s',
          }}
        >
          ★
        </button>
      ))}
    </div>
  );
}

export function AddReview({
  restaurantId,
  restaurantName,
  onBack,
  onSuccess,
}: {
  restaurantId: number;
  restaurantName: string;
  onBack: () => void;
  onSuccess: () => void;
}) {
  const [ratings, setRatings] = useState<Record<string, number>>({
    rating: 5,
    food_quality_rating: 4,
    service_quality_rating: 4,
    ambience_rating: 4,
    location_rating: 4,
    value_rating: 4,
    dietary_accommodation_rating: 4,
    cleanliness_rating: 4,
  });
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [submitting, setSubmitting] = useState(false);

  const setRating = (key: string, val: number) => setRatings((prev) => ({ ...prev, [key]: val }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    setSubmitting(true);
    try {
      const r = await apiFetch(`/api/restaurants/${restaurantId}/review/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...ratings, comment }),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.success) {
        onSuccess();
        return;
      }
      if (data.errors) {
        setFieldErrors(data.errors);
        const allMsgs = Object.values(data.errors as Record<string, string[]>).flat().join(' ');
        setError(allMsgs);
      } else {
        setError(data.error || 'Failed to submit review.');
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

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

      <main className="flex-1 w-full max-w-2xl mx-auto px-8 pb-8">
        <div className="rounded-lg overflow-hidden" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
          {/* Header */}
          <div className="px-6 py-4" style={{ backgroundColor: '#E06E7F' }}>
            <h2 className="text-lg text-white" style={{ fontFamily: 'Montserrat, sans-serif', margin: 0 }}>
              Share your experience at {restaurantName}
            </h2>
          </div>

          {/* Body */}
          <div className="p-6">
            <p className="text-sm mb-5" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
              Please rate the restaurant across all categories. These scores strongly influence the composite score shown across Nomz.
            </p>

            {error && (
              <div className="mb-4 p-3 rounded-lg" style={{ backgroundColor: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.15)' }}>
                <p className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#dc2626', margin: 0 }}>{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {/* Rating fields */}
              <div className="flex flex-col gap-4 mb-5">
                {RATING_FIELDS.map(({ key, label }) => (
                  <div key={key} className="flex items-center justify-between">
                    <label className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333', fontWeight: 500 }}>
                      {label}
                    </label>
                    <StarSelector value={ratings[key]} onChange={(v) => setRating(key, v)} />
                    {fieldErrors[key] && (
                      <span className="text-xs ml-2" style={{ color: '#dc2626', fontFamily: 'Montserrat, sans-serif' }}>{fieldErrors[key].join(' ')}</span>
                    )}
                  </div>
                ))}
              </div>

              {/* Comment */}
              <div className="mb-5">
                <label className="block text-sm mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333', fontWeight: 500 }}>
                  Written review
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={4}
                  placeholder="Write your review here..."
                  className="w-full px-4 py-3 rounded-lg text-sm focus:outline-none transition-all"
                  style={{
                    backgroundColor: '#FFF9F5',
                    border: '2px solid rgba(224,110,127,0.1)',
                    fontFamily: 'Montserrat, sans-serif',
                    resize: 'vertical',
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = 'rgba(224,110,127,0.3)'; e.currentTarget.style.backgroundColor = 'white'; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(224,110,127,0.1)'; e.currentTarget.style.backgroundColor = '#FFF9F5'; }}
                />
              </div>

              {/* Buttons */}
              <div className="flex flex-col gap-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-3 rounded-lg text-white text-sm font-medium transition-all"
                  title="Post Review"
                  style={{ backgroundColor: submitting ? '#ccc' : '#E06E7F', border: 'none', cursor: submitting ? 'not-allowed' : 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                  onMouseEnter={(e) => { if (!submitting) e.currentTarget.style.transform = 'translateY(-1px)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
                >
                  {submitting ? 'Posting…' : 'Post Review'}
                </button>
                <button
                  type="button"
                  onClick={onBack}
                  className="w-full py-3 rounded-lg text-sm transition-all"
                  title="Cancel review"
                  style={{ backgroundColor: 'transparent', border: '2px solid rgba(224,110,127,0.2)', color: '#E06E7F', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224,110,127,0.1)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
