import { useState, useEffect } from "react";
import { getAvailableProviders } from "@/lib/api-client";

export function useAvailableProviders() {
  const [availableProviders, setAvailableProviders] = useState<Record<string, any>>({});
  useEffect(() => {
    const loadProviders = async () => {
      try {
        const response = await getAvailableProviders();
        const providersMap = response.providers.reduce(
          (acc: Record<string, any>, provider) => {
            acc[provider.id] = provider;
            return acc;
          },
        {});
        setAvailableProviders(providersMap);
      } catch (error) {
        console.error("Failed to load providers:", error);
      }
    };
    loadProviders();
  }, []);
  return availableProviders;
}

// Sorting function: Ollama first, then alphabetical
export function useProviderDisplay() {
  const sortProviders = (entries: [string, any][]) => {
    return entries.sort(([idA, providerA], [idB, providerB]) => {
      if (idA === "ollama") return -1;
      if (idB === "ollama") return 1;
      return providerA.name.localeCompare(providerB.name);
    });
  };
  return { sortProviders };
}
