import { useState, useEffect } from "react";
import { getSystemConfig, updateSystemConfig } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";

export function useCustomEndpoints() {
  const [useCustomEndpoints, setUseCustomEndpoints] = useState(false);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  // Load current config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await getSystemConfig();
        setUseCustomEndpoints(config.use_custom_endpoints ?? false);
      } catch (error) {
        console.error("Failed to load system config:", error);
      }
    };
    loadConfig();
  }, []);

  const toggleCustomEndpoints = async (checked: boolean) => {
    setLoading(true);
    try {
      await updateSystemConfig({ use_custom_endpoints: checked });
      setUseCustomEndpoints(checked);
      
      toast({
        title: "Settings Updated",
        description: `Custom endpoints ${checked ? 'enabled' : 'disabled'}`,
      });
    } catch (error) {
      console.error("Failed to update custom endpoints setting:", error);
      toast({
        title: "Error",
        description: "Failed to update custom endpoints setting",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return {
    useCustomEndpoints,
    loading,
    toggleCustomEndpoints,
  };
}
