/**
 * Unified Upload Hook
 *
 * Provides a React hook interface to the upload service.
 * Manages component state integration and provides reactive updates.
 */

import { useState, useEffect, useCallback } from "react";
import { useAtom } from "jotai";
import {
  activeKnowledgeBaseIdAtom,
  selectedMentionDocumentsAtom,
  knowledgeBasesAtom,
  selectedKnowledgeBaseIdsAtom,
  MentionDocument,
} from "@/store/ragAtoms";
import { getKnowledgeBases, getKnowledgeBaseDocuments, setActiveKnowledgeBases } from "@/lib/api-client";
import {
  uploadService,
  type UploadFile,
  type UploadOptions,
} from "@/lib/upload-service";

export interface UseUnifiedUploadProps {
  /** Whether to automatically add uploaded files to mention documents */
  autoAddToMentions?: boolean;
  /** Whether to refresh knowledge bases after upload */
  refreshKnowledgeBases?: boolean;
  /** Whether to refresh document list after upload */
  refreshDocuments?: boolean;
  /** Custom callback when upload completes */
  onUploadComplete?: (fileId: string, filename: string) => void;
  /** Custom callback when upload fails */
  onUploadError?: (fileId: string, error: string) => void;
}

export function useUnifiedUpload(props: UseUnifiedUploadProps = {}) {
  const {
    autoAddToMentions = true,
    refreshKnowledgeBases = true,
    refreshDocuments = true,
    onUploadComplete,
    onUploadError,
  } = props;

  const [activeKbId] = useAtom(activeKnowledgeBaseIdAtom);
  const [selectedMentionDocs, setSelectedMentionDocs] = useAtom(
    selectedMentionDocumentsAtom,
  );
  const [knowledgeBases, setKnowledgeBases] = useAtom(knowledgeBasesAtom);
  const [selectedKbIds, setSelectedKbIds] = useAtom(selectedKnowledgeBaseIdsAtom);

  const [uploads, setUploads] = useState<UploadFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [documentRefreshTrigger, setDocumentRefreshTrigger] = useState(0);

  const fetchKbs = useCallback(async () => {
    try {
      const data = await getKnowledgeBases();
      if (data.knowledgeBases) {
        setKnowledgeBases(data.knowledgeBases);
        return data.knowledgeBases;
      }
    } catch (error) {
      console.error(
        "useUnifiedUpload: Failed to fetch knowledge bases:",
        error,
      );
    }
    return [];
  }, [setKnowledgeBases]);

  useEffect(() => {
    fetchKbs();
  }, [documentRefreshTrigger, fetchKbs]);

  // Update local state when uploads change
  useEffect(() => {
    const interval = setInterval(() => {
      const currentUploads = uploadService.getAllUploads();
      setUploads([...currentUploads]);

      // Check if any uploads are active
      const hasActiveUploads = currentUploads.some(
        (upload) =>
          upload.status === "pending" ||
          upload.status === "uploading" ||
          upload.status === "processing",
      );
      setIsUploading(hasActiveUploads);
    }, 100);

    return () => clearInterval(interval);
  }, []);

  // Setup callbacks
  useEffect(() => {
    uploadService.setCallbacks({
      onKnowledgeBaseUpdate: refreshKnowledgeBases
        ? async () => {
            try {
              const data = await getKnowledgeBases();
              if (data.knowledgeBases) {
                console.log("📊 useUnifiedUpload: Refreshing knowledge bases");
                const newKbs = data.knowledgeBases;
                setKnowledgeBases(newKbs);
                
                // Check if any new KBs were added and activate them
                const currentKbIds = knowledgeBases.map(kb => kb.id);
                const newKbIds = newKbs.map((kb: any) => kb.id);
                const addedKbIds = newKbIds.filter((id: string) => !currentKbIds.includes(id));
                
                if (addedKbIds.length > 0) {
                  console.log("📊 useUnifiedUpload: Activating newly created KBs:", addedKbIds);
                  const updatedSelectedIds = [...selectedKbIds, ...addedKbIds];
                  setSelectedKbIds(updatedSelectedIds);
                  
                  // Sync with backend
                  try {
                    await setActiveKnowledgeBases(updatedSelectedIds);
                  } catch (error) {
                    console.warn("Failed to sync active KBs with backend:", error);
                  }
                }
              }
            } catch (error) {
              console.error("Failed to refresh knowledge bases:", error);
            }
          }
        : undefined,

      onDocumentListUpdate: refreshDocuments
        ? async () => {
            console.log("📚 useUnifiedUpload: Document list refresh requested");
            // Trigger document refresh for components that use this hook
            setDocumentRefreshTrigger((prev) => prev + 1);
          }
        : undefined,

      onMentionDocumentAdd: autoAddToMentions
        ? (doc: MentionDocument) => {
            setSelectedMentionDocs((prev) => {
              const existingIndex = prev.findIndex(
                (existing) => existing.id === doc.id,
              );
              if (existingIndex >= 0) {
                const updated = [...prev];
                updated[existingIndex] = doc;
                return updated;
              } else {
                return [...prev, doc];
              }
            });
          }
        : undefined,
    });
  }, [
    refreshKnowledgeBases,
    refreshDocuments,
    autoAddToMentions,
    setKnowledgeBases,
    setSelectedMentionDocs,
    knowledgeBases,
    selectedKbIds,
    setSelectedKbIds,
  ]);

  /**
   * Upload multiple files
   */
  const uploadFiles = useCallback(
    async (files: File[]): Promise<string[]> => {
      if (files.length === 0) return [];

      const options: UploadOptions = {
        knowledgeBaseId: activeKbId || "uploaded-documents",
        onComplete: (fileId, result) => {
          onUploadComplete?.(fileId, result.filename);
        },
        onError: (fileId, error) => {
          onUploadError?.(fileId, error);
        },
      };

      return uploadService.uploadFiles(files, options);
    },
    [activeKbId, onUploadComplete, onUploadError],
  );

  /**
   * Upload a single file
   */
  const uploadFile = useCallback(
    async (file: File): Promise<string> => {
      const [fileId] = await uploadFiles([file]);
      return fileId;
    },
    [uploadFiles],
  );

  const uploadToDefault = async (files: File[]) => {
    // Directly call uploadService.uploadFiles with the default knowledgeBaseId
    return uploadService.uploadFiles(files, { knowledgeBaseId: "uploaded-documents" });
  };

  /**
   * Handle file input change event
   */
  const createFileChangeHandler = (uploadFn: (files: File[]) => Promise<any>) =>
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (!files || files.length === 0) return;
      await uploadFn(Array.from(files));
      event.target.value = "";
  };
  const handleFileChange = createFileChangeHandler(uploadFiles);
  const handleFileChangeDefault = createFileChangeHandler(uploadToDefault);

  /**
   * Remove an upload from tracking
   */
  const removeUpload = useCallback((fileId: string) => {
    uploadService.cleanup(fileId);
  }, []);

  /**
   * Clear all completed/failed uploads
   */
  const clearCompleted = useCallback(() => {
    uploadService.cleanup();
  }, []);

  /**
   * Get uploads by status
   */
  const getUploadsByStatus = useCallback(
    (status: UploadFile["status"]) => {
      return uploads.filter((upload) => upload.status === status);
    },
    [uploads],
  );

  /**
   * Trigger document list refresh (for components that need it)
   */
  const refreshDocumentList = useCallback(async () => {
    if (!activeKbId) {
      return [];
    }

    let kbs = knowledgeBases;
    // If KBs are not loaded yet, fetch them to avoid a race condition
    if (kbs.length === 0) {
      kbs = await fetchKbs();
    }

    const knowledgeBase = kbs.find((kb) => kb.id === activeKbId);

    if (!knowledgeBase) {
      console.error(
        `useUnifiedUpload: Knowledge base with ID '${activeKbId}' not found.`,
      );
      return [];
    }

    try {
      const data = await getKnowledgeBaseDocuments(knowledgeBase.name);
      return data.documents || [];
    } catch (error) {
      console.error(
        `useUnifiedUpload: Failed to refresh document list for KB '${knowledgeBase.name}':`,
        error,
      );
      return [];
    }
  }, [activeKbId, knowledgeBases, fetchKbs]);

  return {
    // Upload actions
    uploadFiles,
    uploadFile,
    uploadToDefault,
    handleFileChange,
    handleFileChangeDefault,

    // State
    uploads,
    isUploading,
    activeUploads: getUploadsByStatus("uploading").concat(
      getUploadsByStatus("processing"),
    ),
    completedUploads: getUploadsByStatus("completed"),
    failedUploads: getUploadsByStatus("error"),

    // Utility functions
    removeUpload,
    clearCompleted,
    getUploadsByStatus,
    refreshDocumentList,

    // Configuration
    targetKnowledgeBase: activeKbId || "uploaded-documents",
    targetKnowledgeBaseName:
      knowledgeBases.find((kb) => kb.id === activeKbId)?.name ||
      "uploaded-documents",

    // Refresh trigger for components to watch
    documentRefreshTrigger,
  };
}
