import React from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, XCircle } from "lucide-react";
import { SaveConfigResult } from "@/lib/chat-service";

interface ConfigAlertsProps {
  saveResult: SaveConfigResult | null;
  error: string | null;
}

export function ConfigAlerts({ saveResult, error }: ConfigAlertsProps) {
  return (
    <>
      {/* Save Success */}
      {saveResult?.success && (
        <Alert>
          <CheckCircle className="w-4 h-4" />
          <AlertDescription>
            <strong>Configuration saved!</strong> {saveResult.message}
          </AlertDescription>
        </Alert>
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <XCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </>
  );
}
