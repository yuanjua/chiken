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
  getLiteLLMModels 
} from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { useProviderConnection } from "@/hooks/useProviderConnection";
import { isValidBaseUrl } from "@/lib/utils";

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
  const [models, setModels] = useState<any[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const { connectionState } = useProviderConnection(selectedModel, updateSelectedModelConfig);
  
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


  // Suggestion fetcher for dropdown
  const fetchSuggestions = useCallback(async (input: string) => {
    let suggestionsData: ModelSuggestion[] = [];
    if (currentProvider === "ollama") {
      if (!selectedModel.baseUrl || connectionState.status !== "connected") return [];
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
  }, [currentProvider, selectedModel.baseUrl, connectionState.status]);



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
      console.log(`Skipping model fetch - connection status: ${connectionState.status}`);
      return;
    }

    console.log(`Fetching models for provider: ${currentProvider}`);
    setLoadingModels(true);

    try {
      if (currentProvider === "ollama") {
        console.log("Fetching Ollama local models...");
        const response = await getOllamaModelList(selectedModel.baseUrl || "");
        console.log("Ollama response:", response);
        
        if (response.models && response.models.length >= 0) {
          setModels(response.models);
          console.log(`Successfully loaded ${response.models.length} Ollama models`);
        } else {
          setModels([]);
          console.error("No Ollama models found");
        }
      } else {
        console.log(`Fetching ${currentProvider} models from LiteLLM...`);
        const response = await getLiteLLMProviderModels(currentProvider);
        console.log(`${currentProvider} response:`, response);
        
        if (response.models && response.models.length > 0) {
          setModels(response.models);
          console.log(`Successfully loaded ${response.models.length} ${currentProvider} models`);
        } else {
          setModels([]);
          console.error(`No models found for ${currentProvider}`);
        }
      }
    } catch (error) {
      console.error(`Error fetching models for ${currentProvider}:`, error);
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
      console.log(`Connection established for ${currentProvider}, fetching models immediately...`);
      fetchModels();
    } else {
      setModels([]);
    }
  }, [connectionState.status, currentProvider, fetchModels]);

  // Refresh models when refreshTrigger changes (e.g., when settings dialog opens)
  useEffect(() => {
    if (refreshTrigger !== undefined && connectionState.status === "connected") {
      console.log(`RefreshTrigger changed, refreshing models for ${currentProvider}...`);
      fetchModels();
    }
  }, [refreshTrigger, connectionState.status, currentProvider, fetchModels]);



  return (
    <>

      {/* Chat Model Input with Suggestions */}
      <div className="relative">
        <div className="flex items-center justify-between">
          <Label>Chat Model</Label>
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
            Refresh
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
          disabled={selectedModel.provider === "ollama" && !selectedModel.baseUrl}
          placeholder={
            selectedModel.provider === "ollama" && !selectedModel.baseUrl
              ? "Configure Ollama base URL first"
              : `Type to search ${currentProvider} models`
          }
          renderCostInfo={renderCostInfo}
        />
        <div className="mt-1 text-xs text-muted-foreground">
          Showing models from: {currentProvider} provider. Type to filter available models.
        </div>
      </div>
    </>
  );
}
