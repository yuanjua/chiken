import { useState, useEffect } from 'react';

export interface ProviderCredentials {
  provider: string;
  api_key?: string;
  base_url?: string;
  updated_at?: string;
}

const PYTHON_BACKEND_URL =
  process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || "http://localhost:8009";

export function useProviderCredentials() {
  const [credentials, setCredentials] = useState<ProviderCredentials[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch all provider credentials
  const fetchCredentials = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${PYTHON_BACKEND_URL}/config/provider-keys`);
      if (!response.ok) {
        throw new Error(`Failed to fetch credentials: ${response.statusText}`);
      }
      const data = await response.json() as unknown as ProviderCredentials[];
      setCredentials(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch credentials');
    } finally {
      setLoading(false);
    }
  };

  // Get credentials for a specific provider
  const getProviderCredentials = async (provider: string): Promise<ProviderCredentials | null> => {
    try {
      const response = await fetch(`${PYTHON_BACKEND_URL}/config/provider-keys/${provider}`);
      if (response.status === 404) {
        return null;
      }
      if (!response.ok) {
        throw new Error(`Failed to fetch credentials for ${provider}: ${response.statusText}`);
      }
      return await response.json() as unknown as ProviderCredentials;
    } catch (err) {
      console.error(`Error fetching credentials for ${provider}:`, err);
      return null;
    }
  };

  // Set or update provider credentials
  const setProviderCredentials = async (
    provider: string, 
    credentials: { api_key?: string; base_url?: string }
  ): Promise<boolean> => {
    try {
      const response = await fetch(`${PYTHON_BACKEND_URL}/config/provider-keys`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          provider,
          ...credentials
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to set credentials: ${response.statusText}`);
      }

      // Refresh the credentials list
      await fetchCredentials();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set credentials');
      return false;
    }
  };

  // Delete provider credentials
  const deleteProviderCredentials = async (provider: string): Promise<boolean> => {
    try {
      const response = await fetch(`${PYTHON_BACKEND_URL}/config/provider-keys/${provider}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`Failed to delete credentials: ${response.statusText}`);
      }

      // Refresh the credentials list
      await fetchCredentials();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete credentials');
      return false;
    }
  };

  // Load credentials on mount
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
