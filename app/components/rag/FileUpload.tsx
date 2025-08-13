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

  const { uploadFiles, activeUploads } = useUnifiedUpload({
    onUploadComplete: (fileId: string, filename: string) => {
      console.log("FileUpload: onUploadComplete called for:", fileId, filename);
      toast({
        title: "Upload Successful",
        description: `${filename} uploaded successfully`,
      });
    },
    onUploadError: (fileId: string, error: string) => {
      console.log("FileUpload: onUploadError called for:", fileId, error);
      toast({
        title: "Upload Failed",
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
          <p className="text-sm text-primary">Drop files here...</p>
        ) : (
          <div>
            <p className="text-sm font-medium mb-1">
              Drop files here or click to browse
            </p>
            {!hideSupportMessage && (
              <p className="text-xs text-muted-foreground">
                Supports PDF (max 100MB)
              </p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              📁 Uploading to:{" "}
              {targetKnowledgeBase
                ? targetKnowledgeBase.name
                : activeKbId && activeKbId !== "uploaded-documents"
                  ? knowledgeBases.find((kb) => kb.id === activeKbId)?.name ||
                    "Unknown KB"
                  : "uploaded-documents (reserved)"}
            </p>
          </div>
        )}
      </div>

      {/* Upload Progress */}
      {Object.keys(activeUploads).length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Processing files...</p>
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
                    Duplicate
                  </Badge>
                )}
              </div>
              {upload.status === "processing" && (
                <p className="text-xs text-muted-foreground">
                  Generating hash and checking duplicates...
                </p>
              )}
              {upload.status === "uploading" && (
                <Progress value={upload.progress || 0} className="h-2" />
              )}
              {upload.status === "completed" && upload.result?.message?.includes("duplicate") && (
                <p className="text-xs text-green-600">
                  File already exists, using existing version
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
