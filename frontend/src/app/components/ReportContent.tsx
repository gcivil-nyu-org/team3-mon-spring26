import { useState } from 'react';
import { apiFetch } from '../api';
import { Footer } from './Footer';

const REASON_OPTIONS = [
  { value: 'SPAM', label: 'Spam or misleading' },
  { value: 'FRAUD', label: 'Fraudulent activity' },
  { value: 'HARASSMENT', label: 'Harassment or hate speech' },
  { value: 'INAPPROPRIATE', label: 'Inappropriate content' },
  { value: 'OTHER', label: 'Other' },
];

export function ReportContent({
  contentType,
  contentId,
  onBack,
  onSuccess,
}: {
  contentType: 'review' | 'user';
  contentId: number;
  onBack: () => void;
  onSuccess: () => void;
}) {
  const [reason, setReason] = useState('SPAM');
  const [details, setDetails] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!details.trim()) { setError('Please provide details about your report.'); return; }
    setSubmitting(true);
    try {
      const r = await apiFetch('/api/report/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_type: contentType, content_id: contentId, reason, details }),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.success) { onSuccess(); return; }
      if (data.errors) {
        setError(Object.values(data.errors as Record<string, string[]>).flat().join(' '));
      } else {
        setError(data.error || 'Failed to submit report.');
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
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

      <main className="flex-1 w-full max-w-lg mx-auto px-8 pb-8">
        <div className="rounded-lg p-6" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
          <h2 className="text-xl mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F', fontWeight: 600 }}>
            Report {contentType === 'review' ? 'Review' : 'User'}
          </h2>
          <p className="text-sm mb-5" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
            Your report will be reviewed by our moderation team.
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg" style={{ backgroundColor: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.15)' }}>
              <p className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#dc2626', margin: 0 }}>{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333', fontWeight: 500 }}>Reason</label>
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="w-full px-4 py-3 rounded-lg text-sm focus:outline-none transition-all"
                style={{ backgroundColor: '#FFF9F5', border: '2px solid rgba(224,110,127,0.1)', fontFamily: 'Montserrat, sans-serif' }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(224,110,127,0.3)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(224,110,127,0.1)'}
              >
                {REASON_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="mb-5">
              <label className="block text-sm mb-2" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333', fontWeight: 500 }}>Details</label>
              <textarea
                value={details}
                onChange={(e) => setDetails(e.target.value)}
                rows={4}
                placeholder="Provide more details about why you are reporting this..."
                className="w-full px-4 py-3 rounded-lg text-sm focus:outline-none transition-all"
                style={{ backgroundColor: '#FFF9F5', border: '2px solid rgba(224,110,127,0.1)', fontFamily: 'Montserrat, sans-serif', resize: 'vertical' }}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'rgba(224,110,127,0.3)'; e.currentTarget.style.backgroundColor = 'white'; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(224,110,127,0.1)'; e.currentTarget.style.backgroundColor = '#FFF9F5'; }}
              />
            </div>

            <div className="flex flex-col gap-2">
              <button
                type="submit"
                disabled={submitting}
                title="Submit content report"
                className="w-full py-3 rounded-lg text-white text-sm font-medium transition-all"
                style={{ backgroundColor: submitting ? '#ccc' : '#dc2626', border: 'none', cursor: submitting ? 'not-allowed' : 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                {submitting ? 'Submitting…' : 'Submit Report'}
              </button>
              <button
                type="button"
                onClick={onBack}
                title="Cancel report"
                className="w-full py-3 rounded-lg text-sm transition-all"
                style={{ backgroundColor: 'transparent', border: '2px solid rgba(224,110,127,0.2)', color: '#666', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </main>

      <Footer />
    </div>
  );
}
