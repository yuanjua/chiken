import { useState, useEffect, useRef, useCallback } from "react";
import { 
  getModelSuggestions, 
  getLiteLLMProviderModels,
  getAvailableProviders,
  getOllamaModelList,
} from "@/lib/api-client";
import { formatModelForLiteLLM } from "@/store/chatAtoms";
import * as secretStore from "@/lib/secret-store";

export interface ModelSuggestion {
  id: string;
  name: string;
  cost_info?: {
    input_cost_per_token?: number;
    output_cost_per_token?: number;
  };
}

interface ProviderSelectionOptions {
  initialProvider?: string;
  initialModel?: string;
  initialBaseUrl?: string;
  onProviderChange?: (provider: string) => void;
  onModelChange?: (model: string) => void;
  embedding?: boolean;
}

export function useProviderSelection({
  initialProvider = "openai",
  initialModel = "",
  initialBaseUrl = "",
  onProviderChange,
  onModelChange,
  embedding = false,
}: ProviderSelectionOptions = {}) {
  // Provider state
  const [provider, setProvider] = useState(initialProvider);
  const [availableProviders, setAvailableProviders] = useState<Record<string, any>>({});

  // Model input and suggestions state
  const [modelInput, setModelInput] = useState(initialModel);
  const [suggestions, setSuggestions] = useState<ModelSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Optional baseUrl for Ollama
  const [baseUrl, setBaseUrl] = useState(initialBaseUrl);
  const [envOllamaBase, setEnvOllamaBase] = useState<string>("");

  // Load available providers on mount
  useEffect(() => {
    const loadProviders = async () => {
      try {
        const response = await getAvailableProviders();
        const providersMap = response.providers.reduce(
          (acc: Record<string, any>, provider) => {
            acc[provider.id] = provider;
            return acc;
          },
          {},
        );
        setAvailableProviders(providersMap);
      } catch (error) {
        console.error("Failed to load providers:", error);
      }
    };
    loadProviders();
  }, []);

  // Load OLLAMA_API_BASE from keychain
  useEffect(() => {
    const loadEnv = async () => {
      try {
        const envVars = await secretStore.getEnvVars();
        let value = envVars["OLLAMA_API_BASE"] || "";
        if (value) setEnvOllamaBase(value);
      } catch (e) {
        console.error("useProviderSelection: Error loading env vars:", e);
      }
    };
    loadEnv();
  }, [provider]);


  // Extract model name without provider prefix for display
  const getDisplayModelName = (model: string) => {
    if (model.includes("/")) {
      return model.split("/").slice(1).join("/");
    }
    return model;
  };

  // Fetch model suggestions
  const fetchSuggestions = useCallback(async (input: string) => {
    setLoadingSuggestions(true);
    try {
      let suggestionsData: ModelSuggestion[] = [];
      if (provider === "ollama") {
        const effectiveBase = baseUrl || envOllamaBase;

        if (!effectiveBase) {
          setSuggestions([]);
          setSelectedSuggestionIndex(-1);
          setLoadingSuggestions(false);
          return;
        }
        try {
          const response = await getOllamaModelList(effectiveBase);
          if (response.models && response.models.length > 0) {
            const filteredModels = response.models
              .filter((model: any) => {
                const modelName = model.name || model.id;
                return modelName.toLowerCase().includes(input.toLowerCase());
              })
              .slice(0, 20);
            suggestionsData = filteredModels.map((model: any) => ({
              id: model.name || model.id,
              name: model.name || model.id,
              cost_info: undefined
            }));
          }
        } catch (error) {
          console.error("Failed to get Ollama local models:", error);
          suggestionsData = [];
        }
      } else {
        try {
          // TODO: Get base URL from keyring for OpenAI instead of process.env
          const providerSuggestions = await getModelSuggestions(provider, input, undefined);
          if (providerSuggestions.suggestions && providerSuggestions.suggestions.length > 0) {
            suggestionsData = providerSuggestions.suggestions.map((model: any) => ({
              id: model.name || model.id,
              name: model.name || model.id,
              cost_info: model.cost_info
            }));
          } else {
            const providerModelsResponse = await getLiteLLMProviderModels(provider);
            if (providerModelsResponse.models) {
              const filteredModels = providerModelsResponse.models
                .filter((modelName: string) => {
                  return modelName.toLowerCase().includes(input.toLowerCase());
                })
                .slice(0, 20);
              suggestionsData = filteredModels.map((modelName: string) => ({
                id: modelName,
                name: modelName,
                cost_info: undefined
              }));
            }
          }
        } catch (error) {
          console.error(`Failed to get ${provider} suggestions:`, error);
          suggestionsData = [];
        }
      }
      setSuggestions(suggestionsData);
      setSelectedSuggestionIndex(-1);
    } catch (error) {
      console.error("Failed to fetch suggestions:", error);
      setSuggestions([]);
    } finally {
      setLoadingSuggestions(false);
    }
  }, [provider, baseUrl, envOllamaBase]);

  // Debounced suggestion fetching
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (modelInput.trim() && showSuggestions) {
        fetchSuggestions(modelInput.trim());
      } else {
        setSuggestions([]);
      }
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [modelInput, showSuggestions, fetchSuggestions]);

  // Provider change handler
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    setModelInput("");
    setSuggestions([]);
    setSelectedSuggestionIndex(-1);
    if (onProviderChange) onProviderChange(newProvider);
  };

  // Model input change handler
  const handleModelInputChange = (value: string) => {
    setModelInput(value);
    setShowSuggestions(true);
    setSelectedSuggestionIndex(-1);
  };

  // Suggestion select handler
  const handleSuggestionSelect = (suggestion: ModelSuggestion) => {
    setModelInput(getDisplayModelName(suggestion.name));
    setShowSuggestions(false);
    const formattedModel = formatModelForLiteLLM(provider, suggestion.name);
    if (onModelChange) onModelChange(formattedModel);
  };

  // Keyboard navigation for suggestions
  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) return;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedSuggestionIndex(prev => prev < suggestions.length - 1 ? prev + 1 : 0);
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedSuggestionIndex(prev => prev > 0 ? prev - 1 : suggestions.length - 1);
        break;
      case "Enter":
        e.preventDefault();
        if (selectedSuggestionIndex >= 0) {
          handleSuggestionSelect(suggestions[selectedSuggestionIndex]);
        } else {
          setShowSuggestions(false);
          const formattedModel = formatModelForLiteLLM(provider, modelInput);
          if (onModelChange) onModelChange(formattedModel);
        }
        break;
      case "Escape":
        setShowSuggestions(false);
        setSelectedSuggestionIndex(-1);
        break;
    }
  };

  // Input blur/focus handlers
  const handleInputBlur = () => {
    setTimeout(() => {
      setShowSuggestions(false);
      setSelectedSuggestionIndex(-1);
    }, 200);
  };
  const handleInputFocus = () => {
    if (modelInput.trim()) {
      setShowSuggestions(true);
    }
  };

  // Cost info renderer (returns React fragment for use in components)
  const renderCostInfo = (costInfo: any) => {
    if (!costInfo) return "";
    const inputCost = costInfo.input_cost_per_token
      ? `Input: $${(costInfo.input_cost_per_token * 1000000).toFixed(2)}/1M`
      : "";
    const outputCost = costInfo.output_cost_per_token
      ? `Output: $${(costInfo.output_cost_per_token * 1000000).toFixed(2)}/1M`
      : "";
    if (!inputCost && !outputCost) return "";
    return `${inputCost}${inputCost && outputCost ? " | " : ""}${outputCost}`;
  };

  return {
    provider,
    setProvider,
    availableProviders,
    modelInput,
    setModelInput,
    suggestions,
    showSuggestions,
    loadingSuggestions,
    selectedSuggestionIndex,
    inputRef,
    suggestionsRef,
    baseUrl,
    setBaseUrl,
    handleProviderChange,
    handleModelInputChange,
    handleSuggestionSelect,
    handleInputKeyDown,
    handleInputBlur,
    handleInputFocus,
    renderCostInfo,
  };
}
