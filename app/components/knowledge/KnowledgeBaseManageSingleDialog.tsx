"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  KnowledgeBase,
  processingDocumentIdsAtom,
  ragDocumentsAtom,
} from "@/store/ragAtoms";
import { Badge } from "@/components/ui/badge";
import { FileUpload } from "../rag/FileUpload";
import { Database, Loader2 } from "lucide-react";
import { useAtom } from "jotai";

interface KnowledgeBaseManageSingleDialogProps {
  kb: KnowledgeBase | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function KnowledgeBaseManageSingleDialog({
  kb,
  open,
  onOpenChange,
}: KnowledgeBaseManageSingleDialogProps) {
  const [processingDocumentIds] = useAtom(processingDocumentIdsAtom);
  const [ragDocuments] = useAtom(ragDocumentsAtom);

  if (!kb) return null;

  const isProcessing = ragDocuments.some(
    (doc) => doc.knowledgeBaseId === kb.id && processingDocumentIds.has(doc.id),
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg p-0 overflow-hidden">
        <DialogHeader className="p-6 border-b">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Database className="h-5 w-5" /> Manage &ldquo;{kb.name}&rdquo;
          </DialogTitle>
          <DialogDescription>
            Basic information and file upload for this knowledge base.
          </DialogDescription>
        </DialogHeader>

        <div className="p-6 space-y-6">
          {/* Info section */}
          <div className="space-y-2 text-sm">
            <div>
              <span className="font-medium">Description:</span>{" "}
              {kb.description || "—"}
            </div>
            <div>
              <span className="font-medium">Documents:</span>{" "}
              <Badge variant="secondary" className="flex items-center gap-1">
                {isProcessing && <Loader2 className="h-3 w-3 animate-spin" />}
                {kb.documentCount}
              </Badge>
            </div>
            {kb.createdAt && (
              <div>
                <span className="font-medium">Created:</span>{" "}
                {new Date(kb.createdAt).toLocaleDateString()}
              </div>
            )}
          </div>

          {/* Upload section */}
          <div>
            <h4 className="text-sm font-medium mb-2">Add files</h4>
            <FileUpload
              targetKnowledgeBase={{ id: kb.id, name: kb.name }}
              hideSupportMessage
            />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
