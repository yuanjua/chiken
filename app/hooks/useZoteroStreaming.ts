"use client";

import { useAtom } from "jotai";
import { useCallback } from "react";
import { ragDocumentsAtom, processingDocumentIdsAtom } from "@/store/ragAtoms";
import { addZoteroItemsToKnowledgeBaseStream } from "@/lib/api-client";
import { useToast } from "./use-toast";

export function useZoteroStreaming() {
  const [ragDocuments, setRagDocuments] = useAtom(ragDocumentsAtom);
  const [, setProcessingDocumentIds] = useAtom(processingDocumentIdsAtom);
  const { toast } = useToast();

  const streamZoteroItems = useCallback(
    async (
      knowledgeBaseName: string,
      knowledgeBaseId: string,
      zoteroKeys: string[],
    ) => {
      // Add to processing set
      setProcessingDocumentIds((prev) => {
        const newSet = new Set(prev);
        zoteroKeys.forEach((key) => newSet.add(key));
        return newSet;
      });

      // 1. Set initial pending state
      const placeholderDocs = zoteroKeys.map((key) => ({
        id: key,
        name: `Zotero Item ${key}`,
        status: "processing" as const,
        knowledgeBaseId: knowledgeBaseId,
        type: "zotero/item",
        size: 0,
        url: "",
        uploadedAt: new Date(),
      }));
      setRagDocuments((prev) => [
        ...prev.filter((doc) => !zoteroKeys.includes(doc.id)),
        ...placeholderDocs,
      ]);

      // 2. Define the progress handler
      const handleProgress = (progress: any) => {
        if (progress.status === "error") {
          console.error("Streaming error:", progress.error);
          toast({
            title: "Processing Error",
            description: progress.error,
            variant: "destructive",
          });
        }

        if (progress.current_item) {
          const { key, title, status } = progress.current_item;
          setRagDocuments((prev) =>
            prev.map((doc) =>
              doc.id === key
                ? {
                    ...doc,
                    name: title || doc.name,
                    status: status === "failed" ? "error" : "ready",
                  }
                : doc,
            ),
          );
        }

        if (progress.status === "completed") {
          toast({
            title: "Processing Complete",
            description: `Finished adding items to ${knowledgeBaseName}.`,
          });
        }
      };

      // 3. Start the streaming process
      try {
        await addZoteroItemsToKnowledgeBaseStream(
          knowledgeBaseName,
          zoteroKeys,
          handleProgress,
        );
      } catch (error) {
        console.error("Failed to start Zotero streaming:", error);
        toast({
          title: "Connection Error",
          description: "Could not connect to the backend.",
          variant: "destructive",
        });
        // Revert placeholders to an error state
        setRagDocuments((prev) =>
          prev.map((doc) =>
            zoteroKeys.includes(doc.id)
              ? { ...doc, status: "error", error: "Connection failed" }
              : doc,
          ),
        );
      } finally {
        // Remove from processing set
        setProcessingDocumentIds((prev) => {
          const newSet = new Set(prev);
          zoteroKeys.forEach((key) => newSet.delete(key));
          return newSet;
        });
      }
    },
    [setRagDocuments, toast, setProcessingDocumentIds],
  );

  return { streamZoteroItems };
}
