import { useState, useEffect } from 'react';
import * as secretStore from '@/lib/secret-store';

export interface ProviderCredentials {
  provider: string;
  api_key?: string;
  base_url?: string;
  updated_at?: string;
}

export function useProviderCredentials() {
  const [credentials, setCredentials] = useState<ProviderCredentials[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const providerToEnvKey: Record<string, { api: string; base?: string }> = {
    openai: { api: 'OPENAI_API_KEY', base: 'OPENAI_BASE_URL' },
    anthropic: { api: 'ANTHROPIC_API_KEY', base: 'ANTHROPIC_BASE_URL' },
    azure: { api: 'AZURE_API_KEY' },
    replicate: { api: 'REPLICATE_API_KEY' },
    cohere: { api: 'COHERE_API_KEY' },
    openrouter: { api: 'OPENROUTER_API_KEY', base: 'OPENROUTER_BASE_URL' },
    together: { api: 'TOGETHERAI_API_KEY' },
    huggingface: { api: 'HF_TOKEN' },
    ollama: { api: '', base: 'OLLAMA_API_BASE' },
  };

  const fetchCredentials = async () => {
    setLoading(true);
    setError(null);
    try {
      const envVars = await secretStore.getEnvVars();
      const result: ProviderCredentials[] = await Promise.all(
        Object.entries(providerToEnvKey).map(async ([provider, keys]) => {
          const apiPresent = keys.api ? !!envVars[keys.api] : false;
          const baseUrlPresent = keys.base ? !!envVars[keys.base] : false;
          return {
            provider,
            api_key: apiPresent ? '*****' : undefined,
            base_url: baseUrlPresent ? '*****' : undefined,
          };
        })
      );
      setCredentials(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch credentials');
    } finally {
      setLoading(false);
    }
  };

  const getProviderCredentials = async (provider: string): Promise<ProviderCredentials | null> => {
    try {
      const keys = providerToEnvKey[provider];
      if (!keys) return null;
      const envVars = await secretStore.getEnvVars();
      return {
        provider,
        api_key: keys.api && envVars[keys.api] ? '*****' : undefined,
        base_url: keys.base && envVars[keys.base] ? '*****' : undefined,
      };
    } catch (err) {
      console.error(`Error fetching credentials for ${provider}:`, err);
      return null;
    }
  };

  const setProviderCredentials = async (
    provider: string,
    creds: { api_key?: string; base_url?: string }
  ): Promise<boolean> => {
    try {
      const keys = providerToEnvKey[provider];
      if (!keys) return false;
      // Store in keychain via Tauri
      if (keys.api && creds.api_key !== undefined) {
        await secretStore.setEnvVar(keys.api, creds.api_key || '');
      }
      // Store base URL in keychain as well
      if (keys.base && creds.base_url !== undefined) {
        await secretStore.setEnvVar(keys.base, creds.base_url || '');
      }
      await fetchCredentials();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set credentials');
      return false;
    }
  };

  const deleteProviderCredentials = async (provider: string): Promise<boolean> => {
    try {
      const keys = providerToEnvKey[provider];
      if (!keys) return false;
      // Remove from keychain
      if (keys.api) await secretStore.deleteEnvVar(keys.api);
      if (keys.base) await secretStore.deleteEnvVar(keys.base);
      await fetchCredentials();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete credentials');
      return false;
    }
  };

  useEffect(() => {
    fetchCredentials();
  }, []);

  return {
    credentials,
    loading,
    error,
    fetchCredentials,
    getProviderCredentials,
    setProviderCredentials,
    deleteProviderCredentials,
  };
}
