import React, { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Key, Server, CheckCircle, XCircle, RefreshCw, Loader2 } from "lucide-react";
import { ModelConfig } from "@/store/chatAtoms";
import { useProviderConnection } from "@/hooks/useProviderConnection";
import { useProviderCredentials } from "@/hooks/useProviderCredentials";
import { getProviderConfig as getProviderConfigMeta } from "@/lib/provider-config";
import { getProviderConfig, setProviderKey } from "@/lib/api-client";

interface ProviderAuthProps {
  selectedModel: ModelConfig;
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void;
  embeddingProvider?: string;
  refreshTrigger?: boolean; // Optional trigger to force refresh
}

export function ProviderAuth({
  selectedModel,
  updateSelectedModelConfig,
  embeddingProvider,
  refreshTrigger,
}: ProviderAuthProps) {
  const { connectionState, testConnection } = useProviderConnection(selectedModel, updateSelectedModelConfig);
  const { getProviderCredentials, setProviderCredentials } = useProviderCredentials();

  // Local state for provider-specific custom base URLs only
  const [providerBaseUrls, setProviderBaseUrls] = useState<{[key: string]: string}>({});
  // Local state for per-provider custom endpoint toggles
  const [providerCustomEndpoints, setProviderCustomEndpoints] = useState<{[key: string]: boolean}>({});
  // Local state for loading toggles
  const [loadingToggles, setLoadingToggles] = useState<{[key: string]: boolean}>({});

  // Load provider base URLs and custom endpoint toggles when component mounts or when providers change
  useEffect(() => {
    const loadProviderConfigs = async () => {
      const urls: {[key: string]: string} = {};
      const toggles: {[key: string]: boolean} = {};
      for (const provider of activeProviders) {
        const config = await getProviderConfig(provider);
        urls[provider] = config?.base_url || "";
        toggles[provider] = !!config?.use_custom_endpoint;
      }
      setProviderBaseUrls(urls);
      setProviderCustomEndpoints(toggles);
    };
    loadProviderConfigs();
  }, [selectedModel.provider, embeddingProvider, refreshTrigger]);

  // Remove debounced save effect. Only update local state and selectedModel atom.

  // Get unique providers from chat and embedding models
  const chatProvider = selectedModel.provider || "ollama";
  const embedProvider = embeddingProvider || selectedModel.embeddingProvider || "ollama";
  const activeProviders = Array.from(new Set([chatProvider, embedProvider]));

  // Toggle handler for per-provider custom endpoint
  const toggleCustomEndpoint = async (provider: string, checked: boolean) => {
    setLoadingToggles(prev => ({ ...prev, [provider]: true }));
    setProviderCustomEndpoints(prev => ({ ...prev, [provider]: checked }));
    try {
      await setProviderKey(provider, selectedModel.apiKey || '', providerBaseUrls[provider], checked);
    } finally {
      setLoadingToggles(prev => ({ ...prev, [provider]: false }));
    }
  };

  // Handle manual connection test
  const handleTestConnection = async () => {
    const chatProvider = selectedModel.provider || "openai";
    await testConnection(chatProvider, selectedModel.baseUrl, selectedModel.apiKey);
  };

  const getConnectionBadge = () => {
    if (connectionState.status === "connected") {
      return (
        <Badge variant="default" className="ml-2 bg-green-500 dark:bg-green-700">
          <CheckCircle className="w-3 h-3 mr-1" />
          Connected {connectionState.modelCount > 0 && `(${connectionState.modelCount} models)`}
        </Badge>
      );
    }
    if (connectionState.status === "error") {
      return (
        <Badge variant="destructive" className="ml-2">
          <XCircle className="w-3 h-3 mr-1" />
          Error
        </Badge>
      );
    }
    if (connectionState.status === "testing") {
      return (
        <Badge variant="secondary" className="ml-2">
          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          Testing
        </Badge>
      );
    }
    if (connectionState.status === "pending") {
      return (
        <Badge variant="outline" className="ml-2">
          <RefreshCw className="w-3 h-3 mr-1" />
          Validating...
        </Badge>
      );
    }
    return null;
  };

  const renderProviderAuth = (provider: string) => {
    // Use getProviderConfigMeta for static metadata
    const staticConfig = getProviderConfigMeta(provider);
    const apiConfig = {
      api_key: providerCustomEndpoints[provider] ? selectedModel.apiKey : undefined,
      base_url: providerBaseUrls[provider],
      use_custom_endpoint: providerCustomEndpoints[provider] || false,
    };
    return (
      <div key={provider} className="space-y-3 p-3 border rounded-lg">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4" />
            <Label className="font-medium capitalize">{provider} Authentication</Label>
          </div>
          {(provider === "ollama") && getConnectionBadge()}
        </div>

        {/* Base URL field */}
        {staticConfig.needsBaseUrl && (
          <div>
            <div className="flex items-center justify-between">
              <Label htmlFor={`${provider}-baseUrl`}>Base URL</Label>
              {provider === "ollama" && (
                <Button
                  onClick={handleTestConnection}
                  disabled={!selectedModel.baseUrl || connectionState.status === "testing" || connectionState.status === "pending"}
                  variant="ghost"
                  size="sm"
                >
                  {connectionState.status === "testing" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Test
                </Button>
              )}
            </div>
            <Input
              id={`${provider}-baseUrl`}
              value={selectedModel.baseUrl || ""}
              onChange={(e) => updateSelectedModelConfig("baseUrl", e.target.value)}
              placeholder={staticConfig.defaultBaseUrl}
              className="font-mono text-sm"
            />
          </div>
        )}

        {/* API Key field */}
        {staticConfig.needsApiKey && (
          <div>
            <div className="flex items-center justify-between">
              <Label htmlFor={`${provider}-apiKey`}>API Key</Label>
              <div className="flex items-center gap-2">
                <Label className="text-sm text-muted-foreground cursor-default">Custom Endpoints</Label>
                <Switch
                  id={`${provider}-custom-endpoints`}
                  checked={providerCustomEndpoints[provider] || false}
                  onCheckedChange={(checked) => toggleCustomEndpoint(provider, checked)}
                  disabled={loadingToggles[provider] || false}
                  className="data-[state=checked]:bg-blue-300 data-[state=unchecked]:bg-gray-300 dark:data-[state=checked]:bg-blue-500 dark:data-[state=unchecked]:bg-gray-600 [&>span]:bg-white [&>span]:shadow-md"
                />
              </div>
            </div>
            <Input
              id={`${provider}-apiKey`}
              type="password"
              value={selectedModel.apiKey || ""}
              onChange={(e) => updateSelectedModelConfig("apiKey", e.target.value)}
              placeholder={staticConfig.placeholder}
              className="font-mono text-sm"
            />
          </div>
        )}

        {/* Custom Base URL field - shown when toggle is enabled and provider needs API key */}
        {staticConfig.needsApiKey && providerCustomEndpoints[provider] && (
          <div>
            <Label htmlFor={`${provider}-customBaseUrl`}>Custom Base URL</Label>
            <Input
              id={`${provider}-customBaseUrl`}
              value={providerBaseUrls[provider] || ''}
              onChange={(e) => {
                setProviderBaseUrls(prev => ({
                  ...prev,
                  [provider]: e.target.value
                }));
              }}
              placeholder={staticConfig.customBaseUrlDefault}
              className="font-mono text-sm"
            />
          </div>
        )}

        {/* Error display */}
        {connectionState.error && provider === "ollama" && (
          <p className="text-sm text-red-600">{connectionState.error}</p>
        )}
      </div>
    );
  };

  // Only show auth section if there are providers that need authentication
  const providersNeedingAuth = activeProviders.filter(provider => {
    const staticConfig = getProviderConfigMeta(provider);
    return staticConfig.needsBaseUrl || staticConfig.needsApiKey;
  });

  if (providersNeedingAuth.length === 0) {
    return null;
  }

  // Remove canSave and handleSave logic. All saving is handled by SettingsDialog's SaveConfigButton.

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Server className="w-4 h-4" />
        <Label className="text-sm font-medium">Provider Authentication</Label>
      </div>

      <div className="space-y-3">
        {providersNeedingAuth.map(provider => renderProviderAuth(provider))}
      </div>
      {/* No Save button here. All changes are staged in selectedModel and saved via SettingsDialog's SaveConfigButton. */}
    </div>
  );
}