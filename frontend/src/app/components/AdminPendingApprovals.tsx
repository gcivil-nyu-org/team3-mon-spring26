import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

interface Approval {
  id: number;
  username: string;
  email: string;
  restaurantName: string;
  businessEmail: string;
  submitted: string;
  details: string;
  documents: string[];
}

export function AdminPendingApprovals({
  onBack
}: {
  onBack: () => void;
}) {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedApproval, setSelectedApproval] = useState<number | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [decision, setDecision] = useState('approve');
  const [reason, setReason] = useState('');

  const loadApprovals = useCallback(async () => {
    setLoadError(null);
    try {
      const r = await apiFetch("/api/admin/pending-approvals/");
      if (!r.ok) {
        setLoadError(`Could not load approvals (${r.status}).`);
        setApprovals([]);
        return;
      }
      const data = await r.json();
      const rows = data.results ?? [];
      setApprovals(
        rows.map(
          (row: {
            id: number;
            username: string;
            email: string;
            date_joined: string;
            restaurant_name: string;
            business_email: string;
            claim_details: string;
            has_pending_claim: boolean;
          }) => ({
            id: row.id,
            username: row.username,
            email: row.email,
            restaurantName: row.restaurant_name || "—",
            businessEmail: row.business_email || "—",
            submitted: new Date(row.date_joined).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            }),
            details: row.claim_details || "Pending restaurant account review.",
            documents: row.has_pending_claim ? ["Ownership claim submitted"] : ["Pending profile review"],
          })
        )
      );
    } catch {
      setLoadError("Network error.");
      setApprovals([]);
    }
  }, []);

  useEffect(() => {
    void loadApprovals();
  }, [loadApprovals]);

  const handleAction = (approvalId: number) => {
    setSelectedApproval(approvalId);
    setShowModal(true);
  };

  const handleSubmit = async () => {
    if (selectedApproval == null) return;
    try {
      const path =
        decision === "approve"
          ? `/api/admin/approve/${selectedApproval}/`
          : `/api/admin/reject/${selectedApproval}/`;
      const r = await apiFetch(path, { method: "POST" });
      if (!r.ok) {
        setLoadError("Action failed.");
        return;
      }
      await loadApprovals();
    } catch {
      setLoadError("Network error.");
    }
    setShowModal(false);
    setDecision('approve');
    setReason('');
    setSelectedApproval(null);
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
          Business Approvals
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
            <p className="text-sm" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#999'
            }}>
              {approvals.length} business registration(s) pending review
            </p>
          </div>

          {/* Approvals List */}
          {approvals.length > 0 ? (
            <div className="space-y-6">
              {approvals.map((approval) => (
                <div
                  key={approval.id}
                  className="p-6 rounded-lg"
                  style={{
                    backgroundColor: 'white',
                    border: '2px solid rgba(224, 110, 127, 0.1)'
                  }}
                >
                  {/* Header Row */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div>
                      <p className="text-xs mb-1" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Username
                      </p>
                      <p className="font-semibold" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#333'
                      }}>
                        {approval.username}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs mb-1" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Email
                      </p>
                      <p className="text-sm" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#666'
                      }}>
                        {approval.email}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs mb-1" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Submitted
                      </p>
                      <p className="text-sm" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#666'
                      }}>
                        {approval.submitted}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs mb-1" style={{
                        fontFamily: 'Montserrat, sans-serif',
                        color: '#999'
                      }}>
                        Status
                      </p>
                      <span
                        className="text-xs px-3 py-1 rounded inline-block"
                        style={{
                          backgroundColor: '#FFE5EC',
                          color: '#E06E7F',
                          fontFamily: 'Montserrat, sans-serif'
                        }}
                      >
                        Pending
                      </span>
                    </div>
                  </div>

                  {/* Restaurant Info */}
                  <div className="p-4 rounded mb-4" style={{
                    backgroundColor: 'rgba(224, 110, 127, 0.05)'
                  }}>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs mb-1" style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#999'
                        }}>
                          Restaurant Name
                        </p>
                        <p className="font-semibold" style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#333'
                        }}>
                          {approval.restaurantName}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs mb-1" style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#999'
                        }}>
                          Business Email
                        </p>
                        <p className="text-sm" style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#666'
                        }}>
                          {approval.businessEmail}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Details */}
                  <div className="mb-4">
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
                      {approval.details}
                    </p>
                  </div>

                  {/* Documents */}
                  <div className="mb-6">
                    <p className="text-xs mb-2" style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#999'
                    }}>
                      Submitted Documents
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {approval.documents.map((doc, idx) => (
                        <span
                          key={idx}
                          className="px-3 py-1 rounded text-xs"
                          style={{
                            backgroundColor: 'white',
                            border: '1px solid rgba(224, 110, 127, 0.3)',
                            color: '#E06E7F',
                            fontFamily: 'Montserrat, sans-serif'
                          }}
                        >
                          📄 {doc}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleAction(approval.id)}
                      title="Review and decide on this business registration"
                      className="flex-1 px-4 py-2 rounded-lg transition-all"
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
                      Review & Decide
                    </button>
                  </div>
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
                All Caught Up!
              </h3>
              <p style={{
                fontFamily: 'Montserrat, sans-serif',
                color: '#999'
              }}>
                No pending approvals to review
              </p>
            </div>
          )}
        </div>
      </main>

      {/* Decision Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
            <h2 className="text-xl mb-6" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F'
            }}>
              Approve or Reject
            </h2>

            <div className="space-y-4 mb-6">
              <div>
                <label className="text-sm mb-2 block" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  Decision
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="radio"
                      value="approve"
                      checked={decision === 'approve'}
                      onChange={(e) => setDecision(e.target.value)}
                      style={{ accentColor: '#E06E7F' }}
                    />
                    <span style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#333'
                    }}>
                      Approve Registration
                    </span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="radio"
                      value="reject"
                      checked={decision === 'reject'}
                      onChange={(e) => setDecision(e.target.value)}
                      style={{ accentColor: '#E06E7F' }}
                    />
                    <span style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#333'
                    }}>
                      Reject Registration
                    </span>
                  </label>
                </div>
              </div>

              <div>
                <label className="text-sm mb-2 block" style={{
                  fontFamily: 'Montserrat, sans-serif',
                  color: '#333'
                }}>
                  {decision === 'approve' ? 'Notes' : 'Rejection Reason'}
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={decision === 'approve' ? 'Optional notes...' : 'Why are you rejecting this?'}
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
                title="Cancel approval decision"
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
                onClick={handleSubmit}
                title="Submit approval decision"
                className="flex-1 px-4 py-2 rounded-lg"
                style={{
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                Submit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
