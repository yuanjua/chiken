import { X } from "lucide-react";
import { useUnifiedUpload } from "@/hooks/useUnifiedUpload";
import { useTranslations } from "next-intl";

export function UploadStatusDisplay() {
  const t = useTranslations("Common");
  const { activeUploads, failedUploads, removeUpload } = useUnifiedUpload();

  return (
    <>
      {(activeUploads.length > 0 || failedUploads.length > 0) && (
        <div className="flex flex-wrap gap-2">
          {activeUploads.map((upload) => (
            <div
              key={upload.id}
              className="inline-flex items-center gap-2 px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-sm rounded-md border border-blue-200 dark:border-blue-800"
            >
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              <span className="max-w-[200px] truncate" title={upload.file.name}>
                {upload.file.name}
              </span>
              <span className="text-xs">
                {upload.status === "uploading"
                  ? t("uploading")
                  : t("processing")}
              </span>
            </div>
          ))}
          {failedUploads.map((upload) => (
            <div
              key={upload.id}
              className="inline-flex items-center gap-2 px-3 py-1 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 text-sm rounded-md border border-red-200 dark:border-red-800"
            >
              <span className="max-w-[200px] truncate" title={upload.file.name}>
                {upload.file.name}
              </span>
              <span className="text-xs">{upload.error}</span>
              <button
                onClick={() => removeUpload(upload.id)}
                className="hover:bg-red-200 dark:hover:bg-red-800 rounded-full p-0.5"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
