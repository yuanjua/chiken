import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { cleanupLocalStorage, notifyStorageIssue } from "@/lib/utils";

export interface ChatSession {
  id: string;
  title: string;
  preview?: string;
  createdAt: Date;
  updatedAt: Date;
  messageCount: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

export interface SessionMessagesBlock {
  msgs: ChatMessage[];
  oldest: number | null;
  hasMore: boolean;
}

// Background streaming state
export interface StreamingState {
  sessionId: string | null;
  isStreaming: boolean;
  progress?: {
    message: string;
  };
}

// Custom storage for handling Date objects
const sessionStorage = {
  getItem: (key: string) => {
    const value = localStorage.getItem(key);
    if (!value) return {};

    try {
      const parsed = JSON.parse(value);
      // Convert date strings back to Date objects
      const sessions: Record<string, ChatSession> = {};
      for (const [sessionId, session] of Object.entries(parsed)) {
        const typedSession = session as any;
        sessions[sessionId] = {
          ...typedSession,
          createdAt: typedSession.createdAt
            ? new Date(typedSession.createdAt)
            : new Date(),
          updatedAt: typedSession.updatedAt
            ? new Date(typedSession.updatedAt)
            : new Date(),
          preview: typedSession.preview || "",
        };
      }
      return sessions;
    } catch {
      return {};
    }
  },
  setItem: (key: string, value: Record<string, ChatSession>) => {
    localStorage.setItem(key, JSON.stringify(value));
  },
  removeItem: (key: string) => {
    localStorage.removeItem(key);
  },
};

// Session management atoms
export const chatSessionsMapAtom = atomWithStorage<Record<string, ChatSession>>(
  "chatSessions",
  {},
  sessionStorage,
);
export const activeSessionIdAtom = atomWithStorage<string | null>(
  "activeSessionId",
  null,
);

// Messages for each session (in-memory only)
export const sessionMessagesAtom = atom<Record<string, SessionMessagesBlock>>(
  {},
);

// Background streaming state
export const streamingStateAtom = atom<StreamingState | null>(null);

// Sessions loading state to prevent multiple API calls
export const sessionsLoadedAtom = atom<boolean>(false);

// Scroll position for the chat sessions list sidebar
export const chatSessionsListScrollAtom = atom<number>(0);

// Derived atom to get the active session
export const activeSessionAtom = atom((get) => {
  const sessionId = get(activeSessionIdAtom);
  const sessions = get(chatSessionsMapAtom);
  return sessionId ? sessions[sessionId] : null;
});

// Derived atom to get sessions as an array sorted by timestamp
// Only show sessions that have actual messages (not just "New Chat" placeholders)
export const sessionsListAtom = atom((get) => {
  const sessions = get(chatSessionsMapAtom);
  return Object.values(sessions)
    .filter((session) => session.messageCount > 0)
    .sort((a, b) => {
      const timeA = a.updatedAt?.getTime() || 0;
      const timeB = b.updatedAt?.getTime() || 0;
      return timeB - timeA;
    });
});
