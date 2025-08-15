"use client";

import { useAtom } from "jotai";
import { useState, useEffect, useCallback } from "react";
import {
  knowledgeBasesAtom,
  activeKnowledgeBaseIdAtom,
  activeKnowledgeBaseAtom,
  selectedKnowledgeBaseIdsAtom,
} from "../../store/ragAtoms";
import {
  isKnowledgeBaseSidebarOpenAtom,
  knowledgeBaseLoadedAtom,
  isBackendReadyAtom,
} from "../../store/uiAtoms";
import { Button } from "@/components/ui/button";
import { Plus, Database, X, Loader2, Lightbulb } from "lucide-react";
import { useTranslations } from "next-intl";
import { ConnectionOverlay } from "../providers/ConnectionManager";

import { KnowledgeBaseList } from "./KnowledgeBaseList";
import { KnowledgeBaseQuerySection } from "./KnowledgeBaseQuerySection";
// import { useStreamingProgressContext } from '@/components/providers/StreamingProgressProvider';
import { KnowledgeBaseCreationDialog } from "./KnowledgeBaseCreationDialog";
import { MCPSection } from "./MCPSection";
import {
  getKnowledgeBases,
  setActiveKnowledgeBases,
  getActiveKnowledgeBases,
} from "@/lib/api-client";

export function KnowledgeBaseSidebar() {
  const t = useTranslations("KB.Sidebar");
  const [knowledgeBases, setKnowledgeBases] = useAtom(knowledgeBasesAtom);
  const [activeKnowledgeBaseId, setActiveKnowledgeBaseId] = useAtom(
    activeKnowledgeBaseIdAtom,
  );
  const [activeKnowledgeBase] = useAtom(activeKnowledgeBaseAtom);
  // Document list no longer shown here
  const [, setIsKnowledgeBaseSidebarOpen] = useAtom(
    isKnowledgeBaseSidebarOpenAtom,
  );

  // query-related state has been moved to KnowledgeBaseQuerySection
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useAtom(knowledgeBaseLoadedAtom);
  const [isBackendReady] = useAtom(isBackendReadyAtom);

  // Multiple selection state (using persistent atom)
  const [activeKnowledgeBaseIds, setActiveKnowledgeBaseIds] = useAtom(
    selectedKnowledgeBaseIdsAtom,
  );

  const [hasInitializedSelections, setHasInitializedSelections] =
    useState(false);

  // Function to refresh knowledge bases list to get updated document counts
  const refreshKnowledgeBases = useCallback(async () => {
    try {
      const data = await getKnowledgeBases();
      if (data.knowledgeBases) {
        setKnowledgeBases(data.knowledgeBases);
      }
    } catch (error) {
      console.error("Failed to refresh knowledge bases:", error);
    }
  }, [setKnowledgeBases]);

  const loadAndSyncKnowledgeBases = useCallback(async () => {
    if (isBackendReady !== true) {
      console.log(
        "⏳ KnowledgeBaseSidebar: Waiting for backend to be ready (status:",
        isBackendReady,
        ")",
      );
      return;
    }

    console.log(
      "🔄 KnowledgeBaseSidebar: Loading and syncing knowledge bases...",
    );
    setIsLoading(true);
    setError(null);

    try {
      const data = await getKnowledgeBases();
      const fetchedKbs = data.knowledgeBases || [];
      setKnowledgeBases(fetchedKbs);

      const validKbIds = fetchedKbs.map((kb: any) => kb.id);

      // Get active knowledge bases from backend
      try {
        const activeData = await getActiveKnowledgeBases();
        const backendActiveIds = activeData.active_knowledge_bases || [];

        // Filter to only valid IDs that exist in the current KB list
        const validActiveIds = backendActiveIds.filter((id: string) =>
          validKbIds.includes(id),
        );

        if (validActiveIds.length > 0) {
          setActiveKnowledgeBaseIds(validActiveIds);
        } else {
          // If no valid active IDs from backend, use frontend logic
          setActiveKnowledgeBaseIds((currentSelectedIds) => {
            // Filter out any selected IDs that are no longer valid
            const validSelectedIds = currentSelectedIds.filter((id) =>
              validKbIds.includes(id),
            );

            // If no valid selections remain and we fetched KBs, select all by default
            if (validSelectedIds.length === 0 && validKbIds.length > 0) {
              return validKbIds;
            }

            return validSelectedIds;
          });
        }
      } catch (activeErr) {
        console.warn(
          "Failed to get active knowledge bases from backend, using frontend logic:",
          activeErr,
        );
        // Fallback to original logic
        setActiveKnowledgeBaseIds((currentSelectedIds) => {
          const validSelectedIds = currentSelectedIds.filter((id) =>
            validKbIds.includes(id),
          );
          if (validSelectedIds.length === 0 && validKbIds.length > 0) {
            return validKbIds;
          }
          return validSelectedIds;
        });
      }

      setHasLoaded(true);
    } catch (err: any) {
      console.error("Error loading knowledge bases:", err);
      setError("Failed to load knowledge bases.");
    } finally {
      setIsLoading(false);
    }
  }, [
    isBackendReady,
    setKnowledgeBases,
    setActiveKnowledgeBaseIds,
    setHasLoaded,
  ]);

  // Main effect for loading and syncing data
  useEffect(() => {
    loadAndSyncKnowledgeBases();
  }, [isBackendReady, loadAndSyncKnowledgeBases]);

  // Sync activeKnowledgeBaseId with activeKnowledgeBaseIds for @ button functionality
  useEffect(() => {
    // When the list of selected IDs changes, update the primary active KB.
    // Prioritize keeping the existing active KB if it's still in the list.
    const currentActiveIdIsValid =
      activeKnowledgeBaseId &&
      activeKnowledgeBaseIds.includes(activeKnowledgeBaseId);

    if (!currentActiveIdIsValid) {
      setActiveKnowledgeBaseId(
        activeKnowledgeBaseIds.length > 0 ? activeKnowledgeBaseIds[0] : null,
      );
    }
  }, [activeKnowledgeBaseIds, activeKnowledgeBaseId, setActiveKnowledgeBaseId]);

  // Sync frontend selection with backend
  useEffect(() => {
    const syncWithBackend = async () => {
      if (isBackendReady !== true || !hasLoaded) return;

      try {
        await setActiveKnowledgeBases(activeKnowledgeBaseIds);
        console.log(
          "✅ Synced active knowledge bases with backend:",
          activeKnowledgeBaseIds,
        );
      } catch (err) {
        console.warn(
          "Failed to sync active knowledge bases with backend:",
          err,
        );
      }
    };

    syncWithBackend();
  }, [activeKnowledgeBaseIds, isBackendReady, hasLoaded]);

  return (
    <div className="h-full flex flex-col bg-background relative">
      <ConnectionOverlay loadingText="Loading knowledge bases..." />
      {/* Compact Header */}
      <div className="flex items-center gap-2 pt-2 px-2 py-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsKnowledgeBaseSidebarOpen(false)}
          className="h-6 w-6 p-0 sidebar-button sidebar-icon-rotate-hover"
        >
          <X className="h-3 w-3 sidebar-icon" />
        </Button>
        <Lightbulb className="h-4 w-4" />
        <h3 className="text-sm font-medium">{t("title")}</h3>
        {isLoading && <Loader2 className="h-3 w-3 animate-spin ml-auto" />}
      </div>

      {/* New KB Button */}
      <div className="px-2 py-2">
        <KnowledgeBaseCreationDialog mode="standalone">
          <Button
            size="sm"
            className="w-full justify-start gap-2"
            disabled={isLoading}
          >
            <Plus className="h-4 w-4" />
            <span className="text-xs">{t("newKb")}</span>
          </Button>
        </KnowledgeBaseCreationDialog>
      </div>

      {/* Knowledge Bases List */}
      <KnowledgeBaseList setIsLoading={setIsLoading} />

      {/* MCP Section */}
      <MCPSection />

      {/* Query section now always visible */}
      <KnowledgeBaseQuerySection />
    </div>
  );
}
