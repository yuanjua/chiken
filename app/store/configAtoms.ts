import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

// Backend configuration data
export interface ModelProvider {
  id: string;
  name: string;
  baseUrl?: string;
  apiKey?: string;
  models: Array<{
    id: string;
    name: string;
    contextLength?: number;
  }>;
}

export interface ParameterConfig {
  name: string;
  description: string;
  type: "slider" | "number_input" | "select" | "checkbox";
  min?: number;
  max?: number;
  step?: number;
  default: any;
  options?: Array<{ value: any; label: string }>;
}

export interface BackendConfig {
  providers: ModelProvider[];
  parameters: Record<string, ParameterConfig>;
}

// Default provider configurations
export const DEFAULT_PROVIDERS: ModelProvider[] = [
  {
    id: "openai",
    name: "OpenAI",
    models: [
      { id: "gpt-4-turbo", name: "GPT-4 Turbo", contextLength: 128000 },
      { id: "gpt-4", name: "GPT-4", contextLength: 8192 },
      { id: "gpt-3.5-turbo", name: "GPT-3.5 Turbo", contextLength: 16385 },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    models: [
      {
        id: "claude-3-opus-20240229",
        name: "Claude 3 Opus",
        contextLength: 200000,
      },
      {
        id: "claude-3-sonnet-20240229",
        name: "Claude 3 Sonnet",
        contextLength: 200000,
      },
      {
        id: "claude-3-haiku-20240307",
        name: "Claude 3 Haiku",
        contextLength: 200000,
      },
    ],
  },
  {
    id: "ollama",
    name: "Ollama",
    baseUrl: undefined,
    models: [
      { id: "llama2", name: "Llama 2", contextLength: 4096 },
      { id: "llama2:13b", name: "Llama 2 13B", contextLength: 4096 },
      { id: "llama2:70b", name: "Llama 2 70B", contextLength: 4096 },
      { id: "codellama", name: "Code Llama", contextLength: 16384 },
      { id: "mistral", name: "Mistral", contextLength: 8192 },
      { id: "mixtral", name: "Mixtral 8x7B", contextLength: 32768 },
      { id: "neural-chat", name: "Neural Chat", contextLength: 4096 },
      { id: "starcode", name: "StarCode", contextLength: 8192 },
    ],
  },
];

// Core configuration atoms
export const backendConfigAtom = atom<BackendConfig>({
  providers: DEFAULT_PROVIDERS,
  parameters: {},
});
export const selectedProviderIdAtom = atomWithStorage<string>(
  "selectedProviderId",
  "openai",
);
export const selectedModelIdAtom = atomWithStorage<string>(
  "selectedModelId",
  "gpt-4-turbo",
);
export const temperatureAtom = atomWithStorage<number>("temperature", 0.7);

// Derived atom for current AI parameters
export const currentAiParamsAtom = atom((get) => ({
  provider: get(selectedProviderIdAtom),
  model: get(selectedModelIdAtom),
  temperature: get(temperatureAtom),
}));

// Loading state for configuration
export const isConfigLoadingAtom = atom<boolean>(false);
export const configErrorAtom = atom<string | null>(null);
