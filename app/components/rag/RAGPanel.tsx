"use client";

import { useAtom } from "jotai";
import {
  ragDocumentsAtom,
  selectedRAGDocumentsAtom,
  isRAGPanelOpenAtom,
  activeKnowledgeBaseAtom,
  activeKnowledgeBaseDocumentsAtom,
  knowledgeBasesAtom,
  activeKnowledgeBaseIdAtom,
} from "@/store/ragAtoms";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { FileUpload } from "./FileUpload";
import {
  FileText,
  Upload,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";

export function RAGPanel() {
  const t = useTranslations("RAGPanel");
  const [activeKnowledgeBase] = useAtom(activeKnowledgeBaseAtom);
  const [activeKbDocuments] = useAtom(activeKnowledgeBaseDocumentsAtom);
  const [selectedRAGDocs, setSelectedRAGDocs] = useAtom(
    selectedRAGDocumentsAtom,
  );
  const [isRAGPanelOpen, setIsRAGPanelOpen] = useAtom(isRAGPanelOpenAtom);
  const [knowledgeBases, setKnowledgeBases] = useAtom(knowledgeBasesAtom);
  const [activeKbId] = useAtom(activeKnowledgeBaseIdAtom);

  const handleDocumentToggle = (documentId: string) => {
    setSelectedRAGDocs((prev) =>
      prev.includes(documentId)
        ? prev.filter((id) => id !== documentId)
        : [...prev, documentId],
    );
  };

  const handleSelectAll = () => {
    const readyDocs = activeKbDocuments.filter((doc) => doc.status === "ready");
    setSelectedRAGDocs(readyDocs.map((doc) => doc.id));
  };

  const handleClearSelection = () => {
    setSelectedRAGDocs([]);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ready":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "processing":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <FileText className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const readyDocuments = activeKbDocuments.filter(
    (doc) => doc.status === "ready",
  );
  const selectedCount = selectedRAGDocs.filter((id) =>
    activeKbDocuments.some((doc) => doc.id === id),
  ).length;

  return (
    <div className="flex flex-col h-full bg-background border-l">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          <div>
            <h2 className="font-semibold">{activeKnowledgeBase.name}</h2>
            <p className="text-xs text-muted-foreground">
              {t("documentsCount", { count: activeKbDocuments.length })}
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsRAGPanelOpen(false)}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Upload Section */}
      <div className="p-4 border-b">
        <FileUpload />
      </div>

      {/* Document Selection Controls */}
      {readyDocuments.length > 0 && (
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium">
              {t("documentsHeader", { count: readyDocuments.length })}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectAll}
                disabled={selectedCount === readyDocuments.length}
              >
                {t("selectAll")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearSelection}
                disabled={selectedCount === 0}
              >
                {t("clear")}
              </Button>
            </div>
          </div>

          {selectedCount > 0 && (
            <Badge variant="secondary" className="w-full justify-center">
              {t("selectedForContext", { count: selectedCount })}
            </Badge>
          )}
        </div>
      )}

      {/* Documents List */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {activeKbDocuments.length === 0 ? (
            <div className="text-center py-8">
              <Upload className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-sm text-muted-foreground">
                {t("emptyKb")}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {t("uploadToStart")}
              </p>
            </div>
          ) : (
            activeKbDocuments.map((document) => (
              <Card key={document.id} className="p-3">
                <div className="flex items-start gap-3">
                  {document.status === "ready" && (
                    <Checkbox
                      checked={selectedRAGDocs.includes(document.id)}
                      onCheckedChange={() => handleDocumentToggle(document.id)}
                      className="mt-1"
                    />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {getStatusIcon(document.status)}
                      <span className="text-sm font-medium truncate">
                        {document.name}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{(document.size / 1024).toFixed(1)} KB</span>
                      <span>•</span>
                      <span>{document.type}</span>
                      {document.chunks && (
                        <>
                          <span>•</span>
                          <span>{t("chunksCount", { count: document.chunks })}</span>
                        </>
                      )}
                    </div>

                    {document.status === "error" && document.error && (
                      <p className="text-xs text-red-500 mt-1">
                        {document.error}
                      </p>
                    )}
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
