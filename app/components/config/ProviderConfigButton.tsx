"use client";

import React, { useState, useEffect } from "react";
import { useAtom } from "jotai";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Settings } from "lucide-react";
import { selectedModelAtom, ModelConfig, formatModelForLiteLLM, getProviderFromModel } from "@/store/chatAtoms";
import { ProviderAndModelSelect } from "./ProviderAndModelSelect";
import { ProviderSpecificConfig } from "./ProviderSpecificConfig";
import { RAGConfig } from "./RAGConfig";
import {
  getAvailableProviders,
} from "@/lib/api-client";

interface ProviderConfigButtonProps {
  simpleContent?: boolean;
  refreshTrigger?: boolean;
}

export function ProviderConfigButton({
  simpleContent = true,
  refreshTrigger,
}: ProviderConfigButtonProps) {
  const [selectedModel, setSelectedModel] = useAtom(selectedModelAtom);

  // UI state
  const [availableProviders, setAvailableProviders] = useState<Record<string, any>>({});

  const updateSelectedModelConfig = (field: keyof ModelConfig, value: any) => {
    setSelectedModel((prev) => ({
      ...prev,
      [field]: value,
    }));
  };


  // Load available providers when component mounts or refreshTrigger changes
  const loadAvailableProviders = async () => {
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
      console.error("ProviderConfigButton: Failed to load providers:", error);
    }
  };

  // Run on mount and when refreshTrigger changes
  useEffect(() => {
    loadAvailableProviders();
  }, [refreshTrigger]);

  const configContent = (
    <>
      <ProviderAndModelSelect
        selectedModel={selectedModel}
        updateSelectedModelConfig={updateSelectedModelConfig}
      />

      <ProviderSpecificConfig
        selectedModel={selectedModel}
        updateSelectedModelConfig={updateSelectedModelConfig}
        refreshTrigger={refreshTrigger}
      />

      <RAGConfig
        selectedModel={selectedModel}
        updateSelectedModelConfig={updateSelectedModelConfig}
        onEmbeddingProviderChange={(provider) => updateSelectedModelConfig('embeddingProvider', provider)}
        refreshTrigger={refreshTrigger}
      />

      {/* ProviderAuth removed: provider authentication handled via env table and model discovery */}
    </>
  );

  // If simpleContent is true, return just the content without card wrapper
  if (simpleContent) {
    return <div className="space-y-4">{configContent}</div>;
  }

  // Default card layout for standalone usage
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Settings className="w-4 h-4" />
          Model Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {configContent}
      </CardContent>
    </Card>
  );
}
