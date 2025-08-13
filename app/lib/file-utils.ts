/**
 * Frontend file utilities for processing uploads with SHA256 hashing and duplicate detection
 */

import { uploadFile } from "./api-client";

// File validation constants
export const FILE_SIZE_LIMITS = {
  PDF_UPLOAD: 100 * 1024 * 1024, // 100MB for PDF uploads in chat
  GENERAL_UPLOAD: 50 * 1024 * 1024, // 50MB for general file uploads
} as const;

export const ALLOWED_FILE_TYPES = {
  PDF: ["application/pdf"],
  IMAGES: ["image/jpeg", "image/png", "image/gif"],
  TEXT: ["text/plain", "text/markdown"],
  ALL: [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "text/plain",
    "text/markdown",
  ],
} as const;

/**
 * Validate file size against a limit
 */
export function validateFileSize(
  file: File,
  maxSize: number,
): { valid: boolean; error?: string } {
  if (file.size > maxSize) {
    return {
      valid: false,
      error: `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum size is ${(maxSize / 1024 / 1024).toFixed(0)}MB.`,
    };
  }
  return { valid: true };
}

/**
 * Validate file type against allowed types
 */
export function validateFileType(
  file: File,
  allowedTypes: readonly string[],
): { valid: boolean; error?: string } {
  if (!allowedTypes.includes(file.type)) {
    return {
      valid: false,
      error: `File type ${file.type} is not supported.`,
    };
  }
  return { valid: true };
}

/**
 * Comprehensive file validation for PDF uploads in chat
 */
export function validatePDFUpload(file: File): {
  valid: boolean;
  error?: string;
} {
  const typeValidation = validateFileType(file, ALLOWED_FILE_TYPES.PDF);
  if (!typeValidation.valid) {
    return typeValidation;
  }

  const sizeValidation = validateFileSize(file, FILE_SIZE_LIMITS.PDF_UPLOAD);
  if (!sizeValidation.valid) {
    return sizeValidation;
  }

  return { valid: true };
}

/**
 * Generate SHA256 hash of file content
 */
export async function generateFileHash(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hashHex;
}

/**
 * Extract clean title from filename (remove timestamp prefix and .pdf extension)
 */
export function extractCleanTitle(filename: string): string {
  if (!filename) return "";

  // Remove .pdf extension first
  let title = filename;
  if (title.endsWith(".pdf")) {
    title = title.slice(0, -4);
  }

  // Check if it's a timestamped filename (format: timestamp-originalname)
  if (title.includes("-") && title.split("-", 1)[0].match(/^\d+$/)) {
    // Remove timestamp prefix (e.g., "1750998755554-" from "1750998755554-Original Name")
    title = title.split("-").slice(1).join("-");
  }

  return title.trim();
}

/**
 * Check if a file with the same hash already exists in public uploads
 */
export async function checkFileExists(fileHash: string): Promise<{
  exists: boolean;
  url?: string;
}> {
  try {
    // Check if file exists in public uploads directory
    const response = await fetch(`/uploads/${fileHash}.pdf`, {
      method: "HEAD",
    });

    if (response.ok) {
      return {
        exists: true,
        url: `/uploads/${fileHash}.pdf`,
      };
    }

    return { exists: false };
  } catch (error) {
    console.error("Error checking file existence:", error);
    return { exists: false };
  }
}

/**
 * Enhanced file upload with hash-based duplicate detection
 */
export interface ProcessedFileUpload {
  file: File;
  hash: string;
  title: string;
  isDuplicate: boolean;
  existingUrl?: string;
}

/**
 * Process file for upload with duplicate detection
 */
export async function processFileForUpload(
  file: File,
): Promise<ProcessedFileUpload> {
  // Generate file hash
  const hash = await generateFileHash(file);

  // Extract clean title
  const title = extractCleanTitle(file.name);

  // Check for duplicates in public uploads
  const duplicateCheck = await checkFileExists(hash);

  return {
    file,
    hash,
    title,
    isDuplicate: duplicateCheck.exists,
    existingUrl: duplicateCheck.url,
  };
}

/**
 * Upload file with hash and title metadata
 */
export async function uploadFileWithMetadata(
  processedFile: ProcessedFileUpload,
  onProgress?: (progress: number) => void,
): Promise<{
  success: boolean;
  url?: string;
  error?: string;
  fromCache?: boolean;
}> {
  // If it's a duplicate, return the existing URL
  if (processedFile.isDuplicate && processedFile.existingUrl) {
    return {
      success: true,
      url: processedFile.existingUrl,
      fromCache: true,
    };
  }

  try {
    const formData = new FormData();
    formData.append("file", processedFile.file);
    formData.append("file_hash", processedFile.hash);
    formData.append("title", processedFile.title);

    // Use the API client upload function
    const result = await uploadFile(formData);

    return {
      success: true,
      url: result.url,
      fromCache: false,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Upload failed",
    };
  }
}
