import { useAtom } from "jotai";
import { useCallback } from "react";
import { fileUploadsAtom, type FileUpload } from "@/store/uiAtoms";

export function useFileUpload() {
  const [fileUploads, setFileUploads] = useAtom(fileUploadsAtom);

  const addFile = useCallback(
    (upload: FileUpload) => {
      setFileUploads((prev) => [...prev, upload]);
    },
    [setFileUploads],
  );

  const uploadFile = useCallback(
    async (upload: FileUpload) => {
      try {
        // Add file to uploads if not already there
        setFileUploads((prev) => {
          if (prev.find((u) => u.id === upload.id)) {
            // Update existing upload to uploading status
            return prev.map((u) =>
              u.id === upload.id ? { ...u, status: "uploading" } : u,
            );
          } else {
            // Add new upload with uploading status
            return [...prev, { ...upload, status: "uploading" }];
          }
        });

        const formData = new FormData();
        formData.append("file", upload.file);

        const xhr = new XMLHttpRequest();

        // Track upload progress
        xhr.upload.onprogress = (event) => {
          const progressEvent = event as ProgressEvent;
          if (progressEvent.lengthComputable) {
            const progress = Math.round(
              (progressEvent.loaded / progressEvent.total) * 100,
            );
            setFileUploads((prev) =>
              prev.map((u) => (u.id === upload.id ? { ...u, progress } : u)),
            );
          }
        };

        xhr.onload = () => {
          if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText || "{}");
            setFileUploads((prev) =>
              prev.map((u) =>
                u.id === upload.id
                  ? {
                      ...u,
                      status: "success",
                      progress: 100,
                      url: response.url,
                    }
                  : u,
              ),
            );
          }
        };

        xhr.onerror = () => {
          setFileUploads((prev) =>
            prev.map((u) =>
              u.id === upload.id
                ? { ...u, status: "error", error: "Upload failed" }
                : u,
            ),
          );
        };

        xhr.open("POST", "/api/upload");
        xhr.send(formData);
      } catch (error) {
        setFileUploads((prev) =>
          prev.map((u) =>
            u.id === upload.id
              ? {
                  ...u,
                  status: "error",
                  error:
                    error instanceof Error ? error.message : "Unknown error",
                }
              : u,
          ),
        );
      }
    },
    [setFileUploads],
  );

  const removeFile = useCallback(
    (id: string) => {
      setFileUploads((prev) => prev.filter((u) => u.id !== id));
    },
    [setFileUploads],
  );

  const clearCompletedUploads = useCallback(() => {
    setFileUploads((prev) => prev.filter((u) => u.status !== "success"));
  }, [setFileUploads]);

  return {
    fileUploads,
    addFile,
    uploadFile,
    removeFile,
    clearCompletedUploads,
    setFileUploads,
  };
}
