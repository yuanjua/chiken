import React from "react";
import { Label } from "@/components/ui/label";
import { ProviderSelect } from "@/components/config/ProviderSelect";
import { useProviderDisplay } from "@/hooks/useProviderDisplay";
import { ModelConfig, getProviderFromModel, formatModelForLiteLLM } from "@/store/chatAtoms";
import { useProviderSelection } from "@/hooks/useProviderSelection";

interface ProviderAndModelSelectProps {
  selectedModel: ModelConfig;
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void;
}

export function ProviderAndModelSelect(props: ProviderAndModelSelectProps) {
  const { selectedModel, updateSelectedModelConfig } = props;
  const [provider, setProvider] = React.useState(selectedModel.provider);
  React.useEffect(() => {
    setProvider(selectedModel.provider);
  }, [selectedModel.provider]);

  const handleProviderChange = (newProvider: string) => {
    const typedProvider = newProvider as ModelConfig["provider"];
    setProvider(typedProvider);
    updateSelectedModelConfig("provider", typedProvider);
    // Update model name to default for the new provider
    const defaultModel = "";
    updateSelectedModelConfig("model", defaultModel);
  };

  return (
    <div>
      <Label htmlFor="provider">Provider</Label>
      <ProviderSelect
        value={provider}
        onChange={handleProviderChange}
        label={undefined}
      />
    </div>
  );
}
