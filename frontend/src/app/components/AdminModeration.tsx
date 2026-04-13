import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";

interface Report {
  id: number;
  date: string;
  reporter: string;
  reason: string;
  target: string;
  targetType: 'review' | 'user' | 'restaurant';
  details: string;
  severity: 'low' | 'medium' | 'high';
}

export function AdminModeration({
  onBack,
  initialReportId = null,
}: {
  onBack: () => void;
  /** Deep link from `/nomz-admin/moderation/resolve/:id/` — open resolve modal when the report is pending. */
  initialReportId?: number | null;
}) {
  const [reports, setReports] = useState<Report[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedReport, setSelectedReport] = useState<number | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [action, setAction] = useState('dismiss');
  const [notes, setNotes] = useState('');
  const openedInitialReportRef = useRef(false);

  useEffect(() => {
    openedInitialReportRef.current = false;
  }, [initialReportId]);

  const loadReports = useCallback(async () => {
    setLoadError(null);
    try {
      const r = await apiFetch("/api/admin/moderation/");
      if (!r.ok) {
        setLoadError(`Could not load moderation queue (${r.status}).`);
        setReports([]);
        return;
      }
      const data = await r.json();
      const pending = data.pending ?? [];
      setReports(
        pending.map(
          (row: {
            id: number;
            reason: string;
            details: string;
            reporter_username: string;
            created_at: string;
            review_id: number | null;
            reported_user_id: number | null;
          }) => {
            let target = "Unknown";
            let targetType: Report["targetType"] = "review";
            if (row.review_id) {
              target = `Review #${row.review_id}`;
              targetType = "review";
            } else if (row.reported_user_id) {
              target = `User id ${row.reported_user_id}`;
              targetType = "user";
            }
            return {
              id: row.id,
              date: new Date(row.created_at).toLocaleString(),
              reporter: row.reporter_username,
              reason: row.reason,
              target,
              targetType,
              details: row.details,
              severity: "medium" as const,
            };
          }
        )
      );
    } catch {
      setLoadError("Network error.");
      setReports([]);
    }
  }, []);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  useEffect(() => {
    if (openedInitialReportRef.current || initialReportId == null) return;
    if (loadError) return;
    const found = reports.some((r) => r.id === initialReportId);
    if (found) {
      openedInitialReportRef.current = true;
      setSelectedReport(initialReportId);
      setShowModal(true);
    }
  }, [reports, initialReportId, loadError]);

  const handleAction = (reportId: number) => {
    setSelectedReport(reportId);
    setShowModal(true);
  };

  const handleSubmitAction = async () => {
    if (selectedReport == null) return;
    try {
      let apiAction = "dismiss";
      if (action === "flag_fraud") apiAction = "flag_fraud";
      else if (action === "unflag") apiAction = "unflag";
      const r = await apiFetch(`/api/admin/moderation/reports/${selectedReport}/resolve/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: apiAction, moderator_note: notes }),
      });
      if (!r.ok) {
        setLoadError("Action failed.");
        return;
      }
      await loadReports();
    } catch {
      setLoadError("Network error.");
    }
    setShowModal(false);
    setAction('dismiss');
    setNotes('');
    setSelectedReport(null);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high':
        return '#D4183D';
      case 'medium':
        return '#E06E7F';
      default:
        return '#FFB6C1';
    }
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: '#FFF9F5' }}>
      {/* Navigation */}
      <nav className="w-full px-8 py-4 flex items-center gap-4 border-b" style={{ borderColor: 'rgba(224, 110, 127, 0.1)' }}>
        <button
          onClick={onBack}
          className="text-xl transition-all p-2 rounded-lg"
          title="Back"
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: '#E06E7F'
          }}
        >
          ←
        </button>
        <h1 className="text-2xl" style={{
          fontFamily: 'Montserrat, sans-serif',
          color: '#E06E7F'
        }}>
          Content Moderation
        </h1>
      </nav>

      {/* Main Content */}
      <main className="w-full py-8 px-8 flex-1">
        <div className="max-w-6xl mx-auto">
          {loadError && (
            <p className="text-sm mb-4" style={{ color: '#b91c1c' }}>{loadError}</p>
          )}
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl mb-2" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#E06E7F'
                }}>
                  Pending Reports
                </h2>
                <p className="text-sm" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#999'
                }}>
                  {reports.length} report(s) awaiting review
                </p>
              </div>
            </div>
          </div>

          {/* Reports Table */}
          {reports.length > 0 ? (
            <div className="space-y-4">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="p-6 rounded-lg"
                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.1)'
                  }}
                >
                  <div className="grid grid-cols-6 gap-4 items-center mb-4">
                    <div>
                      <p className="text-xs" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Date
                      </p>
                      <p className="text-sm" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {report.date}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Reporter
                      </p>
                      <p className="text-sm" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        @{report.reporter}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Reason
                      </p>
                      <span
                        className="text-xs px-3 py-1 rounded"
                        style={{
                          backgroundColor: 'rgba(224, 110, 127, 0.1)',
                          color: '#E06E7F',
                          fontFamily: 'Montserrat, sans-serif'
                        }}
                      >
                        {report.reason}
                      </span>
                    </div>
                    <div>
                      <p className="text-xs" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Severity
                      </p>
                      <span
                        className="text-xs px-3 py-1 rounded uppercase"
                        style={{
                          backgroundColor: getSeverityColor(report.severity),
                          color: 'white',
                          fontFamily: 'Montserrat, sans-serif'
                        }}
                      >
                        {report.severity}
                      </span>
                    </div>
                    <div className="col-span-2">
                      <p className="text-xs" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Target
                      </p>
                      <p className="text-sm" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {report.target}
                      </p>
                    </div>
                  </div>

                  <div className="mb-4 p-4 rounded" style={{
                    backgroundColor: 'rgba(224, 110, 127, 0.05)'
                  }}>
                    <p className="text-xs mb-2" style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Details
                    </p>
                    <p style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666',
                      fontSize: '14px'
                    }}>
                      {report.details}
                    </p>
                  </div>

                  <button
                    onClick={() => handleAction(report.id)}
                    title="Review and take action on this report"
                    className="px-6 py-2 rounded-lg transition-all text-sm"
                    style={{
                      backgroundColor: '#E06E7F',
                      color: 'white',
                      border: 'none',
                      cursor: 'pointer',
                      fontFamily: 'Montserrat, sans-serif'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#D85870'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#E06E7F'}
                  >
                    Take Action
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 px-8 rounded-lg" style={{
              backgroundColor: 'white',
              border: '2px solid rgba(224, 110, 127, 0.1)'
            }}>
              <span style={{ fontSize: '48px' }}>✓</span>
              <h3 className="mt-4 text-lg" style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#E06E7F'
              }}>
                All Clear!
              </h3>
              <p style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                No pending reports to review
              </p>
            </div>
          )}
        </div>
      </main>

      {/* Action Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4" style={{
            boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1)'
          }}>
            <h2 className="text-xl mb-6" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F'
            }}>
              Take Action on Report
            </h2>

            <div className="space-y-4 mb-6">
              <div>
                <label className="text-sm mb-2 block" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Action
                </label>
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="w-full px-4 py-2 border-2 rounded-lg"
                  style={{
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                >
                  <option value="dismiss">Dismiss Report (No action)</option>
                  <option value="flag_fraud">Flag as Fraudulent</option>
                  <option value="unflag">Unflag / clear flags</option>
                </select>
              </div>

              <div>
                <label className="text-sm mb-2 block" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Moderator Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Reason for this action..."
                  className="w-full px-4 py-2 border-2 rounded-lg"
                  rows={3}
                  style={{
                    borderColor: 'rgba(224, 110, 127, 0.2)',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowModal(false)}
                title="Cancel moderation action"
                className="flex-1 px-4 py-2 rounded-lg"
                style={{
                  backgroundColor: 'transparent',
                  color: '#E06E7F',
                  border: '2px solid #E06E7F',
                  cursor: 'pointer',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitAction}
                title="Confirm moderation action"
                className="flex-1 px-4 py-2 rounded-lg"
                style={{
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
