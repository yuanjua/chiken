import React, { useEffect, useState } from "react";
import { useAtom } from "jotai";
import { selectedModelAtom } from "@/store/chatAtoms";
import { chatService } from "@/lib/chat-service";
import { ProviderConfig } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

export function ConnectionStatusBadge() {
  const [selectedModel] = useAtom(selectedModelAtom);
  const [connectionStatus, setConnectionStatus] = useState<
    "idle" | "connected" | "error" | "testing"
  >("idle");

  useEffect(() => {
    testConnection();
  }, [selectedModel]);

  const testConnection = async () => {
    try {
      setConnectionStatus("testing");
      let envOllama = "";

      const providerConfig: ProviderConfig = {
        provider: (selectedModel.provider as any),
        model: selectedModel.model,
        baseUrl: selectedModel.baseUrl || envOllama,
        temperature: selectedModel.temperature,
        numCtx:
          selectedModel.provider === "ollama" ||
          selectedModel.provider === "custom"
            ? 4096
            : undefined,
      };

      const result =
        await chatService.testProviderConfiguration(providerConfig);
      setConnectionStatus(result.success ? "connected" : "error");
    } catch (error) {
      setConnectionStatus("error");
    }
  };

  const getConnectionStatusBadge = () => {
    switch (connectionStatus) {
      case "connected":
        return (
          <Badge variant="default" className="flex items-center gap-1">
            <CheckCircle className="w-3 h-3" />
            Connected
          </Badge>
        );
      case "error":
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            Disconnected
          </Badge>
        );
      case "testing":
        return (
          <Badge variant="secondary" className="flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" />
            Testing...
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            Not tested
          </Badge>
        );
    }
  };

  return getConnectionStatusBadge();
}
