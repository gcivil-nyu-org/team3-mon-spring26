import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";
import { Footer } from "./Footer";

type ListKind = "approved" | "rejected";

interface Row {
  id: number;
  username: string;
  email: string;
  restaurantName: string;
  dateJoined: string;
}

export function AdminRestaurantAccounts({
  listKind,
  onBack,
}: {
  listKind: ListKind;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const apiPath =
    listKind === "approved" ? "/api/admin/approved-restaurants/" : "/api/admin/rejected-restaurants/";
  const title = listKind === "approved" ? "Approved restaurant accounts" : "Rejected restaurant accounts";
  const subtitle =
    listKind === "approved"
      ? "Verified businesses live on the platform. You can revoke approval to restrict an account."
      : "Denied or revoked businesses. You can approve again to restore access.";

  const loadRows = useCallback(async () => {
    setLoadError(null);
    setActionError(null);
    try {
      const r = await apiFetch(apiPath);
      if (!r.ok) {
        setLoadError(`Could not load list (${r.status}).`);
        setRows([]);
        return;
      }
      const data = await r.json();
      const raw = data.results ?? [];
      setRows(
        raw.map(
          (x: {
            id: number;
            username: string;
            email: string;
            date_joined: string;
            restaurant_name: string;
          }) => ({
            id: x.id,
            username: x.username,
            email: x.email,
            restaurantName: x.restaurant_name || "—",
            dateJoined: new Date(x.date_joined).toLocaleString(),
          })
        )
      );
    } catch {
      setLoadError("Network error.");
      setRows([]);
    }
  }, [apiPath]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const runAction = async (userId: number, action: "approve" | "reject") => {
    const path = action === "approve" ? `/api/admin/approve/${userId}/` : `/api/admin/reject/${userId}/`;
    const msg =
      action === "reject"
        ? "Revoke approval for this business? They will be treated as rejected."
        : "Approve this account again? They will be marked approved.";
    if (!window.confirm(msg)) return;
    setBusyId(userId);
    setActionError(null);
    try {
      const r = await apiFetch(path, { method: "POST" });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setActionError(typeof d.error === "string" ? d.error : "Action failed.");
        return;
      }
      await loadRows();
    } catch {
      setActionError("Network error.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="size-full flex flex-col overflow-y-auto" style={{ backgroundColor: "#FFF9F5" }}>
      <nav
        className="w-full px-8 py-4 flex items-center gap-4 border-b shrink-0"
        style={{ borderColor: "rgba(224, 110, 127, 0.1)" }}
      >
        <button
          type="button"
          onClick={onBack}
          className="text-xl transition-all p-2 rounded-lg"
          title="Back"
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
          style={{
            backgroundColor: "transparent",
            border: "none",
            cursor: "pointer",
            color: "#E06E7F",
          }}
        >
          ←
        </button>
        <div>
          <h1 className="text-xl m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}>
            {title}
          </h1>
          <p className="text-xs m-0 mt-1" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
            {subtitle}
          </p>
        </div>
      </nav>

      <main className="flex-1 w-full py-8 px-8">
        <div className="max-w-5xl mx-auto">
          {(loadError || actionError) && (
            <p className="text-sm mb-4" style={{ fontFamily: "Montserrat, sans-serif", color: "#b91c1c" }}>
              {loadError || actionError}
            </p>
          )}

          <div
            className="rounded-lg overflow-hidden"
            style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm" style={{ fontFamily: "Montserrat, sans-serif" }}>
                <thead>
                  <tr style={{ backgroundColor: "rgba(224, 110, 127, 0.08)", color: "#333" }}>
                    <th className="text-left px-4 py-3 font-semibold">Username</th>
                    <th className="text-left px-4 py-3 font-semibold">Email</th>
                    <th className="text-left px-4 py-3 font-semibold">Business</th>
                    <th className="text-left px-4 py-3 font-semibold">Joined</th>
                    <th className="text-right px-4 py-3 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-10 text-center" style={{ color: "#888" }}>
                        No accounts in this list.
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id} style={{ borderTop: "1px solid rgba(224, 110, 127, 0.12)" }}>
                        <td className="px-4 py-3" style={{ color: "#333" }}>
                          {row.username}
                        </td>
                        <td className="px-4 py-3" style={{ color: "#555" }}>
                          {row.email || "—"}
                        </td>
                        <td className="px-4 py-3" style={{ color: "#333" }}>
                          {row.restaurantName}
                        </td>
                        <td className="px-4 py-3" style={{ color: "#888", fontSize: "12px" }}>
                          {row.dateJoined}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {listKind === "approved" ? (
                            <button
                              type="button"
                              disabled={busyId === row.id}
                              title="Revoke approval for this business"
                              className="text-xs px-3 py-1.5 rounded-lg"
                              style={{
                                border: "1px solid rgba(220, 38, 38, 0.35)",
                                backgroundColor: "white",
                                color: "#b91c1c",
                                cursor: busyId === row.id ? "wait" : "pointer",
                                fontFamily: "Montserrat, sans-serif",
                              }}
                              onClick={() => void runAction(row.id, "reject")}
                            >
                              Revoke approval
                            </button>
                          ) : (
                            <button
                              type="button"
                              disabled={busyId === row.id}
                              title="Approve this business account"
                              className="text-xs px-3 py-1.5 rounded-lg text-white"
                              style={{
                                border: "none",
                                backgroundColor: busyId === row.id ? "#ccc" : "#16a34a",
                                cursor: busyId === row.id ? "wait" : "pointer",
                                fontFamily: "Montserrat, sans-serif",
                              }}
                              onClick={() => void runAction(row.id, "approve")}
                            >
                              Approve
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
