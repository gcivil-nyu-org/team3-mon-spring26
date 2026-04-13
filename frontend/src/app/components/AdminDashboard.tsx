import { useEffect, useState } from "react";
import { Footer } from "./Footer";
import { apiFetch } from "../api";

interface ScoreAnomaly {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  anomaly_type: string;
  severity: string;
  created_at: string;
  is_resolved: boolean;
  resolved_by: string | null;
}

export function AdminDashboard({ 
  onLogout, 
  onNavigateMap,
  onViewModeration, 
  onViewPendingApprovals, 
  onViewPendingUsers,
  onViewLogs,
  onViewApprovedAccounts,
  onViewRejectedAccounts,
}: { 
  onLogout: () => void; 
  onNavigateMap: () => void;
  onViewModeration: () => void; 
  onViewPendingApprovals: () => void; 
  onViewPendingUsers: () => void;
  onViewLogs: () => void;
  onViewApprovedAccounts: () => void;
  onViewRejectedAccounts: () => void;
}) {
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalRestaurants: 0,
    pendingReports: 0,
    pendingApprovals: 0,
    suspiciousAccounts: 0,
    flaggedContent: 0,
  });

  // Score recalculation
  const [recalcId, setRecalcId] = useState("");
  const [recalcName, setRecalcName] = useState("");
  const [recalcLoading, setRecalcLoading] = useState(false);
  const [recalcMsg, setRecalcMsg] = useState<string | null>(null);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  // Score anomalies
  const [anomalies, setAnomalies] = useState<ScoreAnomaly[]>([]);
  const [anomaliesLoading, setAnomaliesLoading] = useState(false);
  const [showAnomalies, setShowAnomalies] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await apiFetch("/api/admin/dashboard-summary/");
        if (!r.ok) return;
        const d = await r.json();
        if (cancelled) return;
        setStats({
          totalUsers: d.total_users ?? 0,
          totalRestaurants: d.total_restaurants ?? 0,
          pendingReports: d.pending_reports ?? 0,
          pendingApprovals: d.pending_approvals ?? 0,
          suspiciousAccounts: d.suspicious_accounts ?? 0,
          flaggedContent: d.flagged_content ?? 0,
        });
      } catch {
        /* keep zeros */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRecalculate = async () => {
    setRecalcLoading(true);
    setRecalcMsg(null);
    setRecalcError(null);
    try {
      const body: Record<string, string> = {};
      if (recalcId.trim()) body.restaurant_id = recalcId.trim();
      else if (recalcName.trim()) body.restaurant_name = recalcName.trim();
      const r = await apiFetch("/api/admin/recalculate-scores/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setRecalcError(d.error || "Failed to recalculate."); return; }
      setRecalcMsg(`Updated ${d.updated}/${d.total} restaurant(s). ${d.anomaly_count} anomaly flag(s) detected.`);
      setRecalcId("");
      setRecalcName("");
    } catch { setRecalcError("Network error."); } finally { setRecalcLoading(false); }
  };

  const loadAnomalies = async () => {
    setAnomaliesLoading(true);
    try {
      const r = await apiFetch("/api/admin/score-anomalies/");
      if (!r.ok) return;
      const d = await r.json();
      setAnomalies(Array.isArray(d.anomalies) ? d.anomalies : []);
    } catch { /* ignore */ } finally { setAnomaliesLoading(false); }
  };

  const resolveAnomaly = async (id: number) => {
    try {
      const r = await apiFetch(`/api/admin/score-anomalies/${id}/resolve/`, { method: "POST", headers: { "Content-Type": "application/json" } });
      if (r.ok) {
        setAnomalies((prev) => prev.map((a) => a.id === id ? { ...a, is_resolved: true } : a));
      }
    } catch { /* ignore */ }
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      {/* Navigation Bar */}
      <nav className="w-full px-8 py-4 flex items-center justify-between">
        <h1 className="text-2xl" style={{
          fontFamily: 'Montserrat, sans-serif',
          color: '#E06E7F'
        }}>
          nomz Admin
        </h1>

        <div className="flex items-center gap-4">
          <button
            onClick={onNavigateMap}
            className="text-xl transition-all p-2 rounded-lg"
            title="Map"
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            style={{
              backgroundColor: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#E06E7F'
            }}
          >
            🗺️
          </button>

          <button
            onClick={onLogout}
          className="text-xl transition-all p-2 rounded-lg"
          title="Logout"
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
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
          {/* Page Title */}
          <div className="mb-10">
            <h2 className="text-3xl mb-2" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F'
            }}>
              Admin Dashboard
            </h2>
            <p className="text-sm" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#999'
            }}>
              Welcome back! Here's what's happening on your platform.
            </p>
          </div>

          {/* Quick Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-10">
            {/* Total Users */}
            <div className="p-6 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <span style={{ fontSize: '28px' }}>👥</span>
                <span className="text-sm" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999'
                }}>
                  Total
                </span>
              </div>
              <p className="text-4xl font-bold mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                {stats.totalUsers}
              </p>
              <p className="text-xs" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                Active Users
              </p>
            </div>

            {/* Total Restaurants */}
            <div className="p-6 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <span style={{ fontSize: '28px' }}>🍽️</span>
                <span className="text-sm" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999'
                }}>
                  Listed
                </span>
              </div>
              <p className="text-4xl font-bold mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                {stats.totalRestaurants}
              </p>
              <p className="text-xs" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                Restaurants
              </p>
            </div>

            {/* Pending Approvals */}
            <div className="p-6 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <span style={{ fontSize: '28px' }}>⏳</span>
                <span className="text-sm" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999',
                  backgroundColor: '#FFE5EC',
                  padding: '4px 8px',
                  borderRadius: '4px'
                }}>
                  Urgent
                </span>
              </div>
              <p className="text-4xl font-bold mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                {stats.pendingApprovals}
              </p>
              <p className="text-xs" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                Pending Approvals
              </p>
            </div>

            {/* Pending Reports */}
            <div className="p-6 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <span style={{ fontSize: '28px' }}>🚨</span>
              </div>
              <p className="text-4xl font-bold mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                {stats.pendingReports}
              </p>
              <p className="text-xs" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                Content Reports
              </p>
            </div>

            {/* Suspicious Accounts */}
            <div className="p-6 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <span style={{ fontSize: '28px' }}>⚠️</span>
              </div>
              <p className="text-4xl font-bold mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                {stats.suspiciousAccounts}
              </p>
              <p className="text-xs" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                Suspicious Accounts
              </p>
            </div>

            {/* Flagged Content */}
            <div className="p-6 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <div className="flex items-center justify-between mb-4">
                <span style={{ fontSize: '28px' }}>🚩</span>
              </div>
              <p className="text-4xl font-bold mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                {stats.flaggedContent}
              </p>
              <p className="text-xs" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                Flagged Content
              </p>
            </div>
          </div>

          {/* Action Buttons Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Moderation */}
            <button
              onClick={onViewModeration}
              title="Review and moderate reported content"
              className="p-8 rounded-lg text-left transition-all"
              style={{
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                e.currentTarget.style.borderColor = '#E06E7F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
              }}
            >
              <h3 className="text-2xl mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                🔍 Content Moderation
              </h3>
              <p className="text-sm" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Review and moderate reported content and user behavior
              </p>
            </button>

            {/* Pending Approvals */}
            <button
              onClick={onViewPendingApprovals}
              title="Review pending restaurant registrations"
              className="p-8 rounded-lg text-left transition-all"
              style={{
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                e.currentTarget.style.borderColor = '#E06E7F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
              }}
            >
              <h3 className="text-2xl mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                ✅ Business Approvals
              </h3>
              <p className="text-sm" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Approve or reject pending restaurant registrations
              </p>
            </button>

            {/* Manage Users */}
            <button
              onClick={onViewPendingUsers}
              title="View and manage user accounts"
              className="p-8 rounded-lg text-left transition-all"
              style={{
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                e.currentTarget.style.borderColor = '#E06E7F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
              }}
            >
              <h3 className="text-2xl mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                👤 Manage Users
              </h3>
              <p className="text-sm" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                View and manage user accounts and permissions
              </p>
            </button>

            {/* Admin Logs */}
            <button
              onClick={onViewLogs}
              title="View system logs and admin activity"
              className="p-8 rounded-lg text-left transition-all"
              style={{
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                e.currentTarget.style.borderColor = '#E06E7F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
              }}
            >
              <h3 className="text-2xl mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                📋 Admin Logs
              </h3>
              <p className="text-sm" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                View system logs and admin activity history
              </p>
            </button>

            {/* Approved accounts (JSON + SPA; replaces nomz-admin/approved-accounts/ list for day-to-day use) */}
            <button
              type="button"
              onClick={onViewApprovedAccounts}
              title="View approved restaurant accounts"
              className="p-8 rounded-lg text-left transition-all"
              style={{
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                e.currentTarget.style.borderColor = '#E06E7F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
              }}
            >
              <h3 className="text-2xl mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                ✓ Approved businesses
              </h3>
              <p className="text-sm" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Restaurant accounts already approved; revoke if needed
              </p>
            </button>

            <button
              type="button"
              onClick={onViewRejectedAccounts}
              title="View rejected restaurant accounts"
              className="p-8 rounded-lg text-left transition-all"
              style={{
                backgroundColor: 'white',
                border: '2px solid rgba(224, 110, 127, 0.1)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)';
                e.currentTarget.style.borderColor = '#E06E7F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'white';
                e.currentTarget.style.borderColor = 'rgba(224, 110, 127, 0.1)';
              }}
            >
              <h3 className="text-2xl mb-2" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                ✕ Rejected businesses
              </h3>
              <p className="text-sm" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#666'
              }}>
                Denied or revoked accounts; approve again if appropriate
              </p>
            </button>
          </div>

          {/* Score Recalculation */}
          <div className="mt-10 p-6 rounded-lg" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
            <h3 className="text-lg mb-4" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>
              📊 Recalculate Composite Scores
            </h3>
            <p className="text-sm mb-4" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
              Recalculate scores for a specific restaurant or leave both fields empty to recalculate all.
            </p>
            <div className="flex gap-3 items-end flex-wrap mb-3">
              <div>
                <label className="block text-xs mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>Restaurant ID</label>
                <input
                  type="text" value={recalcId} onChange={(e) => setRecalcId(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm" style={{ border: '2px solid rgba(224,110,127,0.2)', fontFamily: 'Montserrat, sans-serif', width: '120px', outline: 'none' }}
                  placeholder="e.g. 42"
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>or Restaurant Name</label>
                <input
                  type="text" value={recalcName} onChange={(e) => setRecalcName(e.target.value)}
                  className="px-3 py-2 rounded-lg text-sm" style={{ border: '2px solid rgba(224,110,127,0.2)', fontFamily: 'Montserrat, sans-serif', width: '240px', outline: 'none' }}
                  placeholder="e.g. Sushi Palace"
                />
              </div>
              <button
                disabled={recalcLoading}
                onClick={() => void handleRecalculate()}
                title="Recalculate composite scores"
                className="px-6 py-2 rounded-lg text-sm text-white"
                style={{ backgroundColor: '#E06E7F', border: 'none', cursor: recalcLoading ? 'wait' : 'pointer', fontFamily: 'Montserrat, sans-serif', opacity: recalcLoading ? 0.7 : 1 }}
              >
                {recalcLoading ? 'Recalculating…' : 'Recalculate'}
              </button>
            </div>
            {recalcMsg && <p className="text-sm" style={{ color: '#16a34a', fontFamily: 'Montserrat, sans-serif' }}>{recalcMsg}</p>}
            {recalcError && <p className="text-sm" style={{ color: '#b91c1c', fontFamily: 'Montserrat, sans-serif' }}>{recalcError}</p>}
          </div>

          {/* Score Anomalies */}
          <div className="mt-6 p-6 rounded-lg" style={{ backgroundColor: 'white', border: '2px solid rgba(224,110,127,0.1)' }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg" style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>
                ⚡ Score Anomalies
              </h3>
              <button
                onClick={() => { setShowAnomalies(!showAnomalies); if (!showAnomalies) void loadAnomalies(); }}
                title="Toggle score anomalies view"
                className="px-4 py-2 rounded-lg text-sm"
                style={{ backgroundColor: showAnomalies ? '#E06E7F' : 'white', color: showAnomalies ? 'white' : '#E06E7F', border: showAnomalies ? 'none' : '2px solid rgba(224,110,127,0.2)', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
              >
                {showAnomalies ? 'Hide' : 'Show Anomalies'}
              </button>
            </div>
            {showAnomalies && (
              anomaliesLoading ? (
                <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#E06E7F' }}>Loading…</p>
              ) : anomalies.length === 0 ? (
                <p className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>No anomalies found.</p>
              ) : (
                <div className="space-y-2">
                  {anomalies.map((a) => (
                    <div key={a.id} className="flex items-center justify-between p-3 rounded-lg" style={{ backgroundColor: a.is_resolved ? 'rgba(22,163,74,0.05)' : 'rgba(234,179,8,0.05)', border: `1px solid ${a.is_resolved ? 'rgba(22,163,74,0.2)' : 'rgba(234,179,8,0.2)'}` }}>
                      <div>
                        <p className="text-sm" style={{ fontFamily: 'Montserrat, sans-serif', color: '#333' }}>
                          <strong>{a.restaurant_name}</strong> — {a.anomaly_type.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs" style={{ fontFamily: 'Montserrat, sans-serif', color: '#999' }}>
                          Severity: {a.severity} · {new Date(a.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                          {a.is_resolved && a.resolved_by ? ` · Resolved by ${a.resolved_by}` : ''}
                        </p>
                      </div>
                      {!a.is_resolved && (
                        <button
                          onClick={() => void resolveAnomaly(a.id)}
                          title="Mark this anomaly as resolved"
                          className="px-3 py-1 rounded text-xs text-white"
                          style={{ backgroundColor: '#16a34a', border: 'none', cursor: 'pointer', fontFamily: 'Montserrat, sans-serif' }}
                        >
                          Resolve
                        </button>
                      )}
                      {a.is_resolved && (
                        <span className="text-xs px-2 py-1 rounded" style={{ backgroundColor: 'rgba(22,163,74,0.1)', color: '#16a34a', fontFamily: 'Montserrat, sans-serif' }}>Resolved</span>
                      )}
                    </div>
                  ))}
                </div>
              )
            )}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
