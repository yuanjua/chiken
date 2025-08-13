import React from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  TestTube,
  Settings,
  Loader2,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { ProviderTestResult, SaveConfigResult } from "@/lib/chat-service";
import { useTranslations } from "next-intl";

interface TestAndSaveConfigButtonsProps {
  isTestingProvider: boolean;
  isSavingConfig: boolean;
  testProviderConfig: () => Promise<void>;
  saveProviderConfig: () => Promise<void>;
  providerTestResult: ProviderTestResult | null;
  saveResult: SaveConfigResult | null;
  error: string | null;
}

export function TestAndSaveConfigButtons({
  isTestingProvider,
  isSavingConfig,
  testProviderConfig,
  saveProviderConfig,
  providerTestResult,
  saveResult,
  error,
}: TestAndSaveConfigButtonsProps) {
  const t = useTranslations("ConfigButtons");
  const status = React.useMemo(() => {
    if (isSavingConfig) return { status: "loading", text: t("saving") };
    if (isTestingProvider) return { status: "loading", text: t("testing") };
    if (saveResult?.success) return { status: "success", text: t("saved") };
    if (providerTestResult?.success) return { status: "success", text: t("testSuccessful") };
    if (error) return { status: "error", text: t("error") };
    return { status: "idle", text: t("idle") };
  }, [
    isSavingConfig,
    isTestingProvider,
    saveResult,
    providerTestResult,
    error,
    t,
  ]);

  const StatusIcon = ({ className }: { className?: string }) => {
    switch (status.status) {
      case "success":
        return <CheckCircle className={className} />;
      case "error":
        return <XCircle className={className} />;
      case "loading":
        return <Loader2 className={className} />;
      default:
        return null;
    }
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Button
        onClick={testProviderConfig}
        disabled={isTestingProvider || isSavingConfig}
        variant="outline"
        size="sm"
      >
        {isTestingProvider ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <TestTube className="w-4 h-4 mr-2" />
        )}
        {t("test")}
      </Button>

      <Button
        onClick={saveProviderConfig}
        disabled={
          isSavingConfig || isTestingProvider || !providerTestResult?.success
        }
        variant="default"
        size="sm"
      >
        {isSavingConfig ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Settings className="w-4 h-4 mr-2" />
        )}
        {t("save")}
      </Button>

      <Badge
        variant={
          status.status === "success"
            ? "default"
            : status.status === "error"
              ? "destructive"
              : "secondary"
        }
        className="flex items-center gap-1"
      >
        <StatusIcon
          className={`w-3 h-3 ${status.status === "loading" ? "animate-spin" : ""}`}
        />
        {status.text}
      </Badge>
    </div>
  );
}
