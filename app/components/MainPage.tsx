"use client";

import { useAtom, useSetAtom } from "jotai";
import { useEffect } from "react";
import { activeSessionIdAtom, chatSessionsMapAtom } from "@/store/sessionAtoms";
import { isAppInitializedAtom } from "@/store/uiAtoms";
import ChatInterface from "@/components/chat/ChatInterface";
import { ConnectionScreen, useConnection } from "@/components/providers/ConnectionManager";
import { generateUUID } from "@/lib/utils";
import { useTranslations } from "next-intl";

export default function MainPage() {
  const t = useTranslations("Common");
  const { isReady: isBackendReady } = useConnection();
  const [isAppInitialized, setIsAppInitialized] = useAtom(isAppInitializedAtom);
  const [activeSessionId, setActiveSessionId] = useAtom(activeSessionIdAtom);
  const [chatSessionsMap, setChatSessionsMap] = useAtom(chatSessionsMapAtom);

  // Initialize app when backend is ready
  useEffect(() => {
    if (isBackendReady && !isAppInitialized) {
      console.log("✅ Backend is ready, initializing app");
      setIsAppInitialized(true);
    }
  }, [isBackendReady, isAppInitialized, setIsAppInitialized]);

  // Create initial session when backend is ready and no active session exists
  useEffect(() => {
    if (isBackendReady && isAppInitialized && !activeSessionId) {
      console.log("🆕 Creating initial chat session");
      const newSessionId = generateUUID();
      const newSession = {
        id: newSessionId,
        title: t("newChatTitle"),
        preview: "",
        createdAt: new Date(),
        updatedAt: new Date(),
        messageCount: 0,
      };

      setChatSessionsMap((prev) => ({
        ...prev,
        [newSessionId]: newSession,
      }));
      setActiveSessionId(newSessionId);
    }
  }, [isBackendReady, isAppInitialized, activeSessionId, setActiveSessionId, setChatSessionsMap, t]);

  // Show connection screen while not ready or initializing
  if (!isBackendReady || !isAppInitialized) {
    return <></>;
  }

  // Show loading while creating initial session
  if (!activeSessionId) {
    return (
      <div className="h-screen w-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-sm text-muted-foreground">{t("creatingNewChat")}</p>
        </div>
      </div>
    );
  }

  // Render the main chat interface
  return <ChatInterface sessionId={activeSessionId} />;
}