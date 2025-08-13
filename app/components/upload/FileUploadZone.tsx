"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { UploadIcon, FileIcon, ImageIcon, XIcon, CheckCircle, AlertCircle, Hash } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUnifiedUpload } from "@/hooks/useUnifiedUpload";
import { type UploadFile } from "@/lib/upload-service";
import { FILE_SIZE_LIMITS, ALLOWED_FILE_TYPES } from "@/lib/file-utils";
import { useToast } from "@/hooks/use-toast";
import { useTranslations } from "next-intl";

interface FileUploadZoneProps {
  onClose: () => void;
}

export function FileUploadZone({ onClose }: FileUploadZoneProps) {
  const [uploadError, setUploadError] = useState<string | null>(null);
  const { toast } = useToast();
  const t = useTranslations("UploadZone");

  // Use unified upload for consistency with other components
  const { uploadFiles, uploads, isUploading, removeUpload } = useUnifiedUpload({
    autoAddToMentions: true,
    refreshKnowledgeBases: true,
    refreshDocuments: true,
    onUploadComplete: (fileId: string, filename: string) => {
      console.log("FileUploadZone: Upload completed:", filename);
      toast({ title: t("successTitle"), description: t("successDesc", { filename }) });
    },
    onUploadError: (fileId: string, error: string) => {
      console.error("FileUploadZone: Upload error:", error);
      setUploadError(error);
      toast({ title: t("failedTitle"), description: error, variant: "destructive" });
    },
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setUploadError(null);

      // Validate files
      const validFiles = acceptedFiles.filter((file) => {
        if (file.size > FILE_SIZE_LIMITS.GENERAL_UPLOAD) {
          const errorMsg = t("tooLarge", { name: file.name, size: FILE_SIZE_LIMITS.GENERAL_UPLOAD / 1024 / 1024 });
          setUploadError(errorMsg);
          toast({
            title: t("tooLargeTitle"),
            description: errorMsg,
            variant: "destructive",
          });
          return false;
        }
        if (!ALLOWED_FILE_TYPES.ALL.includes(file.type as any)) {
          const errorMsg = t("unsupportedTypeDesc", { type: file.type });
          setUploadError(errorMsg);
          toast({
            title: t("unsupportedTypeTitle"),
            description: errorMsg,
            variant: "destructive",
          });
          return false;
        }
        return true;
      });

      if (validFiles.length > 0) {
        // Use unified upload - will upload to default KB "uploaded-documents"
        await uploadFiles(validFiles);
      }
    },
    [uploadFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [".png", ".jpg", ".jpeg", ".gif"],
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
    maxFiles: 5,
  });

  const getFileIcon = (file: File) => {
    if (file.type.startsWith("image/")) {
      return <ImageIcon className="h-6 w-6" />;
    }
    return <FileIcon className="h-6 w-6" />;
  };

  const getFilePreview = (upload: UploadFile) => {
    if (upload.file.type.startsWith("image/")) {
      return (
        <img
          src={URL.createObjectURL(upload.file)}
          alt={upload.file.name}
          className="w-12 h-12 object-cover rounded"
        />
      );
    }
    return getFileIcon(upload.file);
  };

  return (
    <Card className="border-dashed">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium">Upload Files</h3>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <XIcon className="h-4 w-4" />
          </Button>
        </div>

        {uploadError && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{uploadError}</AlertDescription>
          </Alert>
        )}

        {/* Dropzone */}
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
            isDragActive
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50",
          )}
        >
          <input {...getInputProps()} />
          <UploadIcon className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
          {isDragActive ? (
            <p className="text-sm text-muted-foreground">{t("dropHere")}</p>
          ) : (
            <div>
              <p className="text-sm text-muted-foreground mb-1">
                {t("dragOrClick")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("supports")}
              </p>
            </div>
          )}
        </div>

        {/* File List */}
        {uploads.length > 0 && (
          <div className="mt-4 space-y-2">
            {uploads.map((upload) => (
              <div
                key={upload.id}
                className="flex items-center gap-3 p-2 border rounded"
              >
                <div className="flex items-center gap-2">
                  {upload.status === "pending" && (
                    <Hash className="h-4 w-4 animate-spin text-blue-600" />
                  )}
                  {upload.status === "processing" && (
                    <Hash className="h-4 w-4 animate-spin text-blue-600" />
                  )}
                  {upload.status === "uploading" && (
                    <UploadIcon className="h-4 w-4 text-blue-600" />
                  )}
                  {upload.status === "completed" && (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  )}
                  {upload.status === "error" && (
                    <AlertCircle className="h-4 w-4 text-red-600" />
                  )}
                  {getFilePreview(upload)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {upload.file.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {(upload.file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  {upload.status === "processing" && (<p className="text-xs text-blue-600">{t("processingMentions")}</p>)}
                  {upload.status === "uploading" && (
                    <div className="mt-1">
                      <Progress value={upload.progress || 0} className="h-2" />
                      <p className="text-xs text-blue-600 mt-1">{t("uploadingToDefaultKb")}</p>
                    </div>
                  )}
                  {upload.status === "error" && (
                    <p className="text-xs text-destructive mt-1">
                      {upload.error}
                    </p>
                  )}
                  {upload.status === "completed" && (<p className="text-xs text-green-600 mt-1">{t("uploadComplete")}</p>)}
                  {upload.result?.message?.includes("duplicate") && (<Badge variant="secondary" className="text-xs mt-1">{t("duplicate")}</Badge>)}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => removeUpload(upload.id)}
                >
                  <XIcon className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
