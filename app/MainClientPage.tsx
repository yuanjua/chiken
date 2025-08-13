"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useEffect } from "react";
import { activeSessionIdAtom, sessionsLoadedAtom, chatSessionsMapAtom } from "@/store/sessionAtoms";
import {
  isAppInitializedAtom,
  isBackendReadyAtom,
  resetLoadingStatesAtom,
} from "@/store/uiAtoms";
import ChatInterface from "@/components/chat/ChatInterface";
import { StartupScreen } from "@/components/StartupScreen";
import { generateUUID } from "@/lib/utils";
import { useTranslations } from "next-intl";

export default function MainClientPage() {
  const t = useTranslations("Common");
  const [isAppInitialized, setIsAppInitialized] = useAtom(isAppInitializedAtom);
  const isBackendReady = useAtomValue(isBackendReadyAtom);
  const setIsBackendReady = useSetAtom(isBackendReadyAtom);
  const setSessionsLoaded = useSetAtom(sessionsLoadedAtom);
  const resetLoadingStates = useSetAtom(resetLoadingStatesAtom);
  const [activeSessionId, setActiveSessionId] = useAtom(activeSessionIdAtom);
  const [chatSessionsMap, setChatSessionsMap] = useAtom(chatSessionsMapAtom);

  useEffect(() => {
    if (!isAppInitialized) {
      setIsBackendReady(false);
      setSessionsLoaded(false);
      resetLoadingStates();
    }
  }, [isAppInitialized, setIsBackendReady, setSessionsLoaded, resetLoadingStates]);

  useEffect(() => {
    if (isBackendReady && !activeSessionId) {
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
  }, [isBackendReady, activeSessionId, setActiveSessionId, setChatSessionsMap, t]);

  if (!isBackendReady) {
    return <StartupScreen onReady={() => setIsAppInitialized(true)} />;
  }

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

  return <ChatInterface sessionId={activeSessionId} />;
}


