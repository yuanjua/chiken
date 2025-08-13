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

export default function MainPage() {
  const [isAppInitialized, setIsAppInitialized] = useAtom(isAppInitializedAtom);
  const isBackendReady = useAtomValue(isBackendReadyAtom);
  const setIsBackendReady = useSetAtom(isBackendReadyAtom);
  const setSessionsLoaded = useSetAtom(sessionsLoadedAtom);
  const resetLoadingStates = useSetAtom(resetLoadingStatesAtom);
  const [activeSessionId, setActiveSessionId] = useAtom(activeSessionIdAtom);
  const [chatSessionsMap, setChatSessionsMap] = useAtom(chatSessionsMapAtom);

  // Reset backend ready state and all loading states when app starts
  useEffect(() => {
    console.log(
      "MainPage: Setting backend state, isAppInitialized:",
      isAppInitialized,
    );
    if (!isAppInitialized) {
      console.log("MainPage: Resetting all backend and loading states");
      setIsBackendReady(false);
      setSessionsLoaded(false);
      resetLoadingStates();
    }
  }, [
    isAppInitialized,
    setIsBackendReady,
    setSessionsLoaded,
    resetLoadingStates,
  ]);

  // Create a new chat session when backend is ready and no active session exists
  useEffect(() => {
    if (isBackendReady && !activeSessionId) {
      console.log("📝 Creating new chat session after backend ready");
      const newSessionId = generateUUID();
      const newSession = {
        id: newSessionId,
        title: "New Chat",
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
  }, [isBackendReady, activeSessionId, setActiveSessionId, setChatSessionsMap]);

  // Show StartupScreen until the backend is ready.
  if (!isBackendReady) {
    return <StartupScreen onReady={() => setIsAppInitialized(true)} />;
  }

  // If backend is ready but no active session yet, show loading
  if (!activeSessionId) {
    return (
      <div className="h-screen w-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-sm text-muted-foreground">Creating new chat...</p>
        </div>
      </div>
    );
  }

  return <ChatInterface sessionId={activeSessionId} />;
}
