import { useState, useRef, useEffect } from "react";
import { useAtom } from "jotai";
import {
  activeKnowledgeBaseIdAtom,
  selectedKnowledgeBaseIdsAtom,
  selectedMentionDocumentsAtom,
  MentionDocument,
} from "@/store/ragAtoms";
import { selectedAgentAtom, availableAgentTypesAtom } from "@/store/chatAtoms";
import { isBackendReadyAtom } from "@/store/uiAtoms";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AtSign,
  FileText,
  MessageCircleMore,
  Globe,
  Search,
  Upload,
  CheckCircle,
} from "lucide-react";
import { FileUploadZone } from "../upload/FileUploadZone";
import { useUnifiedUpload } from "@/hooks/useUnifiedUpload";
import { getKnowledgeBaseDocuments } from "@/lib/api-client";
import { useTranslations } from "next-intl";

interface InputControlsProps {
  isLoading: boolean;
}

export function InputControls({ isLoading }: InputControlsProps) {
  const t = useTranslations("Common");
  const [activeKbId] = useAtom(activeKnowledgeBaseIdAtom);
  const [selectedAgent, setSelectedAgent] = useAtom(selectedAgentAtom);
  const [selectedMentionDocs, setSelectedMentionDocs] = useAtom(
    selectedMentionDocumentsAtom,
  );
  const [selectedKbIds] = useAtom(selectedKnowledgeBaseIdsAtom);
  const [isBackendReady] = useAtom(isBackendReadyAtom);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [showDocumentDropdown, setShowDocumentDropdown] = useState(false);
  const [availableDocuments, setAvailableDocuments] = useState<
    MentionDocument[]
  >([]);
  const [docSearch, setDocSearch] = useState("");
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [showFileUpload, setShowFileUpload] = useState(false);

  const {
    isUploading,
    handleFileChangeDefault,
    refreshDocumentList,
    targetKnowledgeBaseName,
    documentRefreshTrigger,
  } = useUnifiedUpload({
    autoAddToMentions: true,
    refreshKnowledgeBases: true,
    refreshDocuments: true,
    onUploadComplete: (fileId, filename) => {
      console.log("✅ InputControls: Upload completed for", filename);
      loadKnowledgeBaseDocuments();
    },
    onUploadError: (fileId, error) => {
      console.error("❌ InputControls: Upload failed:", error);
    },
  });

  useEffect(() => {
    if (showDocumentDropdown && isBackendReady === true) {
      loadKnowledgeBaseDocuments();
    }
  }, [
    showDocumentDropdown,
    isBackendReady,
    documentRefreshTrigger,
    selectedKbIds,
  ]);

  // Handle click outside to close dropdown
  // Adds and removes a mousedown event listener on the document to close the dropdown when clicking outside of it.
  useEffect(() => {
    const doc = (globalThis as any).document;
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowDocumentDropdown(false);
      }
    };

    if (showDocumentDropdown && doc) {
      doc.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      if (doc) doc.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showDocumentDropdown]);

  const loadKnowledgeBaseDocuments = async () => {
    const kbIdsToLoad =
      selectedKbIds.length > 0 ? selectedKbIds : activeKbId ? [activeKbId] : [];
    if (kbIdsToLoad.length === 0) return;

    if (isBackendReady !== true) {
      console.log(
        "🚫 InputControls: Backend not ready, skipping document loading",
      );
      return;
    }

    console.log("📚 InputControls: Loading documents for KB IDs:", kbIdsToLoad);
    setLoadingDocuments(true);
    try {
      const allDocs: any[] = [];
      await Promise.all(
        kbIdsToLoad.map(async (kbId) => {
          try {
            const resp = await getKnowledgeBaseDocuments(kbId);
            // FIX: Backend returns a list, not { documents: [...] }
            if (Array.isArray(resp)) {
              allDocs.push(
                ...resp.map((doc: any) => ({
                  id: doc.source || doc.key,
                  title: doc.title,
                  source: doc.source,
                  key: doc.key,
                })),
              );
            }
          } catch (err) {
            console.error("Failed to load docs for KB", kbId, err);
          }
        }),
      );
      // Remove duplicates by id
      const uniqueMap = new Map<string, MentionDocument>();
      allDocs.forEach((d) => {
        if (!uniqueMap.has(d.id)) uniqueMap.set(d.id, d);
      });
      setAvailableDocuments(Array.from(uniqueMap.values()));
      console.log(
        "✅ InputControls: Loaded",
        uniqueMap.size,
        "unique docs across KBs",
      );
    } finally {
      setLoadingDocuments(false);
    }
  };

  const handleDocumentSelect = (document: MentionDocument) => {
    const isAlreadySelected = selectedMentionDocs.find(
      (doc) => doc.id === document.id,
    );
    if (isAlreadySelected) {
      setSelectedMentionDocs((prev) =>
        prev.filter((doc) => doc.id !== document.id),
      );
    } else {
      setSelectedMentionDocs((prev) => [...prev, document]);
    }
  };

  // Use globalThis.alert to notify the user in the browser environment
  const handleAtButtonClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    if (selectedKbIds.length === 0 && !activeKbId) {
      if (typeof globalThis !== "undefined" && (globalThis as any).alert) {
        (globalThis as any).alert(t("selectKbFirst"));
      }
      return;
    }
    setShowDocumentDropdown(!showDocumentDropdown);
  };

  const handleFileUpload = () => {
    fileInputRef.current?.click();
  };

  // Simple fuzzy subsequence match (characters in order)
  const fuzzyMatch = (text: string, query: string): boolean => {
    if (!query) return true;
    let tIndex = 0;
    let qIndex = 0;
    const t = text.toLowerCase();
    const q = query.toLowerCase();
    while (tIndex < t.length && qIndex < q.length) {
      if (t[tIndex] === q[qIndex]) {
        qIndex += 1;
      }
      tIndex += 1;
    }
    return qIndex === q.length;
  };

  return (
    <div className="flex items-end gap-0 relative">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf"
        onChange={handleFileChangeDefault}
        className="hidden"
      />

      {/* @ Button with Dropdown */}
      <div className="relative" ref={dropdownRef}>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="shrink-0 h-9 w-9 p-0 border-0"
          disabled={isLoading || (selectedKbIds.length === 0 && !activeKbId)}
          onClick={(e) => handleAtButtonClick(e)}
        >
          <AtSign className="h-4 w-4" />
        </Button>

        {/* Document Dropdown */}
        {showDocumentDropdown && (
          <div
            className="absolute bottom-full mb-2 left-0 w-80 max-h-80 border rounded-lg shadow-lg z-50 flex flex-col"
            style={{
              backgroundColor: "hsl(var(--color-popover))",
              color: "hsl(var(--color-popover-foreground))",
              borderColor: "hsl(var(--color-border))",
            }}
          >
            <div className="p-2 flex-shrink-0 rounded-t-lg border-b space-y-1">
              <div className="text-sm font-medium">{t("selectDocuments")}</div>
              <div className="text-xs text-muted-foreground">
                {t("selectDocsHint", { selected: selectedMentionDocs.length, total: availableDocuments.length })}
              </div>
              {/* Search Box */}
              <input
                type="text"
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                placeholder={t("searchDocuments")}
                className="w-full px-2 py-1 text-xs border rounded-md"
              />
            </div>
            <div className="flex-1 overflow-y-auto max-h-48">
              {loadingDocuments ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {t("loadingDocuments")}
                </div>
              ) : availableDocuments.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {t("noDocsInKb")}
                </div>
              ) : (
                availableDocuments
                  .filter((doc) => fuzzyMatch(doc.title, docSearch))
                  .map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => handleDocumentSelect(doc)}
                      className={`w-full text-left p-3 border-b last:border-b-0 transition-colors ${
                        selectedMentionDocs.find(
                          (selected) => selected.id === doc.id,
                        )
                          ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
                          : "hover:bg-gray-100 dark:hover:bg-gray-700"
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className="relative">
                          <FileText className="h-4 w-4 mt-0.5 text-muted-foreground" />
                          {selectedMentionDocs.find(
                            (selected) => selected.id === doc.id,
                          ) && (
                            <CheckCircle className="absolute -top-1 -right-1 h-3 w-3 text-blue-600 dark:text-blue-400" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div
                            className="text-sm font-medium truncate"
                            title={doc.title}
                          >
                            {doc.title}
                          </div>
                          {doc.source && (
                            <div className="text-xs text-muted-foreground truncate">
                              {doc.source}
                            </div>
                          )}
                        </div>
                        {selectedMentionDocs.find(
                          (selected) => selected.id === doc.id,
                        ) && (
                          <div className="text-blue-600 dark:text-blue-400 text-xs font-medium">
                            Selected
                          </div>
                        )}
                      </div>
                    </button>
                  ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* File Upload Button */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="shrink-0 h-9 w-9 pr-3 border-0"
        disabled={isLoading || isUploading}
        onClick={handleFileUpload}
        title={`Upload PDF to ${targetKnowledgeBaseName}`}
      >
        <Upload className="h-4 w-4" />
      </Button>

      {/* Agent Selector */}
      <Select
        value={selectedAgent}
        onValueChange={(value: string) => setSelectedAgent(value)}
      >
        <SelectTrigger className="w-10 h-9 border-0 p-0 shadow-none ml-2" aria-label={selectedAgent}>
          {selectedAgent === "chat" && (
            <MessageCircleMore className="h-4 w-4" />
          )}
          {selectedAgent === "search_graph" && (
            <Globe className="h-4 w-4" />
          )}
          {selectedAgent === "deep_research" && (
            <Search className="h-4 w-4" />
          )}
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="chat">
            <div className="flex items-center gap-2">
              <MessageCircleMore className="h-4 w-4" />
              Chat
            </div>
          </SelectItem>
          <SelectItem value="search_graph">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Search
            </div>
          </SelectItem>
          <SelectItem value="deep_research">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4" />
              Deep Research
            </div>
          </SelectItem>
        </SelectContent>
      </Select>

      {showFileUpload && (
        <FileUploadZone onClose={() => setShowFileUpload(false)} />
      )}
    </div>
  );
}
