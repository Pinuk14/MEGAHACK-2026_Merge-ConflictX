import { useState, useRef, useEffect, useMemo } from "react";

const API_BASE = "http://localhost:8000";
const CHATBOT_STATE_KEY = "chatbot_ui_state_v1";

function readPersistedState() {
  try {
    const raw = window.localStorage.getItem(CHATBOT_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

function getNow() {
  const d = new Date();
  return d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function EmptyState() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: 40,
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          background: "rgba(255,69,0,0.08)",
          border: "1.5px solid rgba(255,69,0,0.2)",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 26,
          marginBottom: 4,
        }}
      >
        📡
      </div>
      <div>
        <div
          style={{
            fontFamily: "'Public Sans', sans-serif",
            fontWeight: 800,
            fontSize: 13,
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            color: "#e2e8f0",
            marginBottom: 8,
          }}
        >
          Channel Open
        </div>
        <div
          style={{
            fontSize: 10,
            color: "#64748b",
            letterSpacing: "0.08em",
            lineHeight: 1.8,
            maxWidth: 360,
          }}
        >
          No transmissions yet. Enter your first radio command below to begin.
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginTop: 8,
          padding: "6px 14px",
          background: "#2A2A2A",
          border: "1px solid #1e293b",
          borderRadius: 4,
        }}
      >
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#22c55e",
            animation: "pulse 1.5s infinite",
          }}
        />
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: "#64748b",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
          }}
        >
          Standing by for command
        </span>
      </div>
    </div>
  );
}

