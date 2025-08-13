/**
 * Chat Service
 *
 * Provides comprehensive chat functionality with configurable LLM providers.
 * Integrates with the backend chat API and manages provider configurations.
 */

import { ChatMessage, ProviderConfig, ChatRequest } from "./utils";
import { selectedModelAtom } from "@/store/chatAtoms";
import { useAtom } from "jotai";
import { useToast } from "@/hooks/use-toast";
import {
  updateSystemConfig,
  setModelParams,
} from "./api-client";

export interface ChatResponse {
  message: string;
  sessionId: string;
  providerInfo: Record<string, any>;
  timestamp: string;
}

export interface StreamEvent {
  type: "chunk" | "complete" | "error" | "provider_info";
  content: any;
  sessionId?: string;
  timestamp: string;
}

export interface ProviderInfo {
  name: string;
  available: boolean;
  description: string;
  supportsStreaming?: boolean;
  supportsMessages?: boolean;
  error?: string;
}

export interface ProvidersResponse {
  providers: Record<string, ProviderInfo>;
  totalCount: number;
  availableCount: number;
}

export interface ProviderTestResult {
  success: boolean;
  provider: string;
  error?: string;
}

export interface SaveConfigResult {
  success: boolean;
  message: string;
  error?: string;
}

class ChatService {
  private baseUrl: string;
  private abortController: AbortController | null = null;

  constructor() {
    this.baseUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8009";
  }

  /**
   * Send a chat message to the backend and get a complete response
   */
  async sendChatMessageToBackend(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/sessions/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messages: request.messages,
        provider_config: request.providerConfig,
        session_id: request.sessionId,
        stream: false,
      }),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ error: "Unknown error" }));
      throw new Error((error as any).detail || (error as any).error || `HTTP ${response.status}`);
    }

    // Fix return type for response.json()
    const data = await response.json();
    return data as unknown as ChatResponse;
  }

  /**
   * Stream a chat message response from the backend
   */
  async *streamChatMessageFromBackend(
    request: ChatRequest,
  ): AsyncGenerator<StreamEvent, void, unknown> {
    // Cancel any existing stream
    this.cancelStream();

    this.abortController = new AbortController();

    try {
      const response = await fetch(`${this.baseUrl}/sessions/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: request.messages,
          provider_config: request.providerConfig,
          session_id: request.sessionId,
          stream: true,
        }),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({ error: "Unknown error" }));
        throw new Error(
          (error as any).detail || (error as any).error || `HTTP ${response.status}`,
        );
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body reader available");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read(new Uint8Array());
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              yield data as StreamEvent;
            } catch (e) {
              console.warn("Failed to parse SSE data:", line);
            }
          }
        }
      }
    } finally {
      this.abortController = null;
    }
  }

  /**
   * Cancel the current streaming request
   */
  cancelStream(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /**
   * Get available LLM providers from the backend
   */
  async getAvailableLLMProviders(): Promise<ProvidersResponse> {
    const response = await fetch(`${this.baseUrl}/llm/providers`);

    if (!response.ok) {
      throw new Error(`Failed to fetch providers: HTTP ${response.status}`);
    }

    // Fix return type for response.json()
    const data = await response.json();
    return data as unknown as ProvidersResponse;
  }

  /**
   * Test a provider configuration with the backend
   */
  async testProviderConfiguration(
    config: ProviderConfig,
  ): Promise<ProviderTestResult> {
    try {
      // Use the unified backend to test configuration
      // First update the configuration with current settings
      const updates = {
        model_name: config.model,
        base_url: config.baseUrl,
        temperature: config.temperature,
        num_ctx: config.numCtx,
      };
      
      await updateSystemConfig(updates);
      
      // Test by trying to fetch models (which tests connectivity)
      const response = await fetch(`${process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || "http://localhost:8009"}/llm/models`);
      const result = await response.json();
      
      // Fix error property access by casting result to any
      return {
        success: !(result as any).error && response.ok,
        provider: config.provider,
        error: (result as any).error || (!response.ok ? "Connection failed" : undefined),
      };
    } catch (error) {
      return {
        success: false,
        provider: config.provider,
        error:
          error instanceof Error ? error.message : "Unknown error during test",
      };
    }
  }

  /**
   * Save provider configuration to the backend
   */
  async saveProviderConfiguration(
    config: ProviderConfig,
  ): Promise<SaveConfigResult> {
    try {
      // Use unified system config update
      const updates = {
        model_name: config.model,
        base_url: config.baseUrl,
        temperature: config.temperature || 0.7,
        num_ctx: config.numCtx || 2048,
      };
      
      const result = await updateSystemConfig(updates);
      
      return {
        success: true,
        message: "Configuration saved successfully",
      };
    } catch (error) {
      return {
        success: false,
        message: "Failed to save configuration",
        error:
          error instanceof Error ? error.message : "Unknown error during save",
      };
    }
  }

  /**
   * Get current provider configuration from the backend
   */
  async getCurrentProviderConfig(): Promise<ProviderConfig | null> {
    // This will likely be a GET request to a backend endpoint like /llm/config
    try {
      const response = await fetch(`${this.baseUrl}/llm/config`);
      if (!response.ok) {
        throw new Error(
          `Failed to fetch current config: HTTP ${response.status}`,
        );
      }
      const data = await response.json();
      return {
        // Fix property access by casting data to any
        provider: (data as any).provider,
        model: (data as any).model_name,
        temperature: (data as any).temperature,
        numCtx: (data as any).num_ctx,
        baseUrl: (data as any).base_url,
      };
    } catch (error) {
      console.error("Failed to get current provider config:", error);
      return null;
    }
  }

  /**
   * Check the overall health of the chat service and its dependencies.
   */
  async checkChatServiceHealth(): Promise<{
    backendStatus: "ok" | "error";
    llmStatus: "ok" | "error";
    llmError?: string;
  }> {
    try {
      const response = await fetch(`${this.baseUrl}/`);
      const backendStatus = response.ok ? "ok" : "error";

      let llmStatus: "ok" | "error" = "error";
      let llmError: string | undefined;

      try {
        // Check LLM status by trying to get providers
        const llmHealthResponse = await fetch(`${this.baseUrl}/llm/providers`);
        if (llmHealthResponse.ok) {
          llmStatus = "ok";
        } else {
          const errorData = await llmHealthResponse.json().catch(() => null);
          llmError =
            // Fix property access by casting errorData to any
            (errorData as any)?.detail ||
            `LLM providers check failed with status ${llmHealthResponse.status}`;
        }
      } catch (e) {
        llmError =
          e instanceof Error ? e.message : "Unknown LLM providers check error";
      }

      return { backendStatus, llmStatus, llmError };
    } catch (error) {
      return {
        backendStatus: "error",
        llmStatus: "error",
        llmError:
          error instanceof Error
            ? error.message
            : "Unknown backend health check error",
      };
    }
  }
}

export const chatService = new ChatService();
export default chatService;
