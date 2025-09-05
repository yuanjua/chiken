"use client";

import React, { useState } from "react";
import { useAtom } from "jotai";
import { Button } from "@/components/ui/button";
import { selectedModelAtom } from "@/store/chatAtoms";
import { updateSystemConfig } from "@/lib/api-client";
import { Loader2, Save } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import * as secretStore from "@/lib/secret-store";
import { useTranslations } from "next-intl";

export function SaveConfigButton({
  activeProviders,
  providerBaseUrls,
  providerCustomEndpoints,
}: {
  activeProviders?: string[];
  providerBaseUrls?: { [key: string]: string };
  providerCustomEndpoints?: { [key: string]: boolean };
} = {}) {
  const [selectedModel] = useAtom(selectedModelAtom);
  const { toast } = useToast();
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const t = useTranslations("Common");

  // Provider credentials are managed via Env Variables section; no per-provider writes here

  const saveProviderConfig = async () => {
    setIsSavingConfig(true);
    try {
      // Save main configuration - use model name as-is to allow custom names
      const updates: any = {
        provider: selectedModel.provider,
        model_name: selectedModel.model,
        temperature: selectedModel.temperature,
        num_ctx: selectedModel.numCtx || 4096,
        base_url: selectedModel.baseUrl,
        embed_model: selectedModel.embeddingModel,
        embed_provider: selectedModel.embeddingProvider || "ollama",
        system_prompt: selectedModel.systemPrompt,
        max_history_length: selectedModel.maxHistoryLength,
        memory_update_frequency: selectedModel.memoryUpdateFrequency,
        pdf_parser_type: selectedModel.pdfParserType || "kreuzberg",
        pdf_parser_url: selectedModel.pdfParserUrl,
        // Deprecated search config removed
        // Add chunk params and reference filtering
        chunk_size: selectedModel.chunkSize,
        chunk_overlap: selectedModel.chunkOverlap,
        enable_reference_filtering: selectedModel.enableReferenceFiltering,
      };
      await updateSystemConfig(updates);


      toast({
        title: "✅ " + t("success"),
        description: t("configSavedPersisted"),
        className: "bg-green-50 border-green-200 text-green-800",
      });
    } catch (error) {
      console.error("SaveConfigButton: Save error:", error);
      toast({
        variant: "destructive",
        title: "❌ " + t("saveError"),
        description: t("saveConfigFailed", { error: String(error) }),
      });
    } finally {
      setIsSavingConfig(false);
    }
  };

  return (
    <div className="flex justify-end">
      <Button
        onClick={saveProviderConfig}
        disabled={isSavingConfig || !selectedModel.model}
        size="lg"
      >
        {isSavingConfig ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Save className="w-4 h-4 mr-2" />
        )}
        {isSavingConfig ? t("saving") : t("saveConfiguration")}
      </Button>
    </div>
  );
}
