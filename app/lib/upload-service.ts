/**
 * Unified Upload Service
 *
 * Centralizes all file upload logic, state management, and backend communication.
 * Provides a clean interface for different components to handle uploads consistently.
 */

import { v4 as uuidv4 } from "uuid";
import {
  uploadFile as apiUploadFile,
  getKnowledgeBases,
  getKnowledgeBaseDocuments,
  addDocuments,
} from "./api-client";
import type { MentionDocument } from "@/store/ragAtoms";
import { FILE_SIZE_LIMITS } from "./file-utils";

export interface UploadFile {
  id: string;
  file: File;
  status: "pending" | "uploading" | "processing" | "completed" | "error";
  progress?: number;
  error?: string;
  result?: UploadResult;
}

export interface UploadResult {
  success: boolean;
  filename: string;
  itemkey?: string;
  fulltext_itemkey?: string;
  content_hash?: string;
  chunks_added?: number;
  knowledge_base?: string;
  url?: string;
  message?: string;
  error?: string;
}

export interface UploadOptions {
  knowledgeBaseId?: string;
  onProgress?: (fileId: string, progress: number) => void;
  onStatusChange?: (fileId: string, status: UploadFile["status"]) => void;
  onComplete?: (fileId: string, result: UploadResult) => void;
  onError?: (fileId: string, error: string) => void;
}

export interface UploadCallbacks {
  onKnowledgeBaseUpdate?: () => Promise<void>;
  onDocumentListUpdate?: () => Promise<void>;
  onMentionDocumentAdd?: (doc: MentionDocument) => void;
}

export class UploadService {
  private uploadMap = new Map<string, UploadFile>();
  private callbacks: UploadCallbacks = {};

  setCallbacks(callbacks: UploadCallbacks) {
    this.callbacks = callbacks;
  }

  /**
   * Start uploading multiple files
   */
  async uploadFiles(
    files: File[],
    options: UploadOptions = {},
  ): Promise<string[]> {
    const fileIds: string[] = [];

    for (const file of files) {
      const fileId = uuidv4();
      fileIds.push(fileId);

      const uploadFile: UploadFile = {
        id: fileId,
        file,
        status: "pending",
      };

      this.uploadMap.set(fileId, uploadFile);

      // Start upload asynchronously
      this.processFileUpload(fileId, options);
    }

    return fileIds;
  }

  /**
   * Get upload status for a file
   */
  getUploadStatus(fileId: string): UploadFile | undefined {
    return this.uploadMap.get(fileId);
  }

  /**
   * Get all active uploads
   */
  getAllUploads(): UploadFile[] {
    return Array.from(this.uploadMap.values());
  }

  /**
   * Remove completed or failed uploads
   */
  cleanup(fileId?: string) {
    if (fileId) {
      this.uploadMap.delete(fileId);
    } else {
      // Clean up completed and error uploads
      const entriesToDelete: string[] = [];
      this.uploadMap.forEach((upload, id) => {
        if (upload.status === "completed" || upload.status === "error") {
          entriesToDelete.push(id);
        }
      });
      entriesToDelete.forEach((id) => this.uploadMap.delete(id));
    }
  }

  /**
   * Internal method to process a single file upload
   */
  private async processFileUpload(fileId: string, options: UploadOptions) {
    const uploadFileData = this.uploadMap.get(fileId);
    if (!uploadFileData) return;

    try {
      // Update to uploading
      this.updateStatus(fileId, "uploading");
      options.onStatusChange?.(fileId, "uploading");

      // Validate file
      const validation = this.validateFile(uploadFileData.file);
      if (!validation.valid) {
        throw new Error(validation.error);
      }

      // Check if this is a PDF and if PDF.js parsing is configured
      const isPDF = uploadFileData.file.type === "application/pdf";

      // Handle regular file upload
      await this.handleRegularUpload(fileId, options);
    } catch (error) {
      console.error(
        "❌ UploadService: Upload failed for",
        uploadFileData.file.name,
        ":",
        error,
      );

      const errorMessage =
        error instanceof Error ? error.message : "Upload failed";
      uploadFileData.error = errorMessage;
      this.updateStatus(fileId, "error");
      options.onStatusChange?.(fileId, "error");
      options.onError?.(fileId, errorMessage);
    }
  }

  private async handleRegularUpload(fileId: string, options: UploadOptions) {
    const uploadFileData = this.uploadMap.get(fileId);
    if (!uploadFileData) return;

    // Prepare form data
    const formData = new FormData();
    formData.append("file", uploadFileData.file);

    // Add knowledge base if specified
    if (options.knowledgeBaseId && options.knowledgeBaseId !== "kb-default") {
      formData.append("knowledge_base_name", options.knowledgeBaseId);
    }

    // Update to processing
    this.updateStatus(fileId, "processing");
    options.onStatusChange?.(fileId, "processing");

    // Upload file
    console.log(
      "🚀 UploadService: Starting upload for",
      uploadFileData.file.name,
    );
    const result = await apiUploadFile(formData);
    console.log(
      "📥 UploadService: Upload response for",
      uploadFileData.file.name,
      ":",
      result,
    );

    // Process result
    if (result.success) {
      // Update status to completed
      uploadFileData.result = result;
      this.updateStatus(fileId, "completed");
      options.onStatusChange?.(fileId, "completed");
      options.onComplete?.(fileId, result);

      // Handle mention document creation
      await this.handleMentionDocument(result);

      // Trigger updates
      await this.triggerUpdates();

      console.log(
        "✅ UploadService: Successfully uploaded",
        uploadFileData.file.name,
      );
    } else {
      throw new Error(result.error || "Upload failed");
    }
  }

  /**
   * Update upload status
   */
  private updateStatus(fileId: string, status: UploadFile["status"]) {
    const uploadFile = this.uploadMap.get(fileId);
    if (uploadFile) {
      uploadFile.status = status;
    }
  }

  /**
   * Validate file before upload
   */
  private validateFile(file: File): { valid: boolean; error?: string } {

    // Check file size (50MB limit)
    if (file.size > FILE_SIZE_LIMITS.PDF_UPLOAD) {
      return { valid: false, error: "File too large. Maximum size is 50MB" };
    }

    return { valid: true };
  }

  /**
   * Handle mention document creation
   */
  private async handleMentionDocument(result: UploadResult) {
    const key =
      result.itemkey || result.fulltext_itemkey || result.content_hash;

    if (key && this.callbacks.onMentionDocumentAdd) {
      const mentionDoc: MentionDocument = {
        id: key,
        title: result.filename,
        source: result.filename,
        key: key,
        content: "", // Agents will retrieve fulltext using key
      };

      this.callbacks.onMentionDocumentAdd(mentionDoc);
    }
  }

  /**
   * Trigger knowledge base and document list updates
   */
  private async triggerUpdates() {
    try {
      // Update knowledge bases
      if (this.callbacks.onKnowledgeBaseUpdate) {
        await this.callbacks.onKnowledgeBaseUpdate();
      }

      // Update document list
      if (this.callbacks.onDocumentListUpdate) {
        await this.callbacks.onDocumentListUpdate();
      }
    } catch (error) {
      console.error("Failed to trigger updates after upload:", error);
    }
  }
}

// Export singleton instance
export const uploadService = new UploadService();
