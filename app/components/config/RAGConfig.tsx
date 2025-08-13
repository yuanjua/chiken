import React from "react";
import { Label } from "@/components/ui/label";
import { ProviderSelect } from "@/components/config/ProviderSelect";
import { ModelSuggestDropdown } from "./ModelSuggestDropdown";
import { ModelConfig } from "@/store/chatAtoms";
import { useProviderSelection } from "@/hooks/useProviderSelection";
import { useTranslations } from "next-intl";

// RAGConfig Component - Optimized for LiteLLM Compatibility
// - Properly handles embed_provider persistence separately from chat model provider
// - Uses formatModelForLiteLLM for consistent model name formatting
// - Supports all LiteLLM providers with proper model suggestions

interface RAGConfigProps {
  selectedModel: ModelConfig;
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void;
  availableModels?: any[];
  onEmbeddingProviderChange?: (provider: string) => void;
  refreshTrigger?: boolean;
}

export function RAGConfig(props: RAGConfigProps) {
  const { selectedModel, updateSelectedModelConfig, availableModels = [], onEmbeddingProviderChange, refreshTrigger } = props;
  const t = useTranslations("RAG");
  // Use the hook for provider/model selection
  const {
    provider,
    handleProviderChange,
    renderCostInfo,
  } = useProviderSelection({
    initialProvider: selectedModel.embeddingProvider || "ollama",
    initialModel: selectedModel.embeddingModel || "",
    initialBaseUrl: selectedModel.baseUrl || "",
    onProviderChange: (newProvider: string) => {
      updateSelectedModelConfig("embeddingProvider", newProvider);
      updateSelectedModelConfig("embeddingModel", "");
      onEmbeddingProviderChange?.(newProvider);
    },
    onModelChange: (model: string) => {
      updateSelectedModelConfig("embeddingModel", model);
    },
    embedding: true,
  });

  // Model input state
  const [modelInput, setModelInput] = React.useState(selectedModel.embeddingModel || "");

  React.useEffect(() => {
    setModelInput(selectedModel.embeddingModel || "");
  }, [selectedModel.embeddingModel]);

  // Refresh embedding models when refreshTrigger changes (e.g., when settings dialog opens)
  React.useEffect(() => {
    if (refreshTrigger !== undefined) {
      // Force refresh by updating the model input which will trigger suggestion fetch
      setModelInput(selectedModel.embeddingModel || "");
    }
  }, [refreshTrigger, provider, selectedModel.embeddingModel]);

  // Suggestion fetcher for dropdown
  const fetchSuggestions = React.useCallback(async (input: string) => {
    // This logic should match ProviderSpecificConfig, but for embedding models
    // For now, just call the same API as chat models, but you can adapt as needed
    // If you have a separate API for embedding models, use it here
    // For demonstration, we use provider/model logic
    // You may want to add embedding-specific logic if needed
    try {
      // Try to fetch suggestions from the same endpoint as chat models
      // (Replace with embedding-specific endpoint if available)
      const { getModelSuggestions, getLiteLLMProviderModels, getOllamaModelList } = await import("@/lib/api-client");
      let suggestionsData: any[] = [];
      if (provider === "ollama") {
        if (!selectedModel.baseUrl) return [];
        try {
          const response = await getOllamaModelList(selectedModel.baseUrl || "");
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
        } catch {
          suggestionsData = [];
        }
      } else {
        try {
          const baseUrlForSuggestions = provider === "ollama" ? selectedModel.baseUrl : undefined;
          const providerSuggestions = await getModelSuggestions(provider, input, baseUrlForSuggestions);
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
        } catch {
          suggestionsData = [];
        }
      }
      return suggestionsData;
    } catch {
      return [];
    }
  }, [provider, selectedModel.baseUrl]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Left side - Configuration */}
        <div className="lg:col-span-2 space-y-3">
          {/* Embedding Provider Selection */}
          <div>
            <Label htmlFor="embeddingProvider">{t("embeddingProvider")}</Label>
            <ProviderSelect
              value={provider}
              onChange={handleProviderChange}
              label={undefined}
            />
          </div>
          {/* Embedding Model Input with Suggestions */}
          <div className="relative">
            <Label htmlFor="embeddingModel">{t("embeddingModel")}</Label>
            <ModelSuggestDropdown
              provider={provider}
              baseUrl={selectedModel.baseUrl}
              value={modelInput}
              onChange={setModelInput}
              onModelSelect={(model) => {
                let fullModelName = model;
                if (!model.startsWith(provider + "/")) {
                  fullModelName = `${provider}/${model}`;
                }
                updateSelectedModelConfig("embeddingModel", fullModelName);
                setModelInput(fullModelName);
              }}
              fetchSuggestions={fetchSuggestions}
              placeholder={t("searchModelsPlaceholder", { provider })}
              renderCostInfo={renderCostInfo}
            />
          </div>
        </div>
        {/* Right side - Description */}
        <div className="lg:col-span-2">
          <div className="text-sm p-3 bg-muted rounded-lg h-full flex flex-col justify-center">
            <strong className="text-foreground">{t("embeddingSetupTitle")}</strong>
            <p className="text-muted-foreground mt-1">{t("embeddingSetupDesc")}</p>
            <div className="mt-2 text-xs text-muted-foreground">
              <p className="">{t("examplesTitle")}</p>
              <p>
                <strong>Ollama:</strong> nomic-embed-text, all-MiniLM-L6-v2
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}