import { useCallback, useEffect, useState } from "react";
import { Footer } from "./Footer";
import { apiFetch } from "../api";

type ConvRow = {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  diner_username: string;
  updated_at: string;
  last_message: { body: string; created_at: string } | null;
};

type ChatMessage = {
  id: number;
  sender_id: number;
  sender_username: string;
  body: string;
  created_at: string;
};

export function Messages({
  onNavigateMap,
  onNavigateHome,
  onNavigateProfile,
  onNavigateFriendChat,
  onLogout,
  accountType = "Diner",
  pendingStartRestaurantId = null,
  pendingStartRestaurantName = "",
  onConsumedPendingStart,
  initialConversationId = null,
}: {
  onNavigateMap: () => void;
  onNavigateHome: () => void;
  onNavigateProfile: () => void;
  onNavigateFriendChat?: () => void;
  onLogout: () => void;
  accountType?: "Diner" | "Restaurant";
  pendingStartRestaurantId?: number | null;
  pendingStartRestaurantName?: string;
  onConsumedPendingStart?: () => void;
  /** Deep link: open this thread after load (e.g. `/messages/conversations/:id/`). */
  initialConversationId?: number | null;
}) {
  const [conversations, setConversations] = useState<ConvRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [threadTitle, setThreadTitle] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [composer, setComposer] = useState("");
  const [myUserId, setMyUserId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [startMessageBody, setStartMessageBody] = useState("");
  const [startSubmitting, setStartSubmitting] = useState(false);

  const loadSession = useCallback(async () => {
    try {
      const r = await apiFetch("/api/auth/session/");
      const d = await r.json();
      if (d.authenticated && typeof d.user_id === "number") setMyUserId(d.user_id);
    } catch {
      /* ignore */
    }
  }, []);

  const loadConversations = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const r = await apiFetch("/api/messages/conversations/");
      if (!r.ok) {
        setError(`Could not load conversations (${r.status}).`);
        setConversations([]);
        return;
      }
      const data = await r.json();
      setConversations(data.results ?? []);
    } catch {
      setError("Network error loading messages.");
      setConversations([]);
    } finally {
      setLoadingList(false);
    }
  }, []);

  const loadThread = async (id: number) => {
    setError(null);
    try {
      const r = await apiFetch(`/api/messages/conversations/${id}/`);
      if (!r.ok) {
        setError(`Could not open conversation (${r.status}).`);
        return;
      }
      const data = await r.json();
      setThreadTitle(
        accountType === "Restaurant"
          ? `Diner: ${data.diner_username}`
          : data.restaurant_name
      );
      setMessages(data.messages ?? []);
    } catch {
      setError("Network error loading thread.");
    }
  };

  useEffect(() => {
    void loadSession();
    void loadConversations();
  }, [loadSession, loadConversations]);

  useEffect(() => {
    if (initialConversationId == null || !Number.isFinite(initialConversationId)) return;
    setSelectedId(initialConversationId);
  }, [initialConversationId]);

  useEffect(() => {
    if (pendingStartRestaurantId == null) {
      setStartModalOpen(false);
      return;
    }
    if (accountType !== "Diner") return;
    setStartModalOpen(true);
    setStartMessageBody("");
    setError(null);
  }, [accountType, pendingStartRestaurantId]);

  useEffect(() => {
    if (selectedId != null) void loadThread(selectedId);
  }, [selectedId, accountType]);

  const dismissStartModal = () => {
    setStartModalOpen(false);
    setStartMessageBody("");
    onConsumedPendingStart?.();
  };

  const submitStartConversation = async () => {
    if (pendingStartRestaurantId == null || accountType !== "Diner") return;
    const msg = startMessageBody.trim();
    if (!msg) {
      setError("Please enter a message to start the conversation.");
      return;
    }
    setStartSubmitting(true);
    setError(null);
    try {
      const r = await apiFetch("/api/messages/conversations/start/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ restaurant_id: pendingStartRestaurantId, message: msg }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(typeof d.error === "string" ? d.error : `Could not start conversation (${r.status}).`);
        setStartSubmitting(false);
        return;
      }
      const cid = typeof d.conversation_id === "number" ? d.conversation_id : null;
      setStartModalOpen(false);
      setStartMessageBody("");
      onConsumedPendingStart?.();
      if (cid != null) {
        setSelectedId(cid);
        await loadConversations();
        await loadThread(cid);
      } else {
        await loadConversations();
      }
    } catch {
      setError("Network error starting conversation.");
    } finally {
      setStartSubmitting(false);
    }
  };

  const sendMessage = async () => {
    const body = composer.trim();
    if (!selectedId || !body) return;
    setError(null);
    try {
      const r = await apiFetch(`/api/messages/conversations/${selectedId}/send/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: body }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setError(typeof d.error === "string" ? d.error : "Could not send message.");
        return;
      }
      setComposer("");
      await loadThread(selectedId);
      await loadConversations();
    } catch {
      setError("Network error while sending.");
    }
  };

  return (
    <div className="size-full flex flex-col" style={{ backgroundColor: "#FFF9F5" }}>
      <nav className="w-full px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-6">
          <button
            onClick={onNavigateHome}
            className="text-xl transition-all p-2 rounded-lg"
            title="Home"
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "transparent";
            }}
            style={{
              backgroundColor: "transparent",
              border: "none",
              cursor: "pointer",
              color: "#E06E7F",
              fontWeight: "normal",
            }}
            type="button"
          >
            ←
          </button>

          <h1 className="text-2xl" style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}>
            nomz
          </h1>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={onNavigateMap}
            className="text-xl transition-all p-2 rounded-lg"
            title="Map"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            style={{
              backgroundColor: "transparent",
              border: "none",
              cursor: "pointer",
              color: "#E06E7F",
            }}
            type="button"
          >
            🗺️
          </button>

          {accountType === "Diner" && onNavigateFriendChat && (
            <button
              onClick={onNavigateFriendChat}
              className="text-xl transition-all p-2 rounded-lg"
              title="Friend Chat"
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              style={{
                backgroundColor: "transparent",
                border: "none",
                cursor: "pointer",
                color: "#E06E7F",
              }}
              type="button"
            >
              🤝
            </button>
          )}

          {accountType === "Diner" && (
            <button
              onClick={onNavigateProfile}
              className="text-xl transition-all p-2 rounded-lg"
              title="Profile"
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              style={{
                backgroundColor: "transparent",
                border: "none",
                cursor: "pointer",
                color: "#E06E7F",
              }}
              type="button"
            >
              👤
            </button>
          )}

          <button
            onClick={onLogout}
            className="text-xl transition-all p-2 rounded-lg"
            title="Logout"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(224, 110, 127, 0.1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            style={{
              backgroundColor: "transparent",
              border: "none",
              cursor: "pointer",
              color: "#E06E7F",
            }}
            type="button"
          >
            →
          </button>
        </div>
      </nav>

      <main className="w-full py-6 px-6 flex-1 flex flex-col min-h-0 relative">
        {startModalOpen && accountType === "Diner" && pendingStartRestaurantId != null && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center p-4"
            style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="start-conv-title"
          >
            <div
              className="w-full max-w-md rounded-lg p-6 shadow-lg"
              style={{ backgroundColor: "white", border: "2px solid rgba(224, 110, 127, 0.2)" }}
            >
              <h2
                id="start-conv-title"
                className="text-base m-0 mb-2"
                style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}
              >
                Message {pendingStartRestaurantName || "restaurant"}
              </h2>
              <p className="text-xs mb-3 m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                Your first message opens a thread with this restaurant.
              </p>
              <textarea
                className="w-full px-3 py-2 rounded-lg text-sm border-2 mb-3 min-h-[88px]"
                style={{ borderColor: "rgba(224, 110, 127, 0.25)", fontFamily: "Montserrat, sans-serif" }}
                placeholder="Hi, I'd like to ask about…"
                value={startMessageBody}
                disabled={startSubmitting}
                onChange={(e) => setStartMessageBody(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  disabled={startSubmitting}
                  title="Cancel message"
                  className="px-4 py-2 rounded-lg text-sm"
                  style={{
                    border: "1px solid rgba(224,110,127,0.3)",
                    backgroundColor: "white",
                    color: "#666",
                    fontFamily: "Montserrat, sans-serif",
                    cursor: startSubmitting ? "wait" : "pointer",
                  }}
                  onClick={dismissStartModal}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={startSubmitting || !startMessageBody.trim()}
                  title="Send initial message"
                  className="px-4 py-2 rounded-lg text-sm text-white"
                  style={{
                    backgroundColor: startSubmitting || !startMessageBody.trim() ? "#ccc" : "#E06E7F",
                    border: "none",
                    fontFamily: "Montserrat, sans-serif",
                    cursor: startSubmitting || !startMessageBody.trim() ? "not-allowed" : "pointer",
                  }}
                  onClick={() => void submitStartConversation()}
                >
                  {startSubmitting ? "Sending…" : "Send"}
                </button>
              </div>
            </div>
          </div>
        )}
        {error && (
          <p className="text-sm mb-2" style={{ fontFamily: "Montserrat, sans-serif", color: "#b91c1c" }}>
            {error}
          </p>
        )}
        <div className="flex-1 flex gap-4 min-h-0 max-w-6xl mx-auto w-full">
          <div
            className="w-72 shrink-0 rounded-lg overflow-y-auto flex flex-col"
            style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
          >
            <div className="px-3 py-2 text-sm" style={{ backgroundColor: "#E06E7F", color: "white", fontFamily: "Montserrat, sans-serif" }}>
              Conversations
            </div>
            {loadingList ? (
              <p className="p-3 text-xs" style={{ color: "#999" }}>
                Loading…
              </p>
            ) : conversations.length === 0 ? (
              <p className="p-3 text-xs" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                No conversations yet.
              </p>
            ) : (
              conversations.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setSelectedId(c.id)}
                  title={`Open conversation with ${accountType === "Restaurant" ? c.diner_username : c.restaurant_name}`}
                  className="text-left px-3 py-3 border-b w-full"
                  style={{
                    fontFamily: "Montserrat, sans-serif",
                    borderColor: "rgba(224, 110, 127, 0.1)",
                    backgroundColor: selectedId === c.id ? "rgba(224, 110, 127, 0.08)" : "white",
                    cursor: "pointer",
                  }}
                >
                  <div className="text-xs font-medium" style={{ color: "#333" }}>
                    {accountType === "Restaurant" ? c.diner_username : c.restaurant_name}
                  </div>
                  <div className="text-xs mt-1 line-clamp-2" style={{ color: "#888" }}>
                    {c.last_message?.body ?? "—"}
                  </div>
                </button>
              ))
            )}
          </div>

          <div
            className="flex-1 flex flex-col rounded-lg min-h-0"
            style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
          >
            <div className="px-4 py-3 shrink-0" style={{ borderBottom: "1px solid rgba(224, 110, 127, 0.15)" }}>
              <h2 className="text-sm m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}>
                {selectedId ? threadTitle || "Conversation" : "Select a conversation"}
              </h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {selectedId == null ? (
                <p className="text-sm" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                  Choose a thread on the left.
                </p>
              ) : (
                messages.map((m) => {
                  const mine = myUserId != null && m.sender_id === myUserId;
                  return (
                    <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                      <div
                        className="max-w-[85%] px-3 py-2 rounded-lg text-xs"
                        style={{
                          backgroundColor: mine ? "rgba(224, 110, 127, 0.2)" : "rgba(0,0,0,0.05)",
                          fontFamily: "Montserrat, sans-serif",
                          color: "#333",
                        }}
                      >
                        <div style={{ color: "#888", fontSize: "10px", marginBottom: 4 }}>
                          {m.sender_username}
                        </div>
                        {m.body}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
            <div className="p-3 shrink-0 flex gap-2" style={{ borderTop: "1px solid rgba(224, 110, 127, 0.15)" }}>
              <input
                className="flex-1 px-3 py-2 rounded-lg text-sm border-2"
                style={{ borderColor: "rgba(224, 110, 127, 0.25)", fontFamily: "Montserrat, sans-serif" }}
                placeholder="Type a message…"
                value={composer}
                disabled={selectedId == null}
                onChange={(e) => setComposer(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), void sendMessage())}
              />
              <button
                type="button"
                disabled={selectedId == null || !composer.trim()}
                onClick={() => void sendMessage()}
                title="Send message"
                className="px-4 py-2 rounded-lg text-sm text-white"
                style={{
                  backgroundColor: selectedId == null || !composer.trim() ? "#ccc" : "#E06E7F",
                  border: "none",
                  fontFamily: "Montserrat, sans-serif",
                  cursor: selectedId == null || !composer.trim() ? "not-allowed" : "pointer",
                }}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
