import { useState, useCallback, useEffect, useRef } from "react";
import { ModelConfig } from "@/store/chatAtoms";
import { getOllamaModelList } from "@/lib/api-client";
import * as secretStore from "@/lib/secret-store";
import { isValidBaseUrl, validateBaseUrl } from "@/lib/utils";

export interface ConnectionState {
  status: "idle" | "connected" | "error" | "testing" | "pending";
  error: string | null;
  modelCount: number;
}

export function useProviderConnection(
  selectedModel: ModelConfig,
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void
) {
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: "idle",
    error: null,
    modelCount: 0,
  });
  const [envOllamaBase, setEnvOllamaBase] = useState<string>("");

  // Refs for managing debouncing and request cancellation
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const setState = (status: ConnectionState["status"], error: string | null = null, modelCount = 0) => {
    setConnectionState({ status, error, modelCount });
  };

  const testConnection = useCallback(async (provider: string, baseUrl?: string) => {
    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (provider !== "ollama" && provider !== "azure") {
      setState("connected");
      return true;
    }
    let effectiveBase = provider === "ollama" ? (baseUrl || envOllamaBase) : baseUrl;

    if (provider === "ollama" && !effectiveBase) {
      setState("error", "Base URL required for Ollama");
      return false;
    }

    // Validate URL format before making network request
    if (provider === "ollama" && effectiveBase) {
      const validation = validateBaseUrl(effectiveBase);
      if (!validation.isValid) {
        setState("error", validation.error || "Invalid URL format");
        return false;
      }
    }

    setState("testing");
    
    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();
    const currentController = abortControllerRef.current;

    try {
      if (provider === "ollama") {
        const response = await getOllamaModelList(effectiveBase || "", currentController.signal);
        
        // Check if this request was cancelled
        if (currentController.signal.aborted) {
          return false;
        }

        if (response.models) {
          setState("connected", null, response.models.length);
          return true;
        }
        if (response.error) {
          setState("error", response.error);
          return false;
        }
      }
      
      // Check if this request was cancelled
      if (currentController.signal.aborted) {
        return false;
      }

      setState("connected");
      return true;
    } catch (error) {
      // Don't show error if request was cancelled
      if (currentController.signal.aborted) {
        return false;
      }
      
      // Provide more specific error messages
      let errorMessage = "Failed to connect";
      if (error instanceof Error) {
        if (error.name === "AbortError") {
          return false; // Request was cancelled
        } else if (error.message.includes("fetch")) {
          errorMessage = `Network error: ${error.message}`;
        } else if (error.message.includes("timeout")) {
          errorMessage = "Connection timeout - please check the URL and try again";
        } else {
          errorMessage = error.message;
        }
      }
      
      setState("error", errorMessage);
      return false;
    }
  }, []);

  // Load OLLAMA_API_BASE from keychain
  useEffect(() => {
    const load = async () => {
      try {
        const envVars = await secretStore.getEnvVars();
        const value = envVars["OLLAMA_API_BASE"] || "";
        if (value) setEnvOllamaBase(value);
      } catch {}
    };
    load();
  }, []);

  const resetConnection = useCallback(() => {
    // Clear any pending debounced calls
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
      debounceTimeoutRef.current = null;
    }
    
    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    setState("idle");
  }, []);

    // Debounced connection test function
  const debouncedTestConnection = useCallback((provider: string, baseUrl?: string) => {
    // Clear existing timeout
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    // For URL validation, provide immediate feedback for invalid URLs
    if (provider === "ollama" && baseUrl) {
      const validation = validateBaseUrl(baseUrl);
      if (!validation.isValid) {
        setState("error", validation.error || "Invalid URL format");
        return;
      }
    }

    // Show pending state while waiting for debounce
    setState("pending");

    // Set new timeout for debounced execution - shorter for local validation, longer for network requests
    const debounceDelay = provider === "ollama" ? 800 : 500; // 800ms for ollama (network), 500ms for others
    debounceTimeoutRef.current = setTimeout(() => {
      testConnection(provider, baseUrl);
    }, debounceDelay);
  }, [testConnection]);

  // Auto-test connection when provider or auth details change (debounced)
  useEffect(() => {
    const currentProvider = selectedModel.provider || "openai";
    
    if (currentProvider === "ollama") {
      debouncedTestConnection(currentProvider, selectedModel.baseUrl || envOllamaBase);
    } else if (currentProvider !== "ollama") {
      debouncedTestConnection(currentProvider, selectedModel.baseUrl);
    } else {
      // If no base URL for ollama, reset to idle
      setState("idle");
    }
  }, [selectedModel.provider, selectedModel.baseUrl, envOllamaBase, debouncedTestConnection]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    connectionState,
    testConnection,
    resetConnection,
  };
}