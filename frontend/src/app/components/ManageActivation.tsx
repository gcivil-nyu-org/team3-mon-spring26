import { useEffect, useState } from 'react';
import { apiFetch } from '../api';

export function ManageActivation({ onBack, isActive = true, onToggle }: { onBack: () => void; isActive?: boolean; onToggle?: (newStatus: boolean) => void }) {
  const [isRestaurantActive, setIsRestaurantActive] = useState(isActive);
  const [isSaving, setIsSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await apiFetch('/api/restaurant/activation/');
        if (!r.ok) return;
        const d = await r.json();
        if (!cancelled && typeof d.is_active === 'boolean') {
          setIsRestaurantActive(d.is_active);
        }
      } catch {
        /* demo fallback */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleToggle = () => {
    setIsRestaurantActive(!isRestaurantActive);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setLoadError(null);
    try {
      const r = await apiFetch('/api/restaurant/activation/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: isRestaurantActive }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setLoadError(typeof d.errors === 'object' ? 'Could not save.' : 'Could not save.');
        setIsSaving(false);
        return;
      }
      const d = await r.json();
      if (typeof d.is_active === 'boolean') {
        setIsRestaurantActive(d.is_active);
        onToggle?.(d.is_active);
      }
    } catch {
      setLoadError('Network error.');
    } finally {
      setIsSaving(false);
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
      </nav>

      {/* Main Content */}
      <main className="w-full py-8 px-8 flex-1">
        <div className="max-w-2xl mx-auto">
          {/* Card */}
          <div className="rounded-lg p-8" style={{
            backgroundColor: 'white',
            border: '2px solid rgba(224, 110, 127, 0.1)'
          }}>
            {/* Header */}
            <h2 className="text-3xl mb-2" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#333',
              fontWeight: '600'
            }}>
              Manage Profile Status
            </h2>
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#999',
              fontSize: '14px',
              marginBottom: '24px'
            }}>
              Control whether your restaurant profile is visible to customers. When your profile is deactivated, it will no longer appear in searches or recommendations.
            </p>

            {loadError && (
              <p className="text-sm mb-4" style={{ color: '#b91c1c' }}>{loadError}</p>
            )}

            <form onSubmit={handleSubmit}>
              {/* Toggle Switch Section */}
              <div className="mb-8 p-6 rounded-lg" style={{
                backgroundColor: '#FFF9F5',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <div className="flex items-center justify-between">
                  <div>
                    <label style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#333',
                      fontSize: '16px',
                      fontWeight: '500',
                      cursor: 'pointer'
                    }}>
                      Profile Status
                    </label>
                    <p style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999',
                      fontSize: '13px',
                      margin: '4px 0 0 0'
                    }}>
                      {isRestaurantActive ? 'Your profile is currently active' : 'Your profile is currently inactive'}
                    </p>
                  </div>

                  {/* Toggle Switch */}
                  <button
                    type="button"
                    onClick={handleToggle}
                    title="Toggle profile status"
                    className="relative w-16 h-8 rounded-full transition-all"
                    style={{
                      backgroundColor: isRestaurantActive ? '#4CAF50' : '#ccc',
                      border: 'none',
                      cursor: 'pointer'
                    }}
                  >
                    <div
                      className="absolute top-1 w-6 h-6 rounded-full bg-white transition-all"
                      style={{
                        left: isRestaurantActive ? '6px' : '2px'
                      }}
                    />
                  </button>
                </div>
              </div>

              {/* Information Box */}
              <div className="mb-8 p-6 rounded-lg" style={{
                backgroundColor: 'rgba(224, 110, 127, 0.05)',
                border: '2px solid rgba(224, 110, 127, 0.1)'
              }}>
                <h6 style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F',
                  fontSize: '15px',
                  fontWeight: '600',
                  marginBottom: '12px'
                }}>
                  What happens when you deactivate?
                </h6>
                <ul style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#666',
                  fontSize: '14px',
                  margin: '0',
                  paddingLeft: '20px'
                }}>
                  <li style={{ marginBottom: '8px' }}>Your profile will be hidden from customer searches</li>
                  <li style={{ marginBottom: '8px' }}>Customers cannot make reservations or orders</li>
                  <li style={{ marginBottom: '8px' }}>Your profile data is preserved and can be reactivated anytime</li>
                  <li>You can still log in and edit information while inactive</li>
                </ul>
              </div>

              {/* Buttons */}
              <div className="flex gap-4 justify-end">
                <button
                  type="button"
                  onClick={onBack}
                  className="px-6 py-3 rounded-lg transition-all"
                  title="Back to Profile"                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    color: '#E06E7F',
                    cursor: 'pointer',
                    fontFamily: 'Montserrat, sans-serif',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white';
                  }}
                >
                  Back to Profile
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-6 py-3 rounded-lg transition-all text-white"
                  title="Save profile status"
                  style={{
                    backgroundColor: isSaving ? '#ccc' : '#E06E7F',
                    border: 'none',
                    cursor: isSaving ? 'not-allowed' : 'pointer',
                    fontFamily: 'Montserrat, sans-serif',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}
                  onMouseEnter={(e) => {
                    if (!isSaving) {
                      e.currentTarget.style.backgroundColor = '#d1596d';
                      e.currentTarget.style.transform = 'translateY(-2px)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSaving) {
                      e.currentTarget.style.backgroundColor = '#E06E7F';
                      e.currentTarget.style.transform = 'translateY(0)';
                    }
                  }}
                >
                  {isSaving ? 'Saving...' : (isRestaurantActive ? 'Deactivate Profile' : 'Activate Profile')}
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
