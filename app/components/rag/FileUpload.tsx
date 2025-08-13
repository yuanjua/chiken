"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useAtom } from "jotai";
import { useUnifiedUpload } from "@/hooks/useUnifiedUpload";
import {
  knowledgeBasesAtom,
  activeKnowledgeBaseIdAtom,
  type KnowledgeBase,
} from "@/store/ragAtoms";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Upload, AlertCircle, CheckCircle, Hash } from "lucide-react";
import { FILE_SIZE_LIMITS } from "@/lib/file-utils";
import { useToast } from "@/hooks/use-toast";
import { useTranslations } from "next-intl";

interface KnowledgeBaseInfo {
  id: string;
  name: string;
}

interface FileUploadProps {
  hideSupportMessage?: boolean;
  targetKnowledgeBase?: KnowledgeBaseInfo | null;
  className?: string;
}

export function FileUpload({
  targetKnowledgeBase = null,
  className = "",
  hideSupportMessage = false,
}: FileUploadProps) {
  const [knowledgeBases] = useAtom(knowledgeBasesAtom);
  const [activeKbId] = useAtom(activeKnowledgeBaseIdAtom);
  const { toast } = useToast();
  const t = useTranslations("Upload");

  const { uploadFiles, activeUploads } = useUnifiedUpload({
    onUploadComplete: (fileId: string, filename: string) => {
      console.log("FileUpload: onUploadComplete called for:", fileId, filename);
      toast({
        title: t("successTitle"),
        description: t("successDesc", { filename }),
      });
    },
    onUploadError: (fileId: string, error: string) => {
      console.log("FileUpload: onUploadError called for:", fileId, error);
      toast({
        title: t("failedTitle"),
        description: error,
        variant: "destructive",
      });
    },
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      // Use unified upload with default options
      await uploadFiles(acceptedFiles);
    },
    [uploadFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/plain": [".txt"],
      "text/markdown": [".md"],
      "application/pdf": [".pdf"],
      "image/*": [".png", ".jpg", ".jpeg", ".gif"],
    },
    maxSize: FILE_SIZE_LIMITS.PDF_UPLOAD,
  });

  return (
    <div className="space-y-4">
      {/* Upload Area */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
          ${
            isDragActive
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50"
          }
        `}
      >
        <input {...getInputProps()} />
        <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
        {isDragActive ? (
          <p className="text-sm text-primary">{t("dropHere")}</p>
        ) : (
          <div>
            <p className="text-sm font-medium mb-1">
              {t("dropOrClick")}
            </p>
            {!hideSupportMessage && (
              <p className="text-xs text-muted-foreground">
                {t("supportsPdf")}
              </p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              📁 {t("uploadingTo")} {" "}
              {targetKnowledgeBase
                ? targetKnowledgeBase.name
                : activeKbId && activeKbId !== "uploaded-documents"
                  ? knowledgeBases.find((kb) => kb.id === activeKbId)?.name ||
                    t("unknownKb")
                  : t("uploadedDocumentsReserved")}
            </p>
          </div>
        )}
      </div>

      {/* Upload Progress */}
      {Object.keys(activeUploads).length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">{t("processing")}</p>
          {Object.entries(activeUploads).map(([uploadId, upload]) => (
            <div key={uploadId} className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                {upload.status === "processing" && (
                  <Hash className="h-4 w-4 animate-spin" />
                )}
                {upload.status === "uploading" && <Upload className="h-4 w-4" />}
                {upload.status === "completed" && (
                  <CheckCircle className="h-4 w-4 text-green-600" />
                )}
                {upload.status === "error" && (
                  <AlertCircle className="h-4 w-4 text-red-600" />
                )}
                <span className="truncate">{upload.file.name}</span>
                {upload.result?.message?.includes("duplicate") && (
                  <Badge variant="secondary" className="text-xs">
                    {t("duplicate")}
                  </Badge>
                )}
              </div>
              {upload.status === "processing" && (
                <p className="text-xs text-muted-foreground">
                  {t("generatingHash")}
                </p>
              )}
              {upload.status === "uploading" && (
                <Progress value={upload.progress || 0} className="h-2" />
              )}
              {upload.status === "completed" && upload.result?.message?.includes("duplicate") && (
                <p className="text-xs text-green-600">
                  {t("alreadyExists")}
                </p>
              )}
              {upload.status === "error" && (
                <p className="text-xs text-red-600">{upload.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
