"use client";

import { useAtom } from "jotai";
import { useEffect, useState } from "react";
import { getSystemConfig } from "@/lib/api-client";
import { selectedModelAtom } from "@/store/chatAtoms";
import { themeAtom } from "@/store/uiAtoms";
import { ProviderConfigButton } from "@/components/config/ProviderConfigButton";
import { SaveConfigButton } from "@/components/config/SaveConfigButton";
import { PdfParserConfig } from "@/components/config/PdfParserConfig";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FaGithub } from "react-icons/fa";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Settings, Zap, Palette, Brain } from "lucide-react";
import { EnvVariablesConfig } from "@/components/config/EnvVariablesConfig";
import { useTranslations } from "next-intl";
import { setStoredTheme } from "@/lib/tauri-store";

interface SettingsDialogProps {
  children?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function SettingsDialog({
  children,
  open,
  onOpenChange,
}: SettingsDialogProps) {
  const [selectedModel, setSelectedModel] = useAtom(selectedModelAtom);
  const [theme, setTheme] = useAtom(themeAtom);
  const [refreshTrigger, setRefreshTrigger] = useState(false);
  const t = useTranslations("Settings");

  // Fetch config on dialog open and set initial state
  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const config = await getSystemConfig();
        if (config) {
          // Merge backend config with existing selectedModel to preserve any local-only fields
          setSelectedModel(prev => ({
            ...prev,
            provider: config.provider || prev.provider,
            model: config.model_name || prev.model,
            temperature: config.temperature ?? prev.temperature,
            numCtx: config.num_ctx ?? prev.numCtx,
            systemPrompt: config.system_prompt ?? prev.systemPrompt,
            pdfParserType: config.pdf_parser_type ?? prev.pdfParserType,
            pdfParserUrl: config.pdf_parser_url ?? prev.pdfParserUrl,
            baseUrl: config.base_url ?? prev.baseUrl,
            embeddingModel: config.embed_model ?? prev.embeddingModel,
            embeddingProvider: config.embed_provider ?? prev.embeddingProvider,
            maxHistoryLength: config.max_history_length ?? prev.maxHistoryLength,
            memoryUpdateFrequency: config.memory_update_frequency ?? prev.memoryUpdateFrequency,
          }));
        }
        // Trigger refresh for ProviderAuth to reload provider configs
        setRefreshTrigger(prev => !prev);
      } catch (e) {
        // Ignore errors for now
      }
    })();
  }, [open, setSelectedModel]);

  const handleTemperatureChange = (value: number[]) => {
    setSelectedModel((prev) => ({ ...prev, temperature: value[0] }));
  };

  const handleContextSizeChange = (value: number[]) => {
    setSelectedModel((prev) => ({ ...prev, numCtx: value[0] }));
  };

  // Helper function to format context size display
  const formatContextSize = (size: number) => {
    if (size >= 1024) {
      return `${(size / 1024).toFixed(0)}k`;
    }
    return size.toString();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {children && <DialogTrigger asChild>{children}</DialogTrigger>}
      <DialogContent className="sm:max-w-[700px] lg:max-w-[800px] max-h-[90vh] flex flex-col">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            {t("title")}
          </DialogTitle>
          <DialogDescription>
            {t("description")}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea
          className="flex-1 pr-4 -mr-4 overflow-y-auto"
          style={{ minHeight: 0 }}
        >
          <div className="space-y-6 pb-6 px-1">
            {/* Provider Configuration */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4" />
                <Label className="text-sm font-medium">{t("providerAndModel")}</Label>
              </div>
              <ProviderConfigButton simpleContent={true} refreshTrigger={refreshTrigger} />
            </div>

            <Separator />

            {/* Model Parameters */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                <Label className="text-sm font-medium">{t("modelParameters")}</Label>
              </div>

              {/* Temperature */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">{t("temperature")}</Label>
                  <span className="text-sm text-muted-foreground">
                    {selectedModel.temperature}
                  </span>
                </div>
                <Slider
                  value={[selectedModel.temperature]}
                  onValueChange={handleTemperatureChange}
                  max={2}
                  min={0}
                  step={0.1}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground">{t("temperatureHelp")}</p>
              </div>

              {/* Context Size */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm">{t("contextSize")}</Label>
                  <span className="text-sm text-muted-foreground">
                    {formatContextSize(selectedModel.numCtx || 4096)}
                  </span>
                </div>
                <Slider
                  value={[selectedModel.numCtx || 4096]}
                  onValueChange={handleContextSizeChange}
                  max={131072} // 128k
                  min={512}
                  step={512}
                  className="w-full"
                />
                <p className="text-xs text-muted-foreground">{t("contextSizeHelp")}</p>
              </div>
            </div>

            <Separator />

            {/* Environment Variables */}
            <EnvVariablesConfig />

            <Separator />

            {/* Theme Settings */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4" />
                <Label className="text-sm font-medium">{t("appearance")}</Label>
              </div>
              <div className="flex items-center justify-between">
                <Label htmlFor="theme-select" className="text-sm">{t("theme")}</Label>
                <Select
                  value={theme}
                  onValueChange={async (value: any) => {
                    setTheme(value);
                    await setStoredTheme(value);
                  }}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">{t("themeLight")}</SelectItem>
                    <SelectItem value="dark">{t("themeDark")}</SelectItem>
                    <SelectItem value="system">{t("themeSystem")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Separator />

            {/* PDF Parser Configuration */}
            <PdfParserConfig
              selectedModel={selectedModel}
              updateSelectedModelConfig={(field, value) =>
                setSelectedModel((prev) => ({ ...prev, [field]: value }))
              }
            />
          </div>
        </ScrollArea>

        {/* Save Button and link at the very bottom, side by side */}
        <div className="flex items-center justify-between pt-4 border-t gap-4">
          <a
            href="https://github.com/yuanjua/chiken"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-500 hover:text-blue-600 flex items-center"
          >
            <span className="inline-block mr-1">
              <FaGithub />
            </span>
            <span className="text-sm">{t("reportBug")}</span>
          </a>
          <SaveConfigButton />
        </div>
      </DialogContent>
    </Dialog>
  );
}
