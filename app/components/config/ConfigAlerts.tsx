import React from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, XCircle } from "lucide-react";
import { SaveConfigResult } from "@/lib/chat-service";
import { useTranslations } from "next-intl";

interface ConfigAlertsProps {
  saveResult: SaveConfigResult | null;
  error: string | null;
}

export function ConfigAlerts({ saveResult, error }: ConfigAlertsProps) {
  const t = useTranslations("Common");
  return (
    <>
      {/* Save Success */}
      {saveResult?.success && (
        <Alert>
          <CheckCircle className="w-4 h-4" />
          <AlertDescription>
            <strong>{t("configSaved")}</strong> {saveResult.message}
          </AlertDescription>
        </Alert>
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <XCircle className="w-4 h-4" />
          <AlertDescription>{t("configError", { error })}</AlertDescription>
        </Alert>
      )}
    </>
  );
}
