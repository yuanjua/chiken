"use client";

import { useAtom } from "jotai";
import { useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  activeKnowledgeBaseAtom,
  activeKnowledgeBaseDocumentsAtom,
  selectedKnowledgeBaseIdsAtom,
  knowledgeBasesAtom,
  ragDocumentsAtom,
  activeKnowledgeBaseIdAtom,
} from "../../store/ragAtoms";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useKnowledgeBaseActions } from "@/hooks/useKnowledgeBaseActions";

interface KnowledgeBaseDocumentsSectionProps {
  setIsLoading: (state: boolean) => void;
}

export function KnowledgeBaseDocumentsSection({
  setIsLoading,
}: KnowledgeBaseDocumentsSectionProps) {
  const t = useTranslations("KB.Documents");
  const [activeKnowledgeBase] = useAtom(activeKnowledgeBaseAtom);
  const [documents] = useAtom(activeKnowledgeBaseDocumentsAtom);
  const [activeKnowledgeBaseIds] = useAtom(selectedKnowledgeBaseIdsAtom);
  // knowledgeBases local update handled by shared hook
  const [ragDocuments] = useAtom(ragDocumentsAtom);
  const [activeKnowledgeBaseId] = useAtom(activeKnowledgeBaseIdAtom);

  const filteredDocuments = documents;

  const { deleteDocument: removeDocument } =
    useKnowledgeBaseActions(setIsLoading);

  const handleDeleteDocument = (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const doc = documents.find((d) => d.id === docId);
    if (!doc) return;

    removeDocument(docId, doc.name, activeKnowledgeBaseId || undefined);
  };

  if (!(activeKnowledgeBaseIds.length === 1 && activeKnowledgeBase))
    return null;

  return (
    <div className="flex-1 flex flex-col">
      <div className="p-4 border-b">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">
            {t("title", { name: activeKnowledgeBase.name })}
          </h3>
          <Badge variant="outline">{t("docsCount", { count: documents.length })}</Badge>
        </div>
        {/* Search removed */}
      </div>
      {/* Upload removed – use Manage dialog instead */}
      <div className="flex-1 overflow-y-auto p-4">
        {filteredDocuments.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-sm text-muted-foreground">{t("empty")}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredDocuments.map((doc) => (
              <div
                key={doc.id}
                className="group p-3 rounded-md border bg-card hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm font-medium truncate">
                        {doc.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" className="text-xs">
                        {doc.type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {(doc.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                    {doc.uploadedAt && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(doc.uploadedAt).toLocaleDateString()}
                      </p>
                    )}
                  </div>
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
                        onClick={(e) => handleDeleteDocument(doc.id, e)}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        {t("delete")}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
