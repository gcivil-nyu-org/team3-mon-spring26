import { useState } from 'react';
import { apiFetch } from '../api';

export function PasswordResetConfirm({ onBack, onSubmit, isValidLink: initialValidLink = true, uid, token: resetToken }: { onBack: () => void; onSubmit: () => void; isValidLink?: boolean; uid?: string; token?: string }) {
  const [password1, setPassword1] = useState('');
  const [password2, setPassword2] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword1, setShowPassword1] = useState(false);
  const [showPassword2, setShowPassword2] = useState(false);
  const [isValidLink, setIsValidLink] = useState(initialValidLink);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!password1 || !password2) {
      setError('Please fill in all fields');
      return;
    }

    if (password1.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (password1 !== password2) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);
    try {
      const r = await apiFetch('/api/auth/password-reset/confirm/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid, token: resetToken, new_password1: password1, new_password2: password2 }),
      });
      const data = await r.json().catch(() => ({}));
      if (r.ok && data.success) {
        onSubmit();
      } else if (data.expired) {
        setIsValidLink(false);
      } else if (data.errors) {
        const msgs = Object.values(data.errors as Record<string, string[]>).flat().join(' ');
        setError(msgs);
      } else {
        setError(data.error || 'Failed to reset password.');
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isValidLink) {
    return (
      <div className="size-full flex flex-col items-center justify-center" style={{ backgroundColor: '#FFF9F5' }}>
        <div className="w-full max-w-md px-8">
          <div className="rounded-lg p-8 text-center" style={{
            backgroundColor: 'white',
            border: '2px solid rgba(224, 110, 127, 0.1)'
          }}>
            <div className="mb-6 text-5xl">
              ⚠️
            </div>

            <h2 className="text-3xl mb-4" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F',
              fontWeight: '600'
            }}>
              Link Expired
            </h2>

            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#666',
              fontSize: '14px',
              marginBottom: '24px'
            }}>
              The reset link is invalid or has expired. Please request a new one.
            </p>

            <button
              onClick={onBack}
              className="w-full py-3 rounded-lg font-medium transition-all text-white"
              title="Request new reset link"
              style={{
                backgroundColor: '#E06E7F',
                cursor: 'pointer',
                fontFamily: 'Montserrat, sans-serif',
                fontSize: '14px',
                border: 'none'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#d1596d';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#E06E7F';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              Request new link
            </button>
          </div>
        </div>
      </div>
    );
  }

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
              Set new password
            </h2>
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#999',
              fontSize: '13px'
            }}>
              Enter your new password below
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {/* Password 1 */}
            <div className="mb-4">
              <label style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#333',
                fontSize: '14px',
                fontWeight: '500'
              }}>
                New password
              </label>
              <div className="relative mt-2">
                <input
                  type={showPassword1 ? 'text' : 'password'}
                  value={password1}
                  onChange={(e) => setPassword1(e.target.value)}
                  placeholder="Enter new password"
                  className="w-full px-4 py-3 rounded-lg focus:outline-none transition-all pr-10"
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
                <button
                  type="button"
                  onClick={() => setShowPassword1(!showPassword1)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-lg"
                  title="Toggle password visibility"
                  style={{ backgroundColor: 'transparent', border: 'none', cursor: 'pointer' }}
                >
                  {showPassword1 ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
              <p style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999',
                fontSize: '12px',
                marginTop: '6px'
              }}>
                At least 8 characters
              </p>
            </div>

            {/* Password 2 */}
            <div className="mb-4">
              <label style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#333',
                fontSize: '14px',
                fontWeight: '500'
              }}>
                Confirm new password
              </label>
              <div className="relative mt-2">
                <input
                  type={showPassword2 ? 'text' : 'password'}
                  value={password2}
                  onChange={(e) => setPassword2(e.target.value)}
                  placeholder="Confirm new password"
                  className="w-full px-4 py-3 rounded-lg focus:outline-none transition-all pr-10"
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
                <button
                  type="button"
                  onClick={() => setShowPassword2(!showPassword2)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-lg"
                  title="Toggle password visibility"
                  style={{ backgroundColor: 'transparent', border: 'none', cursor: 'pointer' }}
                >
                  {showPassword2 ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
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
              title="Change password"
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
              {isLoading ? 'Changing...' : 'Change password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