export default function GPProtocol({ initialFileIds = [], onBack }) {
  const persistedState = useMemo(() => readPersistedState(), []);
  const [messagesByMission, setMessagesByMission] = useState(persistedState?.messagesByMission || {});
  const [sessionByMission, setSessionByMission] = useState(persistedState?.sessionByMission || {});
  const [input, setInput] = useState("");
  const [missions, setMissions] = useState([]);
  const [activeMission, setActiveMission] = useState(persistedState?.activeMission || "");
  const [loadingCollections, setLoadingCollections] = useState(false);
  const [sending, setSending] = useState(false);
  const [deletingChat, setDeletingChat] = useState(false);
  const [clearingAllChats, setClearingAllChats] = useState(false);
  const [errorText, setErrorText] = useState("");

  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);

  const activeMessages = useMemo(
    () => messagesByMission[activeMission] || [],
    [messagesByMission, activeMission],
  );

  const normalizeCollections = (collections = []) =>
    collections.map((c) => ({
      id: c.collection_id,
      status: "ACTIVE",
      title: c.name || c.collection_id,
      documentCount: Number(c.document_count || 0),
      preview: `${c.document_count || 0} docs • ${c.chunk_count || 0} chunks`,
      time: "LIVE",
    }));

  const activeMissionMeta = useMemo(
    () => missions.find((m) => m.id === activeMission) || null,
    [missions, activeMission],
  );

  const quickQuestions = useMemo(() => {
    const base = [
      "Summarize this document in key points.",
      "List the main risks and concerns.",
      "Extract important deadlines and dates.",
      "What are the key obligations and action items?",
    ];
    if ((activeMissionMeta?.documentCount || 0) > 1) {
      base.push("Compare the uploaded documents and highlight major differences.");
    }
    return base;
  }, [activeMissionMeta]);

  const loadCollections = async () => {
    try {
      setLoadingCollections(true);
      const res = await fetch(`${API_BASE}/chatbot/collections`);
      const data = await res.json();
      const normalized = normalizeCollections(data.collections || []);
      setMissions(normalized);

      const validMissionIds = new Set(normalized.map((m) => m.id));
      setMessagesByMission((prev) =>
        Object.fromEntries(Object.entries(prev).filter(([missionId]) => validMissionIds.has(missionId))),
      );
      setSessionByMission((prev) =>
        Object.fromEntries(Object.entries(prev).filter(([missionId]) => validMissionIds.has(missionId))),
      );

      if (!activeMission && normalized.length) {
        setActiveMission(normalized[0].id);
      } else if (activeMission && !validMissionIds.has(activeMission)) {
        setActiveMission(normalized[0]?.id || "");
      }
    } catch {
      setErrorText("Failed to load chatbot collections.");
    } finally {
      setLoadingCollections(false);
    }
  };

  const createMission = async () => {
    if (!Array.isArray(initialFileIds) || initialFileIds.length === 0) {
      setErrorText("No uploaded files found. Run document analysis with uploads first.");
      return;
    }

    try {
      setErrorText("");
      const res = await fetch(`${API_BASE}/chatbot/collections/from-files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_ids: initialFileIds,
          name: `Mission ${new Date().toLocaleString("en-GB")}`,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Could not create mission.");
      }
      await loadCollections();
      const id = data.collection?.collection_id;
      if (id) {
        setActiveMission(id);
      }
    } catch (error) {
      setErrorText(String(error.message || error));
    }
  };

  useEffect(() => {
    loadCollections();
  }, []);

  useEffect(() => {
    if (!loadingCollections && missions.length === 0 && initialFileIds.length > 0) {
      createMission();
    }
  }, [loadingCollections, missions.length, initialFileIds.length]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeMessages]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        CHATBOT_STATE_KEY,
        JSON.stringify({
          messagesByMission,
          sessionByMission,
          activeMission,
        }),
      );
    } catch {
      // ignore persistence errors
    }
  }, [messagesByMission, sessionByMission, activeMission]);

  const handleMissionSelect = (id) => {
    setActiveMission(id);
    setErrorText("");
  };

  const handleNewSession = () => {
    if (!activeMission) return;
    setSessionByMission((prev) => ({
      ...prev,
      [activeMission]: null,
    }));
    setMessagesByMission((prev) => ({
      ...prev,
      [activeMission]: [],
    }));
    setErrorText("");
  };

  const handleDeleteChat = async () => {
    if (!activeMission || deletingChat) return;

    const confirmed = window.confirm("Delete this chat conversation? This removes current session memory.");
    if (!confirmed) return;

    setDeletingChat(true);
    setErrorText("");

    try {
      const res = await fetch(
        `${API_BASE}/chatbot/collections/${encodeURIComponent(activeMission)}/sessions`,
        { method: "DELETE" },
      );
      if (!res.ok && res.status !== 404) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to delete chat session.");
      }

      setSessionByMission((prev) => ({
        ...prev,
        [activeMission]: null,
      }));
      setMessagesByMission((prev) => ({
        ...prev,
        [activeMission]: [],
      }));
    } catch (error) {
      setErrorText(String(error.message || error));
    } finally {
      setDeletingChat(false);
    }
  };

  const handleClearAllChatHistory = async () => {
    if (clearingAllChats) return;

    const confirmed = window.confirm("Clear all chat history for all missions? This cannot be undone.");
    if (!confirmed) return;

    setClearingAllChats(true);
    setErrorText("");

    try {
      const res = await fetch(`${API_BASE}/chatbot/sessions`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to clear chat history.");
      }

      setMessagesByMission({});
      setSessionByMission({});
      try {
        window.localStorage.removeItem(CHATBOT_STATE_KEY);
      } catch {
        // ignore local storage errors
      }
    } catch (error) {
      setErrorText(String(error.message || error));
    } finally {
      setClearingAllChats(false);
    }
  };

  const handleTransmit = async (presetQuestion = null) => {
    const trimmed = (typeof presetQuestion === "string" ? presetQuestion : input).trim();
    if (!trimmed || !activeMission || sending) return;

    const userMsg = {
      id: Date.now(),
      role: "user",
      time: getNow(),
      content: trimmed,
    };

    setMessagesByMission((prev) => ({
      ...prev,
      [activeMission]: [...(prev[activeMission] || []), userMsg],
    }));
    if (!presetQuestion) {
      setInput("");
    }
    setErrorText("");
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/chatbot/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          collection_id: activeMission,
          question: trimmed,
          top_k: 5,
          session_id: sessionByMission[activeMission] || null,
          history_turns: 4,
          memory_top_k: 3,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to get chatbot answer.");
      }

      if (data.session_id) {
        setSessionByMission((prev) => ({
          ...prev,
          [activeMission]: data.session_id,
        }));
      }

      const citations = Array.isArray(data.citations)
        ? data.citations
            .slice(0, 3)
            .map((c) => `• ${c.document_title} [chunk ${c.chunk_index}]`)
            .join("\n")
        : "";

      const aiMsg = {
        id: Date.now() + 1,
        role: "ai",
        time: getNow(),
        content: citations ? `${data.answer}\n\nEvidence:\n${citations}` : data.answer,
      };

      setMessagesByMission((prev) => ({
        ...prev,
        [activeMission]: [...(prev[activeMission] || []), aiMsg],
      }));
    } catch (error) {
      setErrorText(String(error.message || error));
      const aiMsg = {
        id: Date.now() + 2,
        role: "ai",
        time: getNow(),
        content: "Unable to fetch answer right now.",
      };
      setMessagesByMission((prev) => ({
        ...prev,
        [activeMission]: [...(prev[activeMission] || []), aiMsg],
      }));
    } finally {
      setSending(false);
    }
  };

  const handleQuickQuestion = (question) => {
    if (!activeMission || sending) return;
    handleTransmit(question);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleTransmit();
    }
  };

  return (
    <div
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        background: "#0A0A0A",
        color: "#e2e8f0",
        height: "100vh",
        display: "flex",
        overflow: "hidden",
      }}
    >
      <aside
        style={{
          width: 280,
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid #2A2A2A",
          background: "#0A0A0A",
          zIndex: 20,
          flexShrink: 0,
        }}
      >
        <div style={{ padding: "24px", borderBottom: "1px solid #2A2A2A" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <div
              style={{
                width: 40,
                height: 40,
                background: "#FF4500",
                borderRadius: 4,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "white",
                fontSize: 20,
              }}
            >
              ⚙
            </div>
            <div>
              <div
                style={{
                  fontFamily: "'Public Sans', sans-serif",
                  fontWeight: 800,
                  fontSize: 11,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  lineHeight: 1,
                }}
              >
                GP PROTOCOL
              </div>
              <div
                style={{
                  fontSize: 9,
                  color: "#FF4500",
                  fontWeight: 700,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  marginTop: 2,
                }}
              >
                Nodes Interface
              </div>
            </div>
          </div>

          <button
            style={{
              width: "100%",
              padding: "10px 16px",
              background: "#FF4500",
              color: "white",
              fontSize: 10,
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
              borderRadius: 4,
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
            onClick={createMission}
          >
            + New Mission Brief
          </button>

          <button
            style={{
              width: "100%",
              padding: "9px 16px",
              background: "transparent",
              color: "#94a3b8",
              fontSize: 10,
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
              borderRadius: 4,
              border: "1px solid #334155",
              cursor: "pointer",
              marginTop: 8,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
            onClick={onBack}
          >
            ← Back to Dashboard
          </button>

          <button
            style={{
              width: "100%",
              padding: "9px 16px",
              background: "transparent",
              color: activeMission ? "#94a3b8" : "#475569",
              fontSize: 10,
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
              borderRadius: 4,
              border: "1px solid #334155",
              cursor: activeMission ? "pointer" : "not-allowed",
              marginTop: 8,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
            onClick={handleNewSession}
            disabled={!activeMission}
          >
            ⟳ New Chat Session
          </button>

          <button
            style={{
              width: "100%",
              padding: "9px 16px",
              background: "transparent",
              color: activeMission ? "#fda4af" : "#7f1d1d",
              fontSize: 10,
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
              borderRadius: 4,
              border: "1px solid #7f1d1d",
              cursor: activeMission && !deletingChat ? "pointer" : "not-allowed",
              marginTop: 8,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
            onClick={handleDeleteChat}
            disabled={!activeMission || deletingChat}
          >
            {deletingChat ? "Deleting..." : "🗑 Delete Chat"}
          </button>

          <button
            style={{
              width: "100%",
              padding: "9px 16px",
              background: "transparent",
              color: "#fca5a5",
              fontSize: 10,
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
              borderRadius: 4,
              border: "1px solid #991b1b",
              cursor: clearingAllChats ? "not-allowed" : "pointer",
              marginTop: 8,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
            onClick={handleClearAllChatHistory}
            disabled={clearingAllChats}
          >
            {clearingAllChats ? "Clearing..." : "🧹 Clear All Chat History"}
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
          <div
            style={{
              fontSize: 9,
              fontWeight: 700,
              color: "#64748b",
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              paddingLeft: 8,
              marginBottom: 8,
            }}
          >
            Active Briefings
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {missions.map((m) => (
              <div
                key={m.id}
                onClick={() => handleMissionSelect(m.id)}
                style={{
                  padding: "10px 12px",
                  background: activeMission === m.id ? "rgba(255,69,0,0.1)" : "transparent",
                  borderLeft: `3px solid ${activeMission === m.id ? "#FF4500" : "transparent"}`,
                  borderRadius: "0 4px 4px 0",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 3 }}>
                  <span style={{ fontSize: 9, fontWeight: 700, color: activeMission === m.id ? "#FF4500" : "#64748b", letterSpacing: "0.05em" }}>
                    [{m.status}]
                  </span>
                  <span style={{ fontSize: 9, color: "#64748b" }}>{m.time}</span>
                </div>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    color: activeMission === m.id ? "#e2e8f0" : "#94a3b8",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {m.title}
                </div>
                <div style={{ fontSize: 9, color: "#64748b", marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {m.preview}
                </div>
              </div>
            ))}
            {!loadingCollections && missions.length === 0 && (
              <div style={{ fontSize: 10, color: "#64748b", padding: "0 8px" }}>
                No mission briefs yet.
              </div>
            )}
          </div>
        </div>
      </aside>

      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          position: "relative",
          backgroundImage: "radial-gradient(circle, rgba(255,69,0,0.04) 1px, transparent 1px)",
          backgroundSize: "20px 20px",
          minWidth: 0,
        }}
      >
        <header
          style={{
            height: 64,
            borderBottom: "1px solid #2A2A2A",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            background: "#0A0A0A",
            zIndex: 10,
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#FF4500", fontSize: 18 }}>📡</span>
              <span
                style={{
                  fontFamily: "'Public Sans', sans-serif",
                  fontWeight: 900,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                }}
              >
                COMMS TRANSCRIPT // SESSION {activeMission || "UNASSIGNED"}
              </span>
            </div>
            <div style={{ width: 1, height: 16, background: "#334155" }} />
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#22c55e", animation: "pulse 1.5s infinite" }} />
              <span style={{ fontSize: 9, fontWeight: 700, color: "#64748b", letterSpacing: "0.2em", textTransform: "uppercase" }}>
                DRS STATUS: ACTIVE
              </span>
            </div>
          </div>
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              color: "#fde047",
              background: "rgba(253,224,71,0.08)",
              border: "1px solid rgba(253,224,71,0.2)",
              borderRadius: 4,
              padding: "3px 8px",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            VRS ACTIVE
          </span>
        </header>

        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: activeMessages.length === 0 ? 0 : "24px",
            display: "flex",
            flexDirection: "column",
            gap: 24,
          }}
        >
          {activeMessages.length === 0 ? (
            <EmptyState />
          ) : (
            <>
              {activeMessages.map((msg) =>
                msg.role === "ai" ? (
                  <div key={msg.id} style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 680 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 4 }}>
                      <span style={{ fontSize: 9, fontWeight: 700, color: "#FF4500", letterSpacing: "0.15em", textTransform: "uppercase" }}>
                        Technical Director
                      </span>
                      <span style={{ fontSize: 9, color: "#64748b" }}>[{msg.time}]</span>
                    </div>
                    <div style={{ background: "#2A2A2A", border: "1.5px solid #1e293b", borderRadius: 6, padding: 16 }}>
                      <p style={{ fontSize: 13, lineHeight: 1.7, color: "#e2e8f0", margin: 0, whiteSpace: "pre-wrap" }}>{msg.content}</p>
                    </div>
                  </div>
                ) : (
                  <div
                    key={msg.id}
                    style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 680, marginLeft: "auto", alignItems: "flex-end" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, paddingRight: 4 }}>
                      <span style={{ fontSize: 9, color: "#64748b" }}>[{msg.time}]</span>
                      <span style={{ fontSize: 9, fontWeight: 700, color: "#94a3b8", letterSpacing: "0.15em", textTransform: "uppercase" }}>
                        Driver
                      </span>
                    </div>
                    <div style={{ background: "#FF4500", borderRadius: 6, padding: 16, borderBottom: "3px solid #7c2d00" }}>
                      <p style={{ fontSize: 13, lineHeight: 1.7, color: "white", margin: 0 }}>{msg.content}</p>
                    </div>
                  </div>
                ),
              )}
              <div ref={chatEndRef} />
            </>
          )}
        </div>

        <div style={{ padding: "20px 24px", borderTop: "1px solid #2A2A2A", background: "#0A0A0A", zIndex: 10, flexShrink: 0 }}>
          <div style={{ maxWidth: 800, margin: "0 auto 10px", display: "flex", flexWrap: "wrap", gap: 8 }}>
            {quickQuestions.map((question) => (
              <button
                key={question}
                onClick={() => handleQuickQuestion(question)}
                disabled={!activeMission || sending}
                style={{
                  background: "transparent",
                  border: "1px solid #334155",
                  color: "#94a3b8",
                  borderRadius: 999,
                  padding: "6px 10px",
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                  cursor: !activeMission || sending ? "not-allowed" : "pointer",
                }}
              >
                {question}
              </button>
            ))}
          </div>
          <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", alignItems: "flex-end", gap: 12 }}>
            <div style={{ flex: 1, position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  top: -8,
                  left: 10,
                  padding: "0 6px",
                  background: "#0A0A0A",
                  fontSize: 9,
                  fontWeight: 700,
                  color: "#64748b",
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  zIndex: 1,
                }}
              >
                Command Input
              </div>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={activeMission ? "ENTER RADIO COMMAND..." : "CREATE/SELECT A MISSION FIRST"}
                rows={2}
                disabled={!activeMission || sending}
                style={{
                  width: "100%",
                  background: "#2A2A2A",
                  border: "1.5px solid #1e293b",
                  borderRadius: 6,
                  padding: "16px 14px 12px",
                  fontSize: 12,
                  fontFamily: "'JetBrains Mono', monospace",
                  color: "#e2e8f0",
                  resize: "none",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
            <button
              onClick={handleTransmit}
              disabled={!activeMission || sending}
              style={{
                background: !activeMission || sending ? "#9a3412" : "#FF4500",
                color: "white",
                fontFamily: "'Public Sans', sans-serif",
                fontWeight: 900,
                fontSize: 11,
                padding: "0 28px",
                height: 54,
                borderRadius: 6,
                border: "none",
                cursor: !activeMission || sending ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                flexShrink: 0,
                boxShadow: "0 4px 14px rgba(255,69,0,0.25)",
              }}
            >
              {sending ? "TRANSMITTING..." : "TRANSMIT →"}
            </button>
          </div>
          {errorText && (
            <div style={{ maxWidth: 800, margin: "10px auto 0", color: "#fda4af", fontSize: 10 }}>{errorText}</div>
          )}
        </div>
      </main>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap');
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #0A0A0A; }
        ::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 2px; }
      `}</style>
    </div>
  );
}
