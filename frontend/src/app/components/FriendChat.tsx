import { useCallback, useEffect, useState } from "react";
import { Footer } from "./Footer";
import { apiFetch } from "../api";

/* ── Types ─────────────────────────────────────────── */

type ConvRow = {
  id: number;
  name: string;
  is_group: boolean;
  participants: string[];
  unread_count: number;
  last_message: {
    body: string;
    sender_username: string;
    created_at: string;
  } | null;
  updated_at: string;
};

type ChatMessage = {
  id: number;
  sender_id: number;
  sender_username: string;
  body: string;
  restaurant_recommendation: { id: number; name: string } | null;
  is_read: boolean;
  created_at: string;
};

type SharedRestaurant = {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  added_by: string;
  created_at: string;
};

type OtherUser = { id: number; username: string };

/* ── Component ─────────────────────────────────────── */

export function FriendChat({
  onNavigateHome,
  onNavigateMap,
  onNavigateProfile,
  onNavigateMessages,
  onSelectRestaurant,
  onLogout,
}: {
  onNavigateHome: () => void;
  onNavigateMap: () => void;
  onNavigateProfile: () => void;
  onNavigateMessages: () => void;
  onSelectRestaurant: (id: number) => void;
  onLogout: () => void;
}) {
  /* ── State ── */
  const [conversations, setConversations] = useState<ConvRow[]>([]);
  const [otherUsers, setOtherUsers] = useState<OtherUser[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [threadTitle, setThreadTitle] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sharedRestaurants, setSharedRestaurants] = useState<SharedRestaurant[]>([]);
  const [composer, setComposer] = useState("");
  const [myUserId, setMyUserId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);

  /* New-conversation modal */
  const [newChatOpen, setNewChatOpen] = useState(false);
  const [newChatUsername, setNewChatUsername] = useState("");
  const [newChatSubmitting, setNewChatSubmitting] = useState(false);

  /* Group-creation modal */
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupSelectedIds, setGroupSelectedIds] = useState<number[]>([]);
  const [groupSubmitting, setGroupSubmitting] = useState(false);

  /* ── Data loaders ── */

  const loadSession = useCallback(async () => {
    try {
      const r = await apiFetch("/api/auth/session/");
      const d = await r.json();
      if (d.authenticated && typeof d.user_id === "number") setMyUserId(d.user_id);
    } catch { /* ignore */ }
  }, []);

  const loadConversations = useCallback(async () => {
    setLoadingList(true);
    setError(null);
    try {
      const r = await apiFetch("/api/friends-chat/");
      if (!r.ok) {
        setError(`Could not load conversations (${r.status}).`);
        setConversations([]);
        return;
      }
      const data = await r.json();
      setConversations(data.conversations ?? []);
      setOtherUsers(data.other_users ?? []);
    } catch {
      setError("Network error loading friend chats.");
      setConversations([]);
    } finally {
      setLoadingList(false);
    }
  }, []);

  const loadThread = async (id: number) => {
    setError(null);
    try {
      const r = await apiFetch(`/api/friends-chat/${id}/`);
      if (!r.ok) {
        setError(`Could not open conversation (${r.status}).`);
        return;
      }
      const data = await r.json();
      const conv = data.conversation as ConvRow | undefined;
      setThreadTitle(
        conv?.is_group
          ? conv.name || "Group Chat"
          : conv?.participants?.filter((p: string) => p !== (conv as ConvRow & { participants: string[] }).participants.find(() => true)).join(", ") || "Chat"
      );
      if (conv) {
        setThreadTitle(conv.is_group ? (conv.name || "Group Chat") : conv.participants.join(", "));
      }
      setMessages(data.messages ?? []);
      setSharedRestaurants(data.shared_restaurants ?? []);
    } catch {
      setError("Network error loading thread.");
    }
  };

  /* ── Effects ── */

  useEffect(() => {
    void loadSession();
    void loadConversations();
  }, [loadSession, loadConversations]);

  useEffect(() => {
    if (selectedId != null) void loadThread(selectedId);
  }, [selectedId]);

  /* ── Actions ── */

  const sendMessage = async () => {
    const body = composer.trim();
    if (!selectedId || !body) return;
    setError(null);
    try {
      const r = await apiFetch(`/api/friends-chat/${selectedId}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body }),
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

  const startNewChat = async () => {
    const username = newChatUsername.trim();
    if (!username) return;
    setNewChatSubmitting(true);
    setError(null);
    try {
      const r = await apiFetch("/api/friends-chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(typeof d.error === "string" ? d.error : `Could not start chat (${r.status}).`);
        setNewChatSubmitting(false);
        return;
      }
      setNewChatOpen(false);
      setNewChatUsername("");
      const convId = d.conversation?.id;
      if (convId) setSelectedId(convId);
      await loadConversations();
    } catch {
      setError("Network error starting conversation.");
    } finally {
      setNewChatSubmitting(false);
    }
  };

  const createGroup = async () => {
    const name = groupName.trim();
    if (!name) return;
    setGroupSubmitting(true);
    setError(null);
    try {
      const r = await apiFetch("/api/friends-chat/group/create/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, participant_ids: groupSelectedIds }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(typeof d.error === "string" ? d.error : `Could not create group (${r.status}).`);
        setGroupSubmitting(false);
        return;
      }
      setGroupModalOpen(false);
      setGroupName("");
      setGroupSelectedIds([]);
      const convId = d.conversation?.id;
      if (convId) setSelectedId(convId);
      await loadConversations();
    } catch {
      setError("Network error creating group.");
    } finally {
      setGroupSubmitting(false);
    }
  };

  const toggleGroupUser = (uid: number) => {
    setGroupSelectedIds((prev) =>
      prev.includes(uid) ? prev.filter((id) => id !== uid) : [...prev, uid]
    );
  };

  /* ── Render ── */

  const selectedConv = conversations.find((c) => c.id === selectedId);

  return (
    <div className="size-full flex flex-col" style={{ backgroundColor: "#FFF9F5" }}>
      {/* ── Nav bar ── */}
      <nav className="w-full px-8 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-6">
          <button
            onClick={onNavigateHome}
            className="text-xl transition-all p-2 rounded-lg"
            title="Home"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
            style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", color: "#E06E7F", fontWeight: "normal" }}
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
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
            style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", color: "#E06E7F" }}
            type="button"
          >
            🗺️
          </button>
          <button
            onClick={onNavigateMessages}
            className="text-xl transition-all p-2 rounded-lg"
            title="Restaurant Messages"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
            style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", color: "#E06E7F" }}
            type="button"
          >
            💬
          </button>
          <button
            onClick={onNavigateProfile}
            className="text-xl transition-all p-2 rounded-lg"
            title="Profile"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
            style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", color: "#E06E7F" }}
            type="button"
          >
            👤
          </button>
          <button
            onClick={onLogout}
            className="text-xl transition-all p-2 rounded-lg"
            title="Logout"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
            style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", color: "#E06E7F" }}
            type="button"
          >
            →
          </button>
        </div>
      </nav>

      {/* ── Main area ── */}
      <main className="w-full py-6 px-6 flex-1 flex flex-col min-h-0 relative">
        {/* ── New-chat modal ── */}
        {newChatOpen && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center p-4"
            style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-chat-title"
          >
            <div
              className="w-full max-w-md rounded-lg p-6 shadow-lg"
              style={{ backgroundColor: "white", border: "2px solid rgba(224, 110, 127, 0.2)" }}
            >
              <h2
                id="new-chat-title"
                className="text-base m-0 mb-2"
                style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}
              >
                Start a Chat
              </h2>
              <p className="text-xs mb-3 m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                Choose a friend to start a direct chat with.
              </p>
              <select
                className="w-full px-3 py-2 rounded-lg text-sm border-2 mb-3"
                style={{ borderColor: "rgba(224, 110, 127, 0.25)", fontFamily: "Montserrat, sans-serif" }}
                value={newChatUsername}
                onChange={(e) => setNewChatUsername(e.target.value)}
                disabled={newChatSubmitting}
              >
                <option value="">Select a user…</option>
                {otherUsers.map((u) => (
                  <option key={u.id} value={u.username}>{u.username}</option>
                ))}
              </select>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  disabled={newChatSubmitting}
                  title="Cancel"
                  className="px-4 py-2 rounded-lg text-sm"
                  style={{ border: "1px solid rgba(224,110,127,0.3)", backgroundColor: "white", color: "#666", fontFamily: "Montserrat, sans-serif", cursor: newChatSubmitting ? "wait" : "pointer" }}
                  onClick={() => { setNewChatOpen(false); setNewChatUsername(""); }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={newChatSubmitting || !newChatUsername.trim()}
                  title="Start chat"
                  className="px-4 py-2 rounded-lg text-sm text-white"
                  style={{ backgroundColor: newChatSubmitting || !newChatUsername.trim() ? "#ccc" : "#E06E7F", border: "none", fontFamily: "Montserrat, sans-serif", cursor: newChatSubmitting || !newChatUsername.trim() ? "not-allowed" : "pointer" }}
                  onClick={() => void startNewChat()}
                >
                  {newChatSubmitting ? "Starting…" : "Start"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Group-creation modal ── */}
        {groupModalOpen && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center p-4"
            style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="group-create-title"
          >
            <div
              className="w-full max-w-md rounded-lg p-6 shadow-lg"
              style={{ backgroundColor: "white", border: "2px solid rgba(224, 110, 127, 0.2)" }}
            >
              <h2
                id="group-create-title"
                className="text-base m-0 mb-2"
                style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}
              >
                Create Group Chat
              </h2>
              <input
                className="w-full px-3 py-2 rounded-lg text-sm border-2 mb-3"
                style={{ borderColor: "rgba(224, 110, 127, 0.25)", fontFamily: "Montserrat, sans-serif" }}
                placeholder="Group name"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                disabled={groupSubmitting}
              />
              <p className="text-xs mb-2 m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                Select members:
              </p>
              <div
                className="max-h-40 overflow-y-auto mb-3 rounded-lg border-2 p-2"
                style={{ borderColor: "rgba(224, 110, 127, 0.15)" }}
              >
                {otherUsers.length === 0 ? (
                  <p className="text-xs" style={{ color: "#999" }}>No other users available.</p>
                ) : (
                  otherUsers.map((u) => (
                    <label
                      key={u.id}
                      className="flex items-center gap-2 px-2 py-1 rounded cursor-pointer text-xs"
                      style={{ fontFamily: "Montserrat, sans-serif", color: "#333" }}
                      onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.1)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                    >
                      <input
                        type="checkbox"
                        checked={groupSelectedIds.includes(u.id)}
                        onChange={() => toggleGroupUser(u.id)}
                        disabled={groupSubmitting}
                      />
                      {u.username}
                    </label>
                  ))
                )}
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  disabled={groupSubmitting}
                  title="Cancel group creation"
                  className="px-4 py-2 rounded-lg text-sm"
                  style={{ border: "1px solid rgba(224,110,127,0.3)", backgroundColor: "white", color: "#666", fontFamily: "Montserrat, sans-serif", cursor: groupSubmitting ? "wait" : "pointer" }}
                  onClick={() => { setGroupModalOpen(false); setGroupName(""); setGroupSelectedIds([]); }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={groupSubmitting || !groupName.trim()}
                  title="Create group"
                  className="px-4 py-2 rounded-lg text-sm text-white"
                  style={{ backgroundColor: groupSubmitting || !groupName.trim() ? "#ccc" : "#E06E7F", border: "none", fontFamily: "Montserrat, sans-serif", cursor: groupSubmitting || !groupName.trim() ? "not-allowed" : "pointer" }}
                  onClick={() => void createGroup()}
                >
                  {groupSubmitting ? "Creating…" : "Create"}
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
          {/* ── Sidebar ── */}
          <div
            className="w-72 shrink-0 rounded-lg overflow-y-auto flex flex-col"
            style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
          >
            <div
              className="px-3 py-2 text-sm flex items-center justify-between"
              style={{ backgroundColor: "#E06E7F", color: "white", fontFamily: "Montserrat, sans-serif" }}
            >
              <span>Friend Chats</span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setNewChatOpen(true)}
                  title="Start new chat"
                  className="text-white rounded px-1"
                  style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", fontSize: "14px" }}
                >
                  ✏️
                </button>
                <button
                  type="button"
                  onClick={() => setGroupModalOpen(true)}
                  title="Create group chat"
                  className="text-white rounded px-1"
                  style={{ backgroundColor: "transparent", border: "none", cursor: "pointer", fontSize: "14px" }}
                >
                  👥
                </button>
              </div>
            </div>
            {loadingList ? (
              <p className="p-3 text-xs" style={{ color: "#999" }}>Loading…</p>
            ) : conversations.length === 0 ? (
              <p className="p-3 text-xs" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                No friend chats yet. Start one!
              </p>
            ) : (
              conversations.map((c) => {
                const label = c.is_group
                  ? (c.name || "Group Chat")
                  : c.participants.join(", ");
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedId(c.id)}
                    title={`Open chat: ${label}`}
                    className="text-left px-3 py-3 border-b w-full"
                    style={{
                      fontFamily: "Montserrat, sans-serif",
                      borderColor: "rgba(224, 110, 127, 0.1)",
                      backgroundColor: selectedId === c.id ? "rgba(224, 110, 127, 0.08)" : "white",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => {
                      if (selectedId !== c.id) e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.05)";
                    }}
                    onMouseLeave={(e) => {
                      if (selectedId !== c.id) e.currentTarget.style.backgroundColor = "white";
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-medium" style={{ color: "#333" }}>
                        {c.is_group ? "👥 " : ""}{label}
                      </div>
                      {c.unread_count > 0 && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full text-white"
                          style={{ backgroundColor: "#E06E7F", fontSize: "10px" }}
                        >
                          {c.unread_count}
                        </span>
                      )}
                    </div>
                    <div className="text-xs mt-1 line-clamp-2" style={{ color: "#888" }}>
                      {c.last_message
                        ? `${c.last_message.sender_username}: ${c.last_message.body}`
                        : "—"}
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* ── Thread pane ── */}
          <div className="flex-1 flex flex-col rounded-lg min-h-0" style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}>
            <div className="px-4 py-3 shrink-0 flex items-center justify-between" style={{ borderBottom: "1px solid rgba(224, 110, 127, 0.15)" }}>
              <h2 className="text-sm m-0" style={{ fontFamily: "Montserrat, sans-serif", color: "#E06E7F" }}>
                {selectedId ? threadTitle || "Chat" : "Select a chat"}
              </h2>
              {selectedConv?.is_group && (
                <span className="text-xs" style={{ fontFamily: "Montserrat, sans-serif", color: "#999" }}>
                  {selectedConv.participants.length} members
                </span>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {selectedId == null ? (
                <p className="text-sm" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                  Choose a chat on the left, or start a new one.
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
                        {m.restaurant_recommendation && (
                          <button
                            type="button"
                            onClick={() => onSelectRestaurant(m.restaurant_recommendation!.id)}
                            title={`View ${m.restaurant_recommendation.name}`}
                            className="block mt-1 text-xs underline"
                            style={{ color: "#E06E7F", background: "none", border: "none", cursor: "pointer", fontFamily: "Montserrat, sans-serif", padding: 0 }}
                          >
                            🍽️ {m.restaurant_recommendation.name}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
            {/* Composer */}
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

          {/* ── Shared restaurants panel ── */}
          {selectedId != null && (
            <div
              className="w-56 shrink-0 rounded-lg overflow-y-auto flex flex-col"
              style={{ border: "2px solid rgba(224, 110, 127, 0.15)", backgroundColor: "white" }}
            >
              <div
                className="px-3 py-2 text-sm"
                style={{ backgroundColor: "#E06E7F", color: "white", fontFamily: "Montserrat, sans-serif" }}
              >
                Together List
              </div>
              {sharedRestaurants.length === 0 ? (
                <p className="p-3 text-xs" style={{ fontFamily: "Montserrat, sans-serif", color: "#666" }}>
                  No shared restaurants yet. Recommend one in the chat!
                </p>
              ) : (
                sharedRestaurants.map((sr) => (
                  <button
                    key={sr.id}
                    type="button"
                    onClick={() => onSelectRestaurant(sr.restaurant_id)}
                    title={`View ${sr.restaurant_name}`}
                    className="text-left px-3 py-2 border-b w-full"
                    style={{
                      fontFamily: "Montserrat, sans-serif",
                      borderColor: "rgba(224, 110, 127, 0.1)",
                      backgroundColor: "white",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(224, 110, 127, 0.05)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "white"; }}
                  >
                    <div className="text-xs font-medium" style={{ color: "#333" }}>
                      🍽️ {sr.restaurant_name}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: "#999", fontSize: "10px" }}>
                      added by {sr.added_by}
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
