"use client";

import { useAtom } from "jotai";
// No longer need the router
// import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
// Removed unused chatAtoms imports - using sessionAtoms instead
import {
  activeSessionIdAtom,
  chatSessionsMapAtom,
  sessionsListAtom,
  chatSessionsListScrollAtom,
  sessionsLoadedAtom,
} from "@/store/sessionAtoms";
import React from "react";
import type { ChatSession } from "@/store/sessionAtoms";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Plus, MoreHorizontal, Trash2, Edit } from "lucide-react";
import { deleteSession, updateSessionTitle } from "@/lib/api-client";
import { generateUUID } from "@/lib/utils";
import { useTranslations } from "next-intl";

// Format timestamp for display - shows formatted time instead of relative time
function formatTimestamp(date: Date): string {
  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// Memoized row to avoid re-rendering unchanged sessions
interface SessionRowProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, e: React.MouseEvent) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  editingSessionId: string | null;
  editingTitle: string;
  setEditingTitle: (t: string) => void;
  handleKeyPress: (
    e: React.KeyboardEvent<HTMLInputElement>,
    id: string,
  ) => void;
  formatTimestamp: (d: Date) => string;
}

const SessionRow: React.FC<SessionRowProps> = React.memo(
  ({
    session,
    isActive,
    onSelect,
    onRename,
    onDelete,
    editingSessionId,
    editingTitle,
    setEditingTitle,
    handleKeyPress,
    formatTimestamp,
  }) => {
    return (
      <div
        className={`
        group relative flex items-center p-2 rounded-lg cursor-pointer transition-colors
        ${isActive ? "bg-primary/10 text-primary" : "hover:bg-muted"}
      `}
        onClick={() => editingSessionId !== session.id && onSelect(session.id)}
        key={session.id}
      >
        <div className="flex-1 min-w-0">
          {editingSessionId === session.id ? (
            <Input
              type="text"
              value={editingTitle}
              onChange={(e) => setEditingTitle(e.target.value)}
              onBlur={() =>
                onRename(session.id, { stopPropagation: () => {} } as any)
              }
              onKeyDown={(e) => handleKeyPress(e, session.id)}
              autoFocus
              className="h-7 text-sm"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <p
              className="text-sm font-medium truncate pr-8"
              title={session.title}
            >
              {session.title}
            </p>
          )}
          <p className="text-xs text-muted-foreground truncate pr-8">
            {formatTimestamp(session.updatedAt)}
          </p>
        </div>
        {/* Dropdown menu */}
        <div className="absolute top-1/2 right-2 -translate-y-1/2 z-10">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity bg-background/90 backdrop-blur-sm shadow-sm hover:bg-accent"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="bg-background dark:bg-gray-800"
            >
              <DropdownMenuItem onClick={(e) => onRename(session.id, e)}>
                <Edit className="h-4 w-4 mr-2" /> Rename
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => onDelete(session.id, e)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="h-4 w-4 mr-2" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Re-render if active state changes or title/timestamp changed
    return (
      prevProps.isActive === nextProps.isActive &&
      prevProps.session.title === nextProps.session.title &&
      prevProps.session.updatedAt.getTime() ===
        nextProps.session.updatedAt.getTime() &&
      prevProps.editingSessionId === nextProps.editingSessionId &&
      prevProps.editingTitle === nextProps.editingTitle
    );
  },
);
SessionRow.displayName = "SessionRow";

export default function ChatSessions() {
  const t = useTranslations("Sessions");
  // const router = useRouter(); // Remove router
  const [activeSessionId, setActiveSessionId] = useAtom(activeSessionIdAtom);
  const [chatSessionsMap, setChatSessionsMap] = useAtom(chatSessionsMapAtom);
  const [sessionsList] = useAtom(sessionsListAtom);
  const [scrollPosition, setScrollPosition] = useAtom(
    chatSessionsListScrollAtom,
  );
  const [sessionsLoaded] = useAtom(sessionsLoadedAtom);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");

  // Sessions are now loaded by SessionInitializer at the top level
  // No need to load them here anymore

  // Restore scroll position after sessions load
  useEffect(() => {
    if (scrollContainerRef.current && scrollPosition > 0) {
      scrollContainerRef.current.scrollTop = scrollPosition;
    }
  }, [sessionsList.length, scrollPosition]);

  // Save scroll position when scrolling
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) return;

    const handleScroll = () => {
      setScrollPosition(scrollContainer.scrollTop);
    };

    scrollContainer.addEventListener("scroll", handleScroll);
    return () => scrollContainer.removeEventListener("scroll", handleScroll);
  }, [setScrollPosition]);

  const handleNewChat = () => {
    const newSessionId = generateUUID();

    // Create a new session in the frontend
    const newSession = {
      id: newSessionId,
      title: t("newChatTitle"),
      preview: "",
      createdAt: new Date(),
      updatedAt: new Date(), // This will be updated when first message is sent
      messageCount: 0,
    };

    // Add the new session to the sessions map
    setChatSessionsMap((prev) => ({
      ...prev,
      [newSessionId]: newSession,
    }));

    // Navigate to the new session
    // router.push(`/${newSessionId}`);
    setActiveSessionId(newSessionId);
  };

  const handleSessionSelect = (sessionId: string) => {
    // router.push(`/${sessionId}`);
    setActiveSessionId(sessionId);
  };

  const handleDeleteSession = async (
    sessionId: string,
    e: React.MouseEvent,
  ) => {
    e.stopPropagation();

    try {
      await deleteSession(sessionId); // Delete session from backend

      // Remove session from sessions map in frontend
      setChatSessionsMap((prev) => {
        const newMap = { ...prev };
        delete newMap[sessionId];
        return newMap;
      });

      // If deleting current session, redirect to a different session or home
      if (activeSessionId === sessionId) {
        const remainingSessions = sessionsList.filter(
          (session) => session.id !== sessionId,
        );
        if (remainingSessions.length > 0) {
          // router.push(`/${remainingSessions[0].id}`);
          setActiveSessionId(remainingSessions[0].id);
        } else {
          // No more sessions, create a new one using the existing handler
          handleNewChat();
        }
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
      // Optionally, show an error message to the user
    }
  };

  const handleRenameSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const session = chatSessionsMap[sessionId];
    if (session) {
      setEditingSessionId(sessionId);
      setEditingTitle(session.title);
    }
  };

  const handleSaveRename = async (sessionId: string) => {
    if (editingTitle.trim()) {
      try {
        // Update title in backend
        await updateSessionTitle(sessionId, editingTitle.trim());

        // Update title in frontend
        setChatSessionsMap((prev) => ({
          ...prev,
          [sessionId]: {
            ...prev[sessionId],
            title: editingTitle.trim(),
          },
        }));
      } catch (error) {
        console.error("Failed to update session title:", error);
        // Optionally show an error message to the user
      }
    }
    setEditingSessionId(null);
    setEditingTitle("");
  };

  const handleCancelRename = () => {
    setEditingSessionId(null);
    setEditingTitle("");
  };

  const handleKeyPress = (
    e: React.KeyboardEvent<HTMLInputElement>,
    sessionId: string,
  ) => {
    if (e.key === "Enter") {
      handleSaveRename(sessionId);
    } else if (e.key === "Escape") {
      handleCancelRename();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 pb-4 flex-shrink-0">
        <Button
          size="sm"
          onClick={handleNewChat}
          className="w-full justify-start gap-2"
        >
          <Plus className="h-4 w-4" />
          {t("newChat")}
        </Button>
      </div>

      {/* Sessions List */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
        <div className="p-2 space-y-1 relative">
          {!sessionsLoaded ? (
            <div className="text-center py-8 px-4">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto mb-2"></div>
              <p className="text-sm text-muted-foreground">
                {t("loading")}
              </p>
            </div>
          ) : sessionsList.length === 0 ? (
            <div className="text-center py-8 px-4">
              <p className="text-sm text-muted-foreground">
                {t("empty")}
              </p>
            </div>
          ) : (
            sessionsList.map((session) => (
              <SessionRow
                key={session.id}
                session={session}
                isActive={activeSessionId === session.id}
                onSelect={handleSessionSelect}
                onRename={handleRenameSession}
                onDelete={handleDeleteSession}
                editingSessionId={editingSessionId}
                editingTitle={editingTitle}
                setEditingTitle={setEditingTitle}
                handleKeyPress={handleKeyPress}
                formatTimestamp={formatTimestamp}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
