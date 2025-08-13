import { invoke } from '@tauri-apps/api/core';
/**
 * MCP (Model Context Protocol) Utilities
 * 
 * This module provides utility functions for MCP server configuration
 * including generating configuration JSON and handling sidecar binary paths.
 */

import { TauriService } from './tauri-service';

export interface MCPServerConfig {
  type?: 'stdio' | 'streamableHttp' | 'sse';
  url?: string;
  port?: number;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
}

export interface MCPConfigJSON {
  mcpServers: {
    [key: string]: MCPServerConfig;
  };
}

/**
 * Get the sidecar binary name for stdio transport
 * For Tauri sidecar binaries, we just use the name defined in tauri.conf.json
 * Tauri handles the path resolution and target triple automatically
 * @returns The sidecar binary name
 */
export const getSidecarBinaryName = (): string => {
  // This should match the name in tauri.conf.json > bundle > externalBin
  // For our case, it would be something like "kb-server" or "api"
  return 'api'; // This is the binary name without target triple suffix
};

/**
 * Get the absolute sidecar binary path using Tauri's invoke command
 * This calls the Rust backend to securely resolve the binary path
 * @returns Promise resolving to the absolute sidecar binary path
 */
export const getSidecarBinaryPath = async (): Promise<string> => {
  try {
    const tauriService = TauriService.getInstance();
    const absolutePath = await invoke<string>('get_sidecar_path');
    
    console.log('✅ Got sidecar path from Rust backend:', absolutePath);
    return absolutePath;

  } catch (error) {
    console.error('❌ Failed to get sidecar binary path:', error);
    // Fallback for development or when Tauri APIs are not available
    return 'You are currently in python development mode, the sidecar binary path will be set in production.';
  }
};

/**
 * Generate MCP configuration JSON for the knowledge base server
 * @param config - The MCP server configuration
 * @returns The complete MCP configuration object
 */
export const generateMCPConfig = async (config: MCPServerConfig): Promise<MCPConfigJSON> => {
  let serverConfig: MCPServerConfig;

  if (config.type === 'stdio') {
    // Use the returned path to determine dev/prod
    const binaryPath = await getSidecarBinaryPath();
    const isDev = binaryPath.endsWith('.py');
    if (!isDev) {
      // In production, use absolute path to sidecar binary
      serverConfig = {
        type: 'stdio',
        command: binaryPath, // Use absolute path to the sidecar binary
        args: [
          '--mcp',
        ],
        env: {}
      };
    } else {
      // In development mode, use python directly
      serverConfig = {
        type: 'stdio',
        command: 'python',
        args: [
          binaryPath,
          '--mcp',
        ],
        env: {
          'PYTHONPATH': '.',
          'This_is_dev': 'command will be binary path in production'
        }
      };
    }
  } else if (config.type === 'streamableHttp') {
    // For HTTP/SSE transports
    serverConfig = {
      type: 'streamableHttp',
      url: "http://localhost:" + (config.port || 8000) + "/mcp",
      headers: {},
    };
  } else if (config.type === 'sse') {
    serverConfig = {
      type: 'sse',
      url: "http://localhost:" + (config.port || 8000) + "/sse",
      headers: {},
    };
  } else {
    throw new Error(`Unsupported transport type: ${config.type}`);
  }

  return {
    mcpServers: {
      ["ChiKen-knowledge-base"]: serverConfig
    }
  };
};

/**
 * Format MCP configuration as a pretty-printed JSON string
 * @param config - The MCP configuration object
 * @returns Formatted JSON string
 */
export const formatMCPConfigJSON = (config: MCPConfigJSON): string => {
  return JSON.stringify(config, null, 2);
};

/**
 * Generate example MCP configuration for different transport types
 */
export const generateExampleConfigs = async () => {
  const configs = {
    stdio: await generateMCPConfig({ type: 'stdio' }),
    http: await generateMCPConfig({ type: 'streamableHttp', port: 8000 }),
    sse: await generateMCPConfig({ type: 'sse', port: 8000 }),
  };

  return {
    stdio: formatMCPConfigJSON(configs.stdio),
    http: formatMCPConfigJSON(configs.http),
    sse: formatMCPConfigJSON(configs.sse),
  };
};