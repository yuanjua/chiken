"use client";

import { useAtom } from "jotai";
import {
  knowledgeBasesAtom,
  selectedKnowledgeBaseIdsAtom,
  activeKnowledgeBaseIdAtom,
  ragDocumentsAtom,
  processingDocumentIdsAtom,
} from "../../store/ragAtoms";
import { isBackendReadyAtom } from "../../store/uiAtoms";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  MoreHorizontal,
  Trash2,
  Edit,
  Settings,
  Check,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { KnowledgeBaseManageSingleDialog } from "./KnowledgeBaseManageSingleDialog";
import { useKnowledgeBaseActions } from "@/hooks/useKnowledgeBaseActions";
import type { KnowledgeBase } from "@/store/ragAtoms";

interface KnowledgeBaseListProps {
  setIsLoading: (state: boolean) => void;
}

export function KnowledgeBaseList({ setIsLoading }: KnowledgeBaseListProps) {
  const t = useTranslations("KB.List");
  const [knowledgeBases, setKnowledgeBases] = useAtom(knowledgeBasesAtom);
  const [activeKnowledgeBaseIds, setActiveKnowledgeBaseIds] = useAtom(
    selectedKnowledgeBaseIdsAtom,
  );
  const [activeKnowledgeBaseId, setActiveKnowledgeBaseId] = useAtom(
    activeKnowledgeBaseIdAtom,
  );
  const [ragDocuments] = useAtom(ragDocumentsAtom);
  const [isBackendReady] = useAtom(isBackendReadyAtom);
  const [processingDocumentIds] = useAtom(processingDocumentIdsAtom);

  // Manage single KB dialog state
  const [manageKb, setManageKb] = useState<KnowledgeBase | null>(null);
  const isManageOpen = manageKb !== null;

  const handleToggleKnowledgeBase = (kbId: string) => {
    setActiveKnowledgeBaseIds((prev) => {
      const isSelected = prev.includes(kbId);
      const newSelection = isSelected
        ? prev.filter((id) => id !== kbId)
        : [...prev, kbId];

      // Update the active KB ID for single-selection-dependent features (mentions)
      if (!isSelected) {
        setActiveKnowledgeBaseId(kbId);
      } else if (isSelected && activeKnowledgeBaseId === kbId) {
        setActiveKnowledgeBaseId(newSelection[0] || null);
      }

      return newSelection;
    });
  };

  // Centralised KB actions
  const { deleteKnowledgeBase: removeKnowledgeBase } =
    useKnowledgeBaseActions(setIsLoading);

  // Track short-lived error flashes per KB
  const [flashErrors, setFlashErrors] = useState<Record<string, boolean>>({});
  const prevParsingRef = useRef<Record<string, boolean>>({});

  useEffect(() => {
    const newPrevParsing: Record<string, boolean> = {
      ...prevParsingRef.current,
    };

    knowledgeBases.forEach((kb) => {
      const isParsing = ragDocuments.some(
        (doc) =>
          doc.knowledgeBaseId === kb.id && processingDocumentIds.has(doc.id),
      );
      const docsForKb = ragDocuments.filter((d) => d.knowledgeBaseId === kb.id);
      const hadError = docsForKb.some((d) => d.status === "error");

      // Detect transition: was parsing -> now finished with errors
      if (newPrevParsing[kb.id] && !isParsing && hadError) {
        setFlashErrors((prev) => ({ ...prev, [kb.id]: true }));
        // Remove flash after 1 second
        setTimeout(() => {
          setFlashErrors((prev) => ({ ...prev, [kb.id]: false }));
        }, 1000);
      }

      newPrevParsing[kb.id] = isParsing;
    });

    prevParsingRef.current = newPrevParsing;
  }, [ragDocuments, knowledgeBases, processingDocumentIds]);

  if (!isBackendReady) {
    return null;
  }

  return (
    <div className="p-4">
      <div className="flex items-center">
        <h3 className="text-sm font-medium text-muted-foreground pb-2">
          {t("activeTitle")}
        </h3>
      </div>
      <ul className="max-h-32 overflow-y-auto border border-gray-400 rounded-sm divide-y divide-border divide-gray-200">
        {knowledgeBases.length === 0 ? (
          <div className="text-center py-4 text-sm text-muted-foreground">
            {t("empty")}
          </div>
        ) : (
          knowledgeBases.map((kb) => {
            const isProcessing = ragDocuments.some(
              (doc) =>
                doc.knowledgeBaseId === kb.id &&
                processingDocumentIds.has(doc.id),
            );
            const isFlashingError = flashErrors[kb.id];
            const isSelected = activeKnowledgeBaseIds.includes(kb.id);
            return (
              <li key={kb.id} className="group transition-colors">
                <div
                  className={`flex items-center justify-between px-2 py-1 cursor-pointer ${
                    isSelected ? "bg-muted" : "hover:bg-muted/40"
                  }`}
                  onClick={() => handleToggleKnowledgeBase(kb.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-xs font-medium truncate">
                      {kb.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    {isProcessing ? (
                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                    ) : isFlashingError ? (
                      <AlertCircle className="h-3 w-3 text-orange-500" />
                    ) : (
                      isSelected && <Check className="h-3 w-3 text-primary" />
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="h-3 w-3" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          data-no-toggle="true"
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={(e) => {
                            e.stopPropagation();
                            setManageKb(kb);
                          }}
                          className="cursor-pointer hover:bg-muted data-[highlighted]:bg-muted"
                        >
                          <Settings className="h-4 w-4 mr-2" />
                          Manage
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          data-no-toggle="true"
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={(e) => {
                            e.stopPropagation();
                            removeKnowledgeBase(kb.id);
                          }}
                          className="text-destructive focus:text-destructive cursor-pointer hover:bg-destructive/10 data-[highlighted]:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              </li>
            );
          })
        )}
      </ul>
      {activeKnowledgeBaseIds.length > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
          <span>
            {t("clearHint", { count: activeKnowledgeBaseIds.length })}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setActiveKnowledgeBaseIds([]);
            }}
            className="h-4 px-2 text-xs"
          >
            {t("clear")}
          </Button>
        </div>
      )}
      {/* Manage Dialog */}
      <KnowledgeBaseManageSingleDialog
        kb={manageKb}
        open={isManageOpen}
        onOpenChange={(open) => {
          if (!open) setManageKb(null);
        }}
      />
    </div>
  );
}
