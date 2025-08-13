import React, { useState, useEffect, useRef, useCallback } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ModelSuggestDropdown } from "./ModelSuggestDropdown";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, RefreshCw, CheckCircle, XCircle, Search } from "lucide-react";
import { ModelConfig, getProviderFromModel, formatModelForLiteLLM } from "@/store/chatAtoms";
import { 
  getOllamaModelList, 
  getModelSuggestions, 
  getLiteLLMProviderModels,
  getLiteLLMModels,
} from "@/lib/api-client";
import * as secretStore from "@/lib/secret-store";
import { useToast } from "@/hooks/use-toast";
import { useProviderConnection } from "@/hooks/useProviderConnection";
import { isValidBaseUrl } from "@/lib/utils";
import { useTranslations } from "next-intl";

interface ProviderSpecificConfigProps {
  selectedModel: ModelConfig;
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void;
  refreshTrigger?: boolean;
}

interface ModelSuggestion {
  id: string;
  name: string;
  cost_info?: {
    input_cost_per_token?: number;
    output_cost_per_token?: number;
  };
}

export function ProviderSpecificConfig({
  selectedModel,
  updateSelectedModelConfig,
  refreshTrigger,
}: ProviderSpecificConfigProps) {
  const t = useTranslations("Config");
  const [models, setModels] = useState<any[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const { connectionState } = useProviderConnection(selectedModel, updateSelectedModelConfig);
  const [envOllamaBase, setEnvOllamaBase] = useState<string>("");
  
  // Model input state
  const [modelInput, setModelInput] = useState("");
  
  const { toast } = useToast();

  // Use the selected provider from the UI instead of detecting from model name
  const currentProvider = selectedModel.provider || "openai"; // fallback to openai

  // Initialize model input with current model value
  useEffect(() => {
    setModelInput(selectedModel.model || "");
  }, [selectedModel.model]);

  // Helper: display only the model name (after the first slash)
  const getDisplayModelName = (model: string) => {
    if (!model) return "";
    const parts = model.split("/");
    return parts.length > 1 ? parts.slice(1).join("/") : model;
  };


  // Load OLLAMA_API_BASE from keychain
  useEffect(() => {
    const load = async () => {
      try {
        const envVars = await secretStore.getEnvVars();
        let value = envVars["OLLAMA_API_BASE"] || "";
        if (value) setEnvOllamaBase(value);
      } catch (e) {
        console.error("ProviderSpecificConfig: Error loading env vars:", e);
      }
    };
    load();
  }, [refreshTrigger]);

  // Suggestion fetcher for dropdown
  const fetchSuggestions = useCallback(async (input: string) => {
    let suggestionsData: ModelSuggestion[] = [];
    if (currentProvider === "ollama") {
      const effectiveBase = selectedModel.baseUrl || envOllamaBase;
      if (!effectiveBase) return [];
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
      } catch {
        suggestionsData = [];
      }
    } else {
      try {
        // Use base URL for suggestions
        const baseUrlForSuggestions = selectedModel.provider === "ollama" ? selectedModel.baseUrl : undefined;
        
        const providerSuggestions = await getModelSuggestions(
          currentProvider, 
          input, 
          baseUrlForSuggestions
        );
        if (providerSuggestions.suggestions && providerSuggestions.suggestions.length > 0) {
          suggestionsData = providerSuggestions.suggestions.map((model: any) => ({
            id: model.name || model.id,
            name: model.name || model.id,
            cost_info: model.cost_info
          }));
        } else {
          const providerModelsResponse = await getLiteLLMProviderModels(currentProvider);
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
  }, [currentProvider, selectedModel.baseUrl, connectionState.status, envOllamaBase]);



  // Render model cost information
  const renderCostInfo = (costInfo: any) => {
    if (!costInfo) return null;
    
    return (
      <div className="text-xs text-muted-foreground mt-1">
        {costInfo.input_cost_per_token && (
          <span>Input: ${(costInfo.input_cost_per_token * 1000000).toFixed(2)}/1M | </span>
        )}
        {costInfo.output_cost_per_token && (
          <span>Output: ${(costInfo.output_cost_per_token * 1000000).toFixed(2)}/1M</span>
        )}
      </div>
    );
  };

  const fetchModels = useCallback(async () => {
    // Only fetch if connection is successful
    if (connectionState.status !== "connected") {
      return;
    }

    setLoadingModels(true);

    try {
      if (currentProvider === "ollama") {
        const effectiveBase = selectedModel.baseUrl || envOllamaBase;

        const response = await getOllamaModelList(effectiveBase);
        
        if (response.models && response.models.length >= 0) {
          setModels(response.models);
          
        } else {
          setModels([]);
          
        }
      } else {
        const response = await getLiteLLMProviderModels(currentProvider);
        
        if (response.models && response.models.length > 0) {
          setModels(response.models);
          
        } else {
          setModels([]);
          
        }
      }
    } catch (error) {
      
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  }, [currentProvider, connectionState.status]);



  // Reset models when provider changes
  useEffect(() => {
    setModels([]);
    // No suggestions to show
  }, [currentProvider]);

  // Auto-fetch models immediately when connection becomes available
  useEffect(() => {
    if (connectionState.status === "connected") {
      fetchModels();
    } else {
      setModels([]);
    }
  }, [connectionState.status, currentProvider, fetchModels]);

  // Refresh models when refreshTrigger changes (e.g., when settings dialog opens)
  useEffect(() => {
    if (refreshTrigger !== undefined && connectionState.status === "connected") {
      fetchModels();
    }
  }, [refreshTrigger, connectionState.status, currentProvider, fetchModels]);



  return (
    <>

      {/* Chat Model Input with Suggestions */}
      <div className="relative">
        <div className="flex items-center justify-between">
          <Label>{t("chatModel")}</Label>
          <Button
            onClick={fetchModels}
            disabled={loadingModels}
            variant="ghost"
            size="sm"
          >
            {loadingModels ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {t("refresh")}
          </Button>
        </div>
        <ModelSuggestDropdown
          provider={currentProvider}
          baseUrl={selectedModel.baseUrl}
          value={modelInput}
          onChange={setModelInput}
          onModelSelect={(model) => {
            let fullModelName = model;
            if (!model.startsWith(currentProvider + "/")) {
              fullModelName = `${currentProvider}/${model}`;
            }
            updateSelectedModelConfig("model", fullModelName);
            setModelInput(fullModelName);
          }}
          fetchSuggestions={fetchSuggestions}
          placeholder={t("searchModelsPlaceholder", { provider: currentProvider })}
          renderCostInfo={renderCostInfo}
        />
        <div className="mt-1 text-xs text-muted-foreground">
          {t("showingModelsFrom", { provider: currentProvider })}
        </div>
      </div>
    </>
  );
}
