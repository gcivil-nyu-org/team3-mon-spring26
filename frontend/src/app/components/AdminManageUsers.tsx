import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

interface User {
  id: number;
  username: string;
  email: string;
  accountType: 'diner' | 'restaurant';
  joinDate: string;
  status: 'active' | 'suspended' | 'flagged';
  reviews: number;
  suspiciousFlags: number;
}

export function AdminManageUsers({
  onBack
}: {
  onBack: () => void;
}) {
  const [users, setUsers] = useState<User[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedUser, setSelectedUser] = useState<number | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all');

  const loadUsers = useCallback(async () => {
    setLoadError(null);
    try {
      const r = await apiFetch("/api/admin/users/");
      if (!r.ok) {
        setLoadError(`Could not load users (${r.status}).`);
        setUsers([]);
        return;
      }
      const data = await r.json();
      const rows = data.results ?? [];
      setUsers(
        rows.map(
          (row: {
            id: number;
            username: string;
            email: string;
            role: string | null;
            is_active: boolean;
            date_joined: string;
            has_suspicious_activity?: boolean;
          }) => {
            const status: User["status"] = !row.is_active
              ? "suspended"
              : row.has_suspicious_activity
                ? "flagged"
                : "active";
            const accountType: User["accountType"] =
              row.role === "restaurant" ? "restaurant" : "diner";
            return {
              id: row.id,
              username: row.username,
              email: row.email,
              accountType,
              joinDate: new Date(row.date_joined).toLocaleDateString(),
              status,
              reviews: 0,
              suspiciousFlags: row.has_suspicious_activity ? 1 : 0,
            };
          }
        )
      );
    } catch {
      setLoadError("Network error.");
      setUsers([]);
    }
  }, []);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const filteredUsers = filterStatus === 'all' 
    ? users 
    : users.filter(u => u.status === filterStatus);

  const handleAction = (userId: number) => {
    setSelectedUser(userId);
    setShowModal(true);
  };

  const handleSubmitAction = async () => {
    if (selectedUser == null) return;
    try {
      const r = await apiFetch(`/api/admin/users/${selectedUser}/toggle-active/`, {
        method: "POST",
      });
      if (!r.ok) {
        setLoadError("Could not update user.");
        return;
      }
      await loadUsers();
    } catch {
      setLoadError("Network error.");
    }
    setShowModal(false);
    setSelectedUser(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return '#4CAF50';
      case 'flagged':
        return '#FFC107';
      case 'suspended':
        return '#D4183D';
      default:
        return '#999';
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
          Manage Users
        </h1>
      </nav>

      {/* Main Content */}
      <main className="w-full py-8 px-8 flex-1">
        <div className="max-w-6xl mx-auto">
          {loadError && (
            <p className="text-sm mb-4" style={{ color: '#b91c1c' }}>{loadError}</p>
          )}
          {/* Filters */}
          <div className="mb-8">
            <div className="flex gap-2">
              {['all', 'active', 'flagged', 'suspended'].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setFilterStatus(filter)}
                  title={`Filter by ${filter} status`}
                  className="px-4 py-2 rounded-lg transition-all text-sm"
                  style={{
                    backgroundColor: filterStatus === filter ? '#E06E7F' : 'white',
                    color: filterStatus === filter ? 'white' : '#E06E7F',
                    border: '2px solid rgba(224, 110, 127, 0.2)',
                    cursor: 'pointer',
                    fontFamily: 'Montserrat, sans-serif'
                  }}
                >
                  {filter.charAt(0).toUpperCase() + filter.slice(1)}
                </button>
              ))}
            </div>
            <p className="text-sm mt-4" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#999'
            }}>
              {filteredUsers.length} user(s) found
            </p>
          </div>

          {/* Users Table */}
          <div className="overflow-hidden rounded-lg border" style={{
            borderColor: 'rgba(224, 110, 127, 0.1)'
          }}>
            <table className="w-full" style={{
              backgroundColor: 'white'
            }}>
              <thead style={{
                backgroundColor: 'rgba(224, 110, 127, 0.05)'
              }}>
                <tr>
                  <th className="px-6 py-4 text-left text-xs" style={{
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#999'
                  }}>
                    Username
                  </th>
                  <th className="px-6 py-4 text-left text-xs" style={{
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#999'
                  }}>
                    Type
                  </th>
                  <th className="px-6 py-4 text-left text-xs" style={{
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#999'
                  }}>
                    Joined
                  </th>
                  <th className="px-6 py-4 text-left text-xs" style={{
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#999'
                  }}>
                    Activity
                  </th>
                  <th className="px-6 py-4 text-left text-xs" style={{
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#999'
                  }}>
                    Status
                  </th>
                  <th className="px-6 py-4 text-left text-xs" style={{
                    fontFamily: 'Montserrat, sans-serif',
                    color: '#999'
                  }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user) => (
                  <tr
                    key={user.id}
                    style={{
                      borderTop: '1px solid rgba(224, 110, 127, 0.1)'
                    }}
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#333',
                          fontWeight: '500'
                        }}>
                          @{user.username}
                        </p>
                        <p style={{
                          fontFamily: 'Montserrat, sans-serif',
                          color: '#999',
                          fontSize: '12px'
                        }}>
                          {user.email}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className="px-3 py-1 rounded text-xs"
                        style={{
                          backgroundColor: user.accountType === 'diner' ? 'rgba(224, 110, 127, 0.1)' : 'rgba(76, 175, 80, 0.1)',
                          color: user.accountType === 'diner' ? '#E06E7F' : '#4CAF50',
                          fontFamily: 'Montserrat, sans-serif'
                        }}
                      >
                        {user.accountType.charAt(0).toUpperCase() + user.accountType.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm" style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      {user.joinDate}
                    </td>
                    <td className="px-6 py-4 text-sm" style={{
                      fontFamily: 'Montserrat, sans-serif',
                      color: '#666'
                    }}>
                      {user.reviews} reviews{user.suspiciousFlags > 0 && ` • ⚠️ ${user.suspiciousFlags}`}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className="px-3 py-1 rounded text-xs uppercase"
                        style={{
                          backgroundColor: getStatusColor(user.status),
                          color: 'white',
                          fontFamily: 'Montserrat, sans-serif'
                        }}
                      >
                        {user.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleAction(user.id)}
                        title="Manage this user account"
                        className="text-xs px-3 py-1 rounded transition-all"
                        style={{
                          backgroundColor: 'transparent',
                          color: '#E06E7F',
                          border: '1px solid rgba(224, 110, 127, 0.3)',
                          cursor: 'pointer',
                          fontFamily: 'Montserrat, sans-serif'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        Manage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Action Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-8 max-w-md w-full mx-4">
            <h2 className="text-xl mb-6" style={{
              fontFamily: 'Montserrat, sans-serif',
              color: '#E06E7F'
            }}>
              Toggle user active status
            </h2>

            <p className="text-sm mb-6" style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>
              Flips whether this account may log in. Superusers cannot be toggled from the API.
            </p>

            <div className="flex gap-3">
              <button
                onClick={() => setShowModal(false)}
                title="Cancel user status change"
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
                title="Update user active status"
                className="flex-1 px-4 py-2 rounded-lg"
                style={{
                  backgroundColor: '#E06E7F',
                  color: 'white',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'Montserrat, sans-serif'
                }}
              >
                Update
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
