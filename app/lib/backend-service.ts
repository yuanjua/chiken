import { DEFAULT_PROVIDERS, type ModelProvider } from "@/store/configAtoms";
import { ChatMessage } from "./utils";

export interface ChatRequest {
  provider: string;
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  numCtx?: number;
  stream?: boolean;
}

export interface ChatResponse {
  content: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

export class BackendService {
  private static instance: BackendService;
  private providers: Map<string, ModelProvider> = new Map();

  constructor() {
    // Initialize with default providers
    DEFAULT_PROVIDERS.forEach((provider) => {
      this.providers.set(provider.id, provider);
    });
  }

  static getInstance(): BackendService {
    if (!BackendService.instance) {
      BackendService.instance = new BackendService();
    }
    return BackendService.instance;
  }

  getProvider(providerId: string): ModelProvider | undefined {
    return this.providers.get(providerId);
  }

  getAllProviders(): ModelProvider[] {
    return Array.from(this.providers.values());
  }

  async checkLLMProviderHealth(providerId: string): Promise<boolean> {
    const provider = this.getProvider(providerId);
    if (!provider) return false;

    try {
      switch (providerId) {
        case "ollama":
          return await this.checkOllamaLLMHealth(provider);
        case "openai":
          return await this.checkOpenAILLMHealth();
        case "anthropic":
          return await this.checkAnthropicLLMHealth();
        default:
          return false;
      }
    } catch (error) {
      console.error(`Health check failed for ${providerId}:`, error);
      return false;
    }
  }

  private async checkOllamaLLMHealth(
    provider: ModelProvider,
  ): Promise<boolean> {
    try {
      const response = await fetch(`${provider.baseUrl}/api/tags`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  private async checkOpenAILLMHealth(): Promise<boolean> {
    // Check if API key is available (only on server side)
    if (typeof globalThis !== "undefined" && (globalThis as any).window) return true; // Client side
    return !!process.env.OPENAI_API_KEY;
  }

  private async checkAnthropicLLMHealth(): Promise<boolean> {
    // Check if API key is available (only on server side)
    if (typeof globalThis !== "undefined" && (globalThis as any).window) return true; // Client side
    return !!process.env.ANTHROPIC_API_KEY;
  }

  async getAvailableLLMModels(providerId: string): Promise<string[]> {
    const provider = this.getProvider(providerId);
    if (!provider) return [];

    try {
      switch (providerId) {
        case "ollama":
          return await this.getOllamaLLMModels(provider);
        case "openai":
        case "anthropic":
          return provider.models.map((m) => m.id);
        default:
          return [];
      }
    } catch (error) {
      console.error(`Failed to get models for ${providerId}:`, error);
      return provider.models.map((m) => m.id);
    }
  }

  private async getOllamaLLMModels(provider: ModelProvider): Promise<string[]> {
    try {
      const response = await fetch(`${provider.baseUrl}/api/tags`);
      if (!response.ok) throw new Error("Failed to fetch Ollama models");

      const data = await response.json() as { models?: any[] };
      return data.models?.map((model: any) => model.name) || [];
    } catch {
      // Return default models if API call fails
      return provider.models.map((m) => m.id);
    }
  }

  async sendLLMChatRequest(request: ChatRequest): Promise<Response> {
    const provider = this.getProvider(request.provider);
    if (!provider) {
      throw new Error(`Provider ${request.provider} not found`);
    }

    switch (request.provider) {
      case "ollama":
        return this.sendOllamaLLMChatRequest(provider, request);
      case "openai":
        return this.sendOpenAILLMChatRequest(request);
      case "anthropic":
        return this.sendAnthropicLLMChatRequest(request);
      default:
        throw new Error(`Unsupported provider: ${request.provider}`);
    }
  }

  private async sendOllamaLLMChatRequest(
    provider: ModelProvider,
    request: ChatRequest,
  ): Promise<Response> {
    const ollamaRequest = {
      model: request.model,
      messages: request.messages,
      stream: request.stream ?? true,
      options: {
        temperature: request.temperature ?? 0.7,
        num_ctx: request.numCtx ?? 2048,
      },
    };

    return fetch(`${provider.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(ollamaRequest),
    });
  }

  private async sendOpenAILLMChatRequest(
    request: ChatRequest,
  ): Promise<Response> {
    if (typeof globalThis !== "undefined" && (globalThis as any).window) {
      throw new Error("OpenAI requests must be made from server side");
    }

    const openaiRequest = {
      model: request.model,
      messages: request.messages,
      stream: request.stream ?? true,
      temperature: request.temperature ?? 0.7,
    };

    return fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify(openaiRequest),
    });
  }

  private async sendAnthropicLLMChatRequest(
    request: ChatRequest,
  ): Promise<Response> {
    if (typeof globalThis !== "undefined" && (globalThis as any).window) {
      throw new Error("Anthropic requests must be made from server side");
    }

    const anthropicRequest = {
      model: request.model,
      messages: request.messages,
      stream: request.stream ?? true,
      temperature: request.temperature ?? 0.7,
    };

    return fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.ANTHROPIC_API_KEY}`,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify(anthropicRequest),
    });
  }
}

export const backendService = BackendService.getInstance();
