import { useAtom } from "jotai";
import {
  knowledgeBasesAtom,
  selectedKnowledgeBaseIdsAtom,
  activeKnowledgeBaseIdAtom,
  ragDocumentsAtom,
} from "@/store/ragAtoms";
import {
  updateKnowledgeBase as apiUpdateKnowledgeBase,
  deleteKnowledgeBase as apiDeleteKnowledgeBase,
  deleteDocument as apiDeleteDocument,
} from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { formatKbResultsAsPrompt } from "@/lib/utils";

export function useKnowledgeBaseActions(
  setIsLoading?: (state: boolean) => void,
) {
  const [knowledgeBases, setKnowledgeBases] = useAtom(knowledgeBasesAtom);
  const [activeKnowledgeBaseId, setActiveKnowledgeBaseId] = useAtom(
    activeKnowledgeBaseIdAtom,
  );
  const [selectedKnowledgeBaseIds, setSelectedKnowledgeBaseIds] = useAtom(
    selectedKnowledgeBaseIdsAtom,
  );
  const [, setRagDocuments] = useAtom(ragDocumentsAtom);
  const { toast } = useToast();

  /** Delete KB */
  const deleteKnowledgeBase = async (kbId: string) => {
    const kb = knowledgeBases.find((k) => k.id === kbId);
    if (!kb) return;

    try {
      setIsLoading?.(true);
      await apiDeleteKnowledgeBase(kbId);

      // Remove KB and its docs from local state
      setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== kbId));
      setRagDocuments((prev) =>
        prev.filter((doc) => doc.knowledgeBaseId !== kbId),
      );

      if (activeKnowledgeBaseId === kbId) {
        setActiveKnowledgeBaseId(null);
      }
      setSelectedKnowledgeBaseIds((prev) => prev.filter((id) => id !== kbId));
    } catch (err) {
      console.error("Failed to delete knowledge base:", err);
      toast({
        title: "Deletion Failed",
        description:
          err instanceof Error ? err.message : "An unknown error occurred.",
        variant: "destructive",
      });
    } finally {
      setIsLoading?.(false);
    }
  };

  /** Delete Document */
  const deleteDocument = async (
    docId: string,
    docName: string,
    knowledgeBaseId?: string,
  ) => {
    // Use globalThis.confirm to avoid TypeScript errors and ensure browser-only usage
    const confirmed =
      typeof globalThis !== "undefined" && (globalThis as any).confirm
        ? (globalThis as any).confirm(`Delete document "${docName}"?`)
        : false;
    if (!confirmed) return;

    try {
      setIsLoading?.(true);
      await apiDeleteDocument(docId);

      setRagDocuments((prev) => prev.filter((d) => d.id !== docId));

      if (knowledgeBaseId) {
        setKnowledgeBases((prev) =>
          prev.map((kb) =>
            kb.id === knowledgeBaseId
              ? { ...kb, documentCount: Math.max(0, kb.documentCount - 1) }
              : kb,
          ),
        );
      }
    } catch (err) {
      console.error("Failed to delete document:", err);
      toast({
        title: "Deletion Failed",
        description:
          err instanceof Error ? err.message : "An unknown error occurred.",
        variant: "destructive",
      });
    } finally {
      setIsLoading?.(false);
    }
  };

  /** Export search results as a formatted prompt */
  const exportResultsAsPrompt = (
    query: string,
    results: Array<{ content: string; metadata?: Record<string, any> }>,
  ) => {
    try {
      const prompt = formatKbResultsAsPrompt(query, results);
      // Copy to clipboard as default action
      const nav = (typeof globalThis !== "undefined" && (globalThis as any).navigator) ? (globalThis as any).navigator : null;
      if (nav && nav.clipboard && nav.clipboard.writeText) {
        nav.clipboard.writeText(prompt).then(() => {
          toast({ title: "Copied", description: "Prompt copied to clipboard." });
        });
      }
      return prompt;
    } catch (err) {
      console.error("Failed to export results:", err);
      toast({ title: "Export Failed", variant: "destructive" });
      return "";
    }
  };

  return {
    deleteKnowledgeBase,
    deleteDocument,
    exportResultsAsPrompt,
  } as const;
}
