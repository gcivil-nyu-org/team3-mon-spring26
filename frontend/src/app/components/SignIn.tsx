import { useEffect, useState } from 'react';
import { Footer } from './Footer';
import { apiFetch } from '../api';

export function SignIn({
  onBackClick,
  onSignIn,
  onForgotPassword,
  onTwoFactorRequired,
  onSignUp,
  adminPortal = false,
}: {
  onBackClick: () => void;
  onSignIn: (accountType: 'diner' | 'restaurant' | 'admin', username: string) => void;
  onForgotPassword?: () => void;
  onTwoFactorRequired?: () => void;
  onSignUp?: () => void;
  /** From URL `?admin` — show security code and POST /api/auth/admin-login/ (AdminLoginForm parity). */
  adminPortal?: boolean;
}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [securityCode, setSecurityCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (adminPortal) {
      setUsername((u) => (u === '' ? 'admin' : u));
    }
  }, [adminPortal]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const u = username.trim();
    if (!u || !password) {
      setError('Enter username and password.');
      return;
    }
    if (adminPortal && !securityCode.trim()) {
      setError('Enter the administrative security code.');
      return;
    }
    setLoading(true);
    try {
      if (adminPortal) {
        const r = await apiFetch('/api/auth/admin-login/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: u,
            password,
            security_code: securityCode,
          }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
          const msg =
            typeof data.error === 'string'
              ? data.error
              : Array.isArray(data.errors?.__all__) && data.errors.__all__[0]
                ? String(data.errors.__all__[0])
                : 'Admin sign-in failed.';
          setError(msg);
          return;
        }
        onSignIn('admin', typeof data.username === 'string' ? data.username : u);
        return;
      }

      const r = await apiFetch('/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(typeof data.error === 'string' ? data.error : 'Login failed.');
        return;
      }
      if (data.requires_2fa) {
        onTwoFactorRequired?.();
        return;
      }
      let role: 'diner' | 'restaurant' | 'admin' = 'diner';
      if (data.is_staff) role = 'admin';
      else if (data.role === 'restaurant') role = 'restaurant';
      onSignIn(role, data.username);
    } catch {
      setError('Network error. Is Django running (and VITE_API_BASE_URL / proxy set)?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      <button
        onClick={onBackClick}
        className="absolute top-8 left-8 p-2 rounded-lg transition-all hover:bg-opacity-10"
        style={{ color: '#E06E7F' }}
        title="Back"
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
        aria-label="Go back"
        type="button"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
      </button>

      <div className="flex-1 flex flex-col items-center justify-center px-8 py-20">
        <h1 className="text-3xl mb-10" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>
          nomz
        </h1>

        <div className="w-full max-w-md">
          <h2
            className={`text-xl text-center ${adminPortal ? 'mb-2' : 'mb-6'}`}
            style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}
          >
            {adminPortal ? 'Admin sign-in' : 'Log In to Your Account'}
          </h2>
          {adminPortal && (
            <p className="text-xs mb-6 text-center" style={{ fontFamily: 'Montserrat, sans-serif', color: '#888' }}>
              Security code required (same as Django <code style={{ color: '#666' }}>/admin-login/</code>). After this once, you can
              use regular Log In with the same username and password.
            </p>
          )}

          {error && (
            <p className="text-sm mb-4 text-center" style={{ fontFamily: 'Montserrat, sans-serif', color: '#b91c1c' }}>
              {error}
            </p>
          )}

          <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-2">
              <label htmlFor="username" className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                Username
              </label>
              <input
                type="text"
                id="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                style={{
                  borderColor: 'rgba(224, 110, 127, 0.2)',
                  fontFamily: 'Montserrat, sans-serif',
                  backgroundColor: 'transparent',
                }}
                onFocus={(e) => (e.target.style.borderColor = '#E06E7F')}
                onBlur={(e) => (e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)')}
                placeholder="Enter your username"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="password" className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                Password
              </label>
              <input
                type="password"
                id="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                style={{
                  borderColor: 'rgba(224, 110, 127, 0.2)',
                  fontFamily: 'Montserrat, sans-serif',
                  backgroundColor: 'transparent',
                }}
                onFocus={(e) => (e.target.style.borderColor = '#E06E7F')}
                onBlur={(e) => (e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)')}
                placeholder="Enter your password"
              />
            </div>

            {adminPortal && (
              <div className="flex flex-col gap-2">
                <label htmlFor="security_code" className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
                  Administrative security code
                </label>
                <input
                  type="password"
                  id="security_code"
                  autoComplete="off"
                  value={securityCode}
                  onChange={(e) => setSecurityCode(e.target.value)}
                  className="px-4 py-2.5 border-2 rounded-lg focus:outline-none transition-all text-sm"
                  style={{
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif',
                    backgroundColor: 'transparent',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = '#E06E7F')}
                  onBlur={(e) => (e.target.style.borderColor = 'rgba(224, 110, 127, 0.2)')}
                  placeholder="ADMIN_SECURITY_CODE from server .env"
                />
              </div>
            )}

            <div className="flex justify-end">
              {!adminPortal && onForgotPassword && (
                <button
                  type="button"
                  onClick={onForgotPassword}
                  className="text-xs transition-all p-1 rounded"
                  title="Forgot password?"
                  style={{
                    color: '#999',
                    backgroundColor: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'Montserrat, sans-serif',
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
                  Forgot password?
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="py-2.5 rounded-lg text-white transition-all text-sm"
              title="Log In"
              style={{
                backgroundColor: loading ? '#ccc' : '#E06E7F',
                fontFamily: 'Montserrat, sans-serif',
                border: 'none',
                cursor: loading ? 'wait' : 'pointer',
              }}
              onMouseEnter={(e) => !loading && (e.currentTarget.style.transform = 'translateY(-2px)')}
              onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
            >
              {loading ? 'Signing in…' : 'Log In'}
            </button>
          </form>

          {!adminPortal && (
            <p className="text-center text-xs mt-6" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
              Don&apos;t have an account?{' '}
              <span className="cursor-pointer transition-all" style={{ color: '#E06E7F' }} onClick={onSignUp} title="Sign up for a new account">
                Sign up
              </span>
            </p>
          )}
        </div>
      </div>

      <Footer />
    </div>
  );
}
