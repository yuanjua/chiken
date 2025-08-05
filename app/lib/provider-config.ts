export interface ProviderConfig {
  needsBaseUrl: boolean;
  needsApiKey: boolean;
  defaultBaseUrl?: string;
  placeholder?: string;
  customBaseUrlDefault: string;
}

export function getProviderConfig(provider: string): ProviderConfig {
  switch (provider) {
    case "ollama":
      return { 
        needsBaseUrl: true, 
        needsApiKey: false, 
        defaultBaseUrl: "http://localhost:11434", 
        customBaseUrlDefault: "http://localhost:11434" 
      };
    case "openai":
      return { 
        needsBaseUrl: false, 
        needsApiKey: true, 
        placeholder: "sk-...", 
        customBaseUrlDefault: "https://api.openai.com/v1" 
      };
    case "anthropic":
      return { 
        needsBaseUrl: false, 
        needsApiKey: true, 
        placeholder: "sk-ant-...", 
        customBaseUrlDefault: "https://api.anthropic.com" 
      };
    case "azure":
      return { 
        needsBaseUrl: true, 
        needsApiKey: true, 
        defaultBaseUrl: "https://your-resource.openai.azure.com", 
        placeholder: "Azure API key", 
        customBaseUrlDefault: "https://your-resource.openai.azure.com" 
      };
    default:
      return { 
        needsBaseUrl: false, 
        needsApiKey: true, 
        placeholder: "API key", 
        customBaseUrlDefault: "" 
      };
  }
}
