"use client";

import { useEffect } from "react";
import { useAtom } from "jotai";
import { sessionsLoadedAtom, chatSessionsMapAtom } from "@/store/sessionAtoms";
import { selectedAgentAtom } from "@/store/chatAtoms";
import { isBackendReadyAtom } from "@/store/uiAtoms";
import { listSessions, convertBackendSessionsToMap } from "@/lib/api-client";
import { tauriService } from "@/lib/tauri-service";
import { availableAgentTypesAtom } from "@/store/chatAtoms";
import { getAgentTypes } from "@/lib/api-client";

export function SessionInitializer() {
  const [sessionsLoaded, setSessionsLoaded] = useAtom(sessionsLoadedAtom);
  const [chatSessionsMap, setChatSessionsMap] = useAtom(chatSessionsMapAtom);
  const [isBackendReady] = useAtom(isBackendReadyAtom);
  const [, setSelectedAgent] = useAtom(selectedAgentAtom);
  const [, setAvailableAgents] = useAtom(availableAgentTypesAtom);

  useEffect(() => {
    async function loadAndSyncSessions() {
      // Skip if already loaded or if backend is not ready
      if (sessionsLoaded || isBackendReady !== true) {
        if (isBackendReady !== true) {
          console.log(
            "⏳ SessionInitializer: Waiting for backend to be ready (status:",
            isBackendReady,
            ")",
          );
        }
        return;
      }

      console.log("🔄 SessionInitializer: Loading sessions (backend ready)");
      try {
        // Load available agent types
        try {
          const agents = await getAgentTypes();
          if (Array.isArray(agents) && agents.length > 0) {
            setAvailableAgents(agents);
          }
        } catch (e) {
          console.warn("Failed to load agent types; defaulting to built-ins", e);
        }

        const response = await listSessions();
        const backendSessions = response.sessions || [];

        // Convert backend sessions to frontend format, preserving existing preview data
        const convertedSessions = convertBackendSessionsToMap(
          backendSessions,
          chatSessionsMap,
        );
        setChatSessionsMap(convertedSessions);
      } catch (error) {
        console.error("Failed to load or sync sessions:", error);
      } finally {
        setSessionsLoaded(true);
      }
    }

    // Only load sessions when backend is ready and sessions haven't been loaded yet
    if (!sessionsLoaded && isBackendReady === true) {
      loadAndSyncSessions();
    }
  }, [
    sessionsLoaded,
    setSessionsLoaded,
    setChatSessionsMap,
    isBackendReady,
    chatSessionsMap,
  ]);

  // Ensure default agent is always set to 'chat' on app start
  useEffect(() => {
    setSelectedAgent("chat");
  }, [setSelectedAgent]);

  // This component doesn't render anything
  return null;
}
