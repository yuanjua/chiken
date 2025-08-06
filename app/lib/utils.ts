import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function generateUUID(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
  id?: string;
}

export interface ProviderConfig {
  provider: "ollama" | "openai" | "anthropic";
  model: string;
  baseUrl?: string;
  apiKey?: string;
  temperature: number;
  numCtx?: number;
}

export interface ChatRequest {
  messages: ChatMessage[];
  providerConfig: ProviderConfig;
  sessionId?: string;
  provider: string;
  model: string;
  temperature?: number;
  topP?: number;
  stream?: boolean;
}

export function createDefaultConfig(
  provider: "ollama" | "openai" | "anthropic",
): ProviderConfig {
  let config: ProviderConfig;
  switch (provider) {
    case "ollama":
      config = {
        provider: "ollama",
        model: "llama2",
        baseUrl: "http://localhost:11434",
        temperature: 0.7,
        numCtx: 4096,
      };
      break;
    case "openai":
      config = {
        provider: "openai",
        model: "gpt-4-turbo",
        apiKey: "",
        temperature: 0.7,
      };
      break;
    case "anthropic":
      config = {
        provider: "anthropic",
        model: "claude-3-sonnet-20240229",
        apiKey: "",
        temperature: 0.7,
      };
      break;
    default:
      throw new Error("Unknown provider");
  }
  return config;
}

export function validateConfig(config: ProviderConfig): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];
  let valid = true;

  if (!config.model) {
    errors.push("Model is required.");
    valid = false;
  }

  if (config.provider === "ollama" && !config.baseUrl) {
    errors.push("Base URL is required for Ollama.");
    valid = false;
  }

  if (
    (config.provider === "openai" || config.provider === "anthropic") &&
    !config.apiKey
  ) {
    errors.push("API Key is required.");
    valid = false;
  }

  if (config.temperature < 0 || config.temperature > 1) {
    errors.push("Temperature must be between 0 and 1.");
    valid = false;
  }

  if (config.numCtx && config.numCtx <= 0) {
    errors.push("Context Size (numCtx) must be a positive number.");
    valid = false;
  }

  return { valid, errors };
}

export function generateSessionId(): string {
  return Date.now().toString(); // Simple ID for demo
}

export function formatMessage(message: ChatMessage): ChatMessage {
  // Ensure message has a timestamp for consistency
  return {
    ...message,
    timestamp: message.timestamp || new Date().toISOString(),
  };
}

export function createSystemMessage(content: string): ChatMessage {
  return { role: "system", content, timestamp: new Date().toISOString() };
}

export function createUserMessage(content: string): ChatMessage {
  return { role: "user", content, timestamp: new Date().toISOString() };
}

export function createAssistantMessage(content: string): ChatMessage {
  return { role: "assistant", content, timestamp: new Date().toISOString() };
}

/**
 * Show a user-friendly notification about storage issues
 */
export function notifyStorageIssue(): void {
  // Fallback to console for now - can be enhanced with proper toast integration later
  console.warn(
    "Storage quota warning: Chat history is getting large. Consider clearing some old conversations.",
  );
}

/**
 * Clean up localStorage when quota is exceeded
 */
export function cleanupLocalStorage(): void {
  try {
    // Remove oldest non-session items first
    const keys = Object.keys(localStorage);
    for (const key of keys) {
      if (!key.includes("session") && key !== "sessionMessages") {
        localStorage.removeItem(key);
        break; // Remove one item at a time
      }
    }
  } catch (error) {
    console.error("Error during localStorage cleanup:", error);
  }
}

export const isValidBaseUrl = (url: string) => {
  const isValidIPv4 = (host: string) => {
    const ipv4Pattern = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
    return ipv4Pattern.test(host);
  };

  const isValidDomain = (host: string) => {
    const domainPattern = /^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$/;
    return domainPattern.test(host);
  };

  const isLocalhost = (host: string) => host === "localhost";

  try {
    const { protocol, hostname, port } = new URL(url);

    if (!protocol.startsWith("http")) return false;
    if (!hostname) return false;

    const hasValidHost = isValidIPv4(hostname) || isValidDomain(hostname) || isLocalhost(hostname);
    const hasValidPort = !port || (Number(port) > 0 && Number(port) <= 65535);

    return hasValidHost && hasValidPort;
  } catch {
    return false;
  }
};

export const validateBaseUrl = (url: string): { isValid: boolean; error?: string } => {
  if (!url || url.trim() === "") {
    return { isValid: false, error: "URL is required" };
  }

  try {
    const { protocol, hostname, port } = new URL(url);

    if (!protocol.startsWith("http")) {
      return { isValid: false, error: "URL must start with http:// or https://" };
    }

    if (!hostname) {
      return { isValid: false, error: "Invalid hostname" };
    }

    const isValidIPv4 = (host: string) => {
      const ipv4Pattern = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
      return ipv4Pattern.test(host);
    };

    const isValidDomain = (host: string) => {
      const domainPattern = /^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$/;
      return domainPattern.test(host);
    };

    const isLocalhost = (host: string) => host === "localhost";

    const hasValidHost = isValidIPv4(hostname) || isValidDomain(hostname) || isLocalhost(hostname);
    if (!hasValidHost) {
      return { isValid: false, error: "Invalid hostname format" };
    }

    if (port && (Number(port) <= 0 || Number(port) > 65535)) {
      return { isValid: false, error: "Port must be between 1 and 65535" };
    }

    return { isValid: true };
  } catch {
    return { isValid: false, error: "Invalid URL format" };
  }
};
