import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export interface ChatSession {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messageCount: number;
  model?: string;
  ragDocuments?: string[];
}

export interface ModelConfig {
  provider: string;
  model: string; // LiteLLM model name (e.g., "ollama/llama3", "gpt-4o", "anthropic/claude-3-opus")
  embeddingModel: string;
  embeddingProvider: string;
  temperature: number;
  apiKey?: string;
  baseUrl?: string;
  numCtx?: number;
  // System configuration properties
  systemPrompt?: string;
  maxHistoryLength?: number;
  memoryUpdateFrequency?: number;
  // PDF Parser configuration
  pdfParserType?: "kreuzberg" | "remote";
  pdfParserUrl?: string;
  // Document processing config
  chunkSize?: number;
  chunkOverlap?: number;
  enableReferenceFiltering?: boolean;
}

// Helper function to extract provider from model name
export function getProviderFromModel(model: string): "openai" | "anthropic" | "ollama" | "custom" {
  if (!model) return "custom";
  if (model.startsWith("ollama/")) return "ollama";
  if (model.startsWith("anthropic/") || model.startsWith("claude")) return "anthropic";
  if (model.startsWith("gpt-") || model.startsWith("text-") || model.startsWith("code-") || model.startsWith("ada-")) return "openai";
  if (model.includes("/")) {
    // Extract provider from prefix
    const provider = model.split("/")[0];
    switch (provider) {
      case "anthropic":
      case "openai":
      case "ollama":
        return provider as "openai" | "anthropic" | "ollama";
      default:
        return "custom";
    }
  }
  return "custom";
}

// Helper function to format model name for LiteLLM
export function formatModelForLiteLLM(provider: string, model: string): string {
  if (!model) return model;
  
  // If model already has provider prefix, return as-is if it matches the expected provider
  if (model.includes("/")) {
    const modelProvider = model.split("/")[0];
    if (modelProvider === provider) return model;
    // If providers don't match, clean and re-format
    model = model.split("/").slice(1).join("/");
  }
  
  switch (provider) {
    case "ollama":
      return `ollama/${model}`;
    case "anthropic":
      // Claude models can be used with or without prefix
      if (model.startsWith("claude")) return model;
      return `anthropic/${model}`;
    case "openai":
      // Most OpenAI models don't need prefix
      return model;
    case "azure":
      return `azure/${model}`;
    case "google":
      return `gemini/${model}`;
    case "groq":
      return `groq/${model}`;
    case "together_ai":
      return `together_ai/${model}`;
    case "replicate":
      return `replicate/${model}`;
    case "huggingface":
      return `huggingface/${model}`;
    default:
      // For custom providers, add provider prefix
      return `${provider}/${model}`;
  }
}

// Chat sessions management
export const chatSessionsAtom = atomWithStorage<ChatSession[]>(
  "chat-sessions",
  [],
);
export const currentSessionIdAtom = atomWithStorage<string | null>(
  "current-session-id",
  null,
);

// Current session derived atom
export const currentSessionAtom = atom((get) => {
  const sessions = get(chatSessionsAtom);
  const currentId = get(currentSessionIdAtom);
  return sessions.find((session) => session.id === currentId) || null;
});

// Model configuration with migration for bad baseUrl
const selectedModelBaseAtom = atomWithStorage<ModelConfig>(
  "selected-model",
  {
    provider: "ollama",
    model: "ollama/gemma3:latest",
    embeddingModel: "ollama/nomic-embed-text:latest",
    embeddingProvider: "ollama",
    temperature: 0.7,
    numCtx: 4096,
    systemPrompt: undefined,
    maxHistoryLength: 50,
    memoryUpdateFrequency: 5,
    pdfParserType: "kreuzberg",
    pdfParserUrl: undefined,
    chunkSize: 1600,
    chunkOverlap: 300,
    enableReferenceFiltering: true,
  }
);

export const selectedModelAtom = selectedModelBaseAtom;


// Chat UI state
export const isTypingAtom = atom<boolean>(false);
export const showModelSelectorAtom = atom<boolean>(false);

// Agent selection
// Agent types are now fetched dynamically from backend
export const selectedAgentAtom = atomWithStorage<string>(
  "selected-agent",
  "chat",
);

// Available agent types (fetched from API)
export const availableAgentTypesAtom = atom<string[]>(["chat"]);
