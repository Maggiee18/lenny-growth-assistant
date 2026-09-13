"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type {
  ArtifactOut,
  ConfigResponse,
  MessageOut,
  MessageResponse,
  SessionSummary,
} from "@/lib/types";
import { Sidebar } from "@/components/Sidebar";
import { Composer } from "@/components/Composer";
import { MessageBubble } from "@/components/MessageBubble";
import { ArtifactViewer } from "@/components/ArtifactViewer";
import { ProviderBadge } from "@/components/ProviderBadge";

type TurnMeta = { sources?: MessageResponse["sources"]; abstained?: boolean; artifactId?: string | null };

export default function Home() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [turnMeta, setTurnMeta] = useState<Record<string, TurnMeta>>({});
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const [artifact, setArtifact] = useState<ArtifactOut | null>(null);
  const [artifactPanelOpen, setArtifactPanelOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  useEffect(() => {
    api
      .getConfig()
      .then(setConfig)
      .catch((err) => setBackendError((err as Error).message));
  }, []);

  useEffect(() => {
    refreshSessions();
  }, []);

  async function refreshSessions(selectFirst = false) {
    setSessionsLoading(true);
    try {
      const list = await api.listSessions();
      setSessions(list);
      setBackendError(null);
      if (selectFirst && list.length > 0 && list[0]) {
        setActiveSessionId(list[0].id);
      }
    } catch (err) {
      setBackendError((err as Error).message);
    } finally {
      setSessionsLoading(false);
    }
  }

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    setMessagesLoading(true);
    api
      .getSession(activeSessionId)
      .then((detail) => {
        setMessages(detail.messages);
        setTurnMeta({});
      })
      .catch((err) => setSendError((err as Error).message))
      .finally(() => setMessagesLoading(false));
  }, [activeSessionId]);

  async function handleNewChat() {
    try {
      const session = await api.createSession();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setArtifact(null);
      setArtifactPanelOpen(false);
    } catch (err) {
      setBackendError((err as Error).message);
    }
  }

  async function handleSend(content: string) {
    let sessionId = activeSessionId;
    setSendError(null);

    if (!sessionId) {
      try {
        const session = await api.createSession();
        setSessions((prev) => [session, ...prev]);
        sessionId = session.id;
        setActiveSessionId(sessionId);
      } catch (err) {
        setSendError((err as Error).message);
        return;
      }
    }

    const optimisticUser: MessageOut = {
      id: `pending-${Date.now()}`,
      session_id: sessionId,
      role: "user",
      content,
      message_metadata: {},
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setSending(true);

    try {
      const response = await api.postMessage(sessionId, content);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticUser.id),
        response.user_message,
        response.assistant_message,
      ]);
      setTurnMeta((prev) => ({
        ...prev,
        [response.assistant_message.id]: {
          sources: response.sources,
          abstained: response.abstained,
          artifactId: response.artifact_id,
        },
      }));
      if (response.artifact_id) {
        const generated = await api.getArtifact(response.artifact_id);
        setArtifact(generated);
        setArtifactPanelOpen(true);
      }
      refreshSessions();
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id));
      if (err instanceof ApiError) {
        setSendError(`${err.message}${err.detail ? ` (${err.detail})` : ""}`);
      } else {
        setSendError((err as Error).message);
      }
    } finally {
      setSending(false);
    }
  }

  async function handleOpenArtifact(artifactId: string) {
    try {
      const a = await api.getArtifact(artifactId);
      setArtifact(a);
      setArtifactPanelOpen(true);
    } catch (err) {
      setSendError((err as Error).message);
    }
  }

  return (
    <div className="flex h-screen w-screen">
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden
        />
      )}
      <div
        className={`fixed inset-y-0 left-0 z-40 transform transition-transform duration-200 md:static md:translate-x-0 ${
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={(id) => {
            setActiveSessionId(id);
            setMobileSidebarOpen(false);
          }}
          onNewChat={() => {
            handleNewChat();
            setMobileSidebarOpen(false);
          }}
          loading={sessionsLoading}
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMobileSidebarOpen(true)}
              aria-label="Open chat sessions"
              className="rounded-md border border-slate-200 p-1.5 text-slate-600 md:hidden"
            >
              ☰
            </button>
            <div>
              <h1 className="text-sm font-semibold text-slate-800">The Lenny Growth Assistant</h1>
              <p className="hidden text-xs text-slate-400 sm:block">
                Grounded product &amp; growth Q&amp;A over podcast transcripts
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ProviderBadge config={config} />
            {artifact && (
              <button
                onClick={() => setArtifactPanelOpen((v) => !v)}
                className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                {artifactPanelOpen ? "Hide artifact" : "Show artifact"}
              </button>
            )}
          </div>
        </header>

        {backendError && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-700">
            {backendError}
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <main className="flex min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
              {!activeSessionId && messages.length === 0 && (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-400">
                  <div className="text-4xl" aria-hidden>
                    💬
                  </div>
                  <p className="text-sm">Start a new chat, or ask a question below to begin one automatically.</p>
                </div>
              )}
              {messagesLoading && <p className="text-xs text-slate-400">Loading conversation…</p>}
              {messages.map((m) => {
                const meta = turnMeta[m.id];
                return (
                  <MessageBubble
                    key={m.id}
                    message={m}
                    sources={meta?.sources}
                    abstained={meta?.abstained}
                    hasArtifact={Boolean(meta?.artifactId)}
                    onOpenArtifact={meta?.artifactId ? () => handleOpenArtifact(meta.artifactId!) : undefined}
                  />
                );
              })}
              {sending && (
                <div className="flex items-center gap-2 text-xs text-slate-400" role="status" aria-live="polite">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:300ms]" />
                  Retrieving sources and generating a grounded answer…
                </div>
              )}
              {sendError && (
                <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                  {sendError}
                </div>
              )}
            </div>
            <Composer onSend={handleSend} disabled={sending} />
          </main>

          {artifactPanelOpen && (
            <div className="fixed inset-0 z-20 bg-white md:static md:z-auto md:w-[45%] md:min-w-[360px] md:shrink-0 md:border-l md:border-slate-200">
              <ArtifactViewer artifact={artifact} onClose={() => setArtifactPanelOpen(false)} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
