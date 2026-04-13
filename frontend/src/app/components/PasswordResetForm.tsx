import { useState } from 'react';
import { apiFetch } from '../api';

export function PasswordResetForm({ onBack, onSubmit }: { onBack: () => void; onSubmit: (email: string) => void }) {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email) {
      setError('Please enter your email address');
      return;
    }

    if (!email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setIsLoading(true);
    try {
      const r = await apiFetch('/api/auth/password-reset/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (r.ok) {
        onSubmit(email);
      } else {
        const data = await r.json().catch(() => ({}));
        setError(data.error || 'Failed to send reset email.');
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="size-full flex flex-col items-center justify-center" style={{ backgroundColor: '#FFF9F5' }}>
      <div className="w-full max-w-md px-8">
        {/* Card */}
        <div className="rounded-lg p-8" style={{
          backgroundColor: 'white',
          border: '2px solid rgba(224, 110, 127, 0.1)'
        }}>
          {/* Header */}
          <div className="mb-6">
            <h2 className="text-3xl mb-3" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F',
              fontWeight: '600'
            }}>
              Forgot password?
            </h2>
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#999',
              fontSize: '14px'
            }}>
              Enter your email and we'll send you a reset link.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#333',
                fontSize: '14px',
                fontWeight: '500'
              }}>
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your registered email"
                className="w-full mt-2 px-4 py-3 rounded-lg focus:outline-none transition-all"
                style={{
                  backgroundColor: '#FFF9F5',
                  border: '2px solid rgba(224, 110, 127, 0.1)',
                  fontFamily: 'Montserrat, sans-serif',
                  fontSize: '14px'
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.3)';
                  e.currentTarget.style.backgroundColor = 'white';
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
                  e.currentTarget.style.backgroundColor = '#FFF9F5';
                }}
              />
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg" style={{
                backgroundColor: 'rgba(212, 24, 61, 0.1)',
                border: '1px solid rgba(212, 24, 61, 0.2)'
              }}>
                <p style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#D4183D',
                  fontSize: '13px',
                  margin: '0'
                }}>
                  {error}
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-lg font-medium transition-all text-white"
              title="Send reset link"
              style={{
                backgroundColor: isLoading ? '#ccc' : '#E06E7F',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                fontFamily: 'Montserrat, sans-serif',
                fontSize: '14px',
                border: 'none'
              }}
              onMouseEnter={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.backgroundColor = '#d1596d';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.backgroundColor = '#E06E7F';
                  e.currentTarget.style.transform = 'translateY(0)';
                }
              }}
            >
              {isLoading ? 'Sending...' : 'Send reset link'}
            </button>
          </form>

          {/* Back Link */}
          <div className="text-center mt-4">
            <button
              onClick={onBack}
              className="text-sm transition-all p-1 rounded"
              title="Back to login"
              style={{
                color: '#999',
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontFamily: 'Montserrat, sans-serif',
                textDecoration: 'none'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#E06E7F';
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = '#999';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              Back to log in
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
