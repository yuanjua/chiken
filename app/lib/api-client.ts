/**
 * API Client for Python Backend
 *
 * This file contains utilities for connecting to the Python FastAPI backend.
 * Separate from Next.js API routes which are in app/api/route.ts files
 */

// Types for API requests and responses
export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
}

export interface LLMConfig {
  provider: string;
  model_name: string;
  temperature: number;
  num_ctx: number;
  base_url?: string;
  available_models: string[];
}

export interface ModelParamsRequest {
  model_name: string;
  temperature?: number;
  num_ctx?: number;
}

export interface SessionInfo {
  session_id: string;
  agent_id: string;
  agent_type: string;
  messages: ChatMessage[];
  statistics: Record<string, any>;
  memory_context: Record<string, any>;
  configuration: Record<string, any>;
}

const PYTHON_BACKEND_URL =
  process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || "http://localhost:8009";

// ===== Model Management =====
export async function getOllamaModelList(baseUrl: string, signal?: AbortSignal): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/llm/models/ollama`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get models: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getModelSuggestions(provider: string, partialModel: string = "", baseUrl?: string): Promise<any> {
  let url = `${PYTHON_BACKEND_URL}/llm/models/suggestions/${provider}?partial_model=${encodeURIComponent(partialModel)}`;
  if (baseUrl) {
    url += `&base_url=${encodeURIComponent(baseUrl)}`;
  }
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get model suggestions: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getLiteLLMModels(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/llm/models/litellm`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get LiteLLM models: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getLiteLLMProviderModels(provider: string): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/llm/models/litellm/${provider}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get ${provider} models: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getLLMConfig(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/llm/config`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get LLM config: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getAvailableProviders(): Promise<{ providers: { id: string; name: string }[] }> {
  const url = `${PYTHON_BACKEND_URL}/llm/providers`;
  const response = await fetch(url);
  const data = await response.json();
  return data as unknown as { providers: { id: string; name: string }[] };
}

export async function setModelParams(params: ModelParamsRequest): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/llm/model/params`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error(`Failed to set model params: ${response.statusText}`);
  }

  return response.json();
}

// ===== Agent Types Management =====
export async function getAgentTypes(): Promise<string[]> {
  const url = `${PYTHON_BACKEND_URL}/agents`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch agent types: ${response.statusText}`);
  }
  const data = await response.json() as any;
  return data.agent_types;
}

// ===== Session Management =====

export async function deleteSession(sessionId: string): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/sessions/${sessionId}`;
  const response = await fetch(url, {
    method: "DELETE",
  });
  return response.json();
}

export async function sendMessage(
  sessionId: string,
  message: string,
  agentType: string = "chat",
): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/sessions/${sessionId}/message?agent_type=${agentType}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return response.json();
}

export async function streamMessage(
  sessionId: string,
  message: string,
  agentType: string = "chat",
  signal?: AbortSignal,
  context?: any,
): Promise<Response> {
  const requestBody: any = { message };
  if (context) {
    requestBody.context = context;
  }

  const url = `${PYTHON_BACKEND_URL}/sessions/${sessionId}/stream?agent_type=${agentType}`;

  return fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream", // Expect an SSE stream
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
    body: JSON.stringify(requestBody),
    signal: signal || null,
  });
}

// Helper to convert backend session list to frontend map format
export function convertBackendSessionsToMap(
  backendSessions: any[],
  existingSessions?: Record<string, any>,
): Record<string, any> {
  const convertedSessions: Record<string, any> = {};

  for (const session of backendSessions) {
    const existingSession = existingSessions?.[session.session_id];

    convertedSessions[session.session_id] = {
      id: session.session_id,
      title: session.title || existingSession?.title || "New Chat",
      preview: existingSession?.preview || "",
      createdAt: new Date(session.created_at),
      updatedAt: new Date(session.last_activity),
      messageCount: session.message_count,
    };
  }
  return convertedSessions;
}

export async function getSessionInfo(sessionId: string): Promise<SessionInfo> {
  const url = `${PYTHON_BACKEND_URL}/sessions/${sessionId}`;
  const response = await fetch(url);
  const data = await response.json();
  return data as unknown as SessionInfo;
}

// ---- Paginated session messages ----
export async function getSessionMessages(
  sessionId: string,
  before?: number,
  limit: number = 200,
): Promise<{
  messages: ChatMessage[];
  has_more: boolean;
  oldest: number | null;
}> {
  const url = new URL(`${PYTHON_BACKEND_URL}/sessions/${sessionId}/messages`);
  if (before !== undefined) {
    url.searchParams.set("before", String(before));
  }
  url.searchParams.set("limit", String(limit));
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to fetch messages: HTTP ${response.status}`);
  }
  const data = await response.json();
  return data as unknown as { messages: ChatMessage[]; has_more: boolean; oldest: number | null };
}

export async function listSessions(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/sessions`;
  const response = await fetch(url);
  return response.json();
}

export async function updateSessionTitle(
  sessionId: string,
  title: string,
): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/sessions/${sessionId}/title?title=${encodeURIComponent(title)}`;
  const response = await fetch(url, {
    method: "POST",
  });
  return response.json();
}

// ===== Health Checks =====

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const url = `${PYTHON_BACKEND_URL}/health`;
    const response = await fetch(url, {
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function getChatGraphHealth(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/chat-graph/health`;
  const response = await fetch(url);
  return response.json();
}

// ===== Zotero =====

export interface ZoteroCollection {
  key: string;
  data: {
    name: string;
    parentCollection?: string;
  };
  meta: {
    numItems: number;
  };
  version: number;
  library: any;
}

export interface ZoteroCollectionsResponse {
  collections: ZoteroCollection[];
  total_count: number;
  timestamp: string;
  message?: string;
  error?: string;
}

export async function getZoteroCollections(
  limit?: number,
): Promise<ZoteroCollectionsResponse> {
  const endpoint = limit
    ? `/zotero/collections?limit=${limit}`
    : "/zotero/collections";
  const url = `${PYTHON_BACKEND_URL}${endpoint}`;
  const response = await fetch(url);
  const data = await response.json();
  return data as unknown as ZoteroCollectionsResponse;
}

export async function getZoteroCollectionItems(
  collectionId: string,
): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/zotero/collections/${collectionId}/items`;
  const response = await fetch(url);
  return response.json();
}

export async function addZoteroItemsToKnowledgeBaseStream(
  knowledgeBaseName: string,
  zoteroKeys: string[],
  onProgress: (progress: any) => void,
) {
  const url = `${PYTHON_BACKEND_URL}/rag/zotero/bulk-add-stream`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      knowledge_base_name: knowledgeBaseName,
      zotero_keys: zoteroKeys,
    }),
  });

  if (!response.body) {
    throw new Error("Response has no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // Fix: Provide a dummy Uint8Array to reader.read() to match the expected signature
  while (true) {
    const { done, value } = await reader.read(new Uint8Array());
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process line by line from the buffer
    const lines = buffer.split("\n");
    buffer = lines.pop() || ""; // Keep the last partial line

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const json = JSON.parse(line.substring(6));
          onProgress(json);
        } catch (e) {
          console.error("Failed to parse stream data:", line, e);
        }
      }
    }
  }
}

export async function getZoteroStatus(): Promise<{
  connected: boolean;
  error?: string;
}> {
  const url = `${PYTHON_BACKEND_URL}/zotero/status`;
  const response = await fetch(url);
  const data = await response.json();
  return data as unknown as { connected: boolean; error?: string };
}

// System Status Functions
export async function getSystemStatus(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/system/status`;
  const response = await fetch(url);
  return response.json();
}

// Configuration Management Functions (Single User)
export async function getSystemConfig(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/config/`;
  const response = await fetch(url);
  return response.json();
}

export async function updateSystemConfig(updates: {
  model_name?: string;
  temperature?: number;
  num_ctx?: number;
  base_url?: string;
  provider?: string;
  openai_api_key?: string;
  anthropic_api_key?: string;
  azure_api_key?: string;
  google_api_key?: string;
  ollama_api_key?: string;
  together_api_key?: string;
  cohere_api_key?: string;
  replicate_api_key?: string;
  embed_model?: string;
  embed_provider?: string;
  system_prompt?: string;
  max_history_length?: number;
  memory_update_frequency?: number;
  pdf_parser_type?: string;
  pdf_parser_url?: string;
  search_engine?: string;
  search_endpoint?: string;
  search_api_key?: string;
  use_custom_endpoints?: boolean;
  chunk_size?: number;
  chunk_overlap?: number;
  enable_reference_filtering?: boolean;
}): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/config/`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return response.json();
}

export async function createSystemBackup(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/system/backup`;
  const response = await fetch(url, {
    method: "POST",
  });
  return response.json();
}

export async function reloadSystemConfig(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/config/reload`;
  const response = await fetch(url, {
    method: "POST",
  });
  return response.json();
}

export async function getSystemHealth(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/system/health`;
  const response = await fetch(url);
  return response.json();
}

// ===== Unified Env Variables Management =====





// Reload backend configuration and environment variables
export async function reloadBackendConfig(): Promise<void> {
  const response = await fetch(`${PYTHON_BACKEND_URL}/config/reload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Failed to reload backend config: ${response.statusText}`);
  }
}





// ===== Knowledge Base Functions =====
export async function getKnowledgeBases(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/knowledge-bases`;
  const response = await fetch(url);
  return response.json();
}

export async function createKnowledgeBase(data: {
  name: string;
  description?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  embed_model?: string;
  enable_reference_filtering?: boolean;
}): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/knowledge-bases`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: data.name.trim(),
      description: data.description || `Knowledge base: ${data.name.trim()}`,
      chunk_size: data.chunk_size || 1000,
      chunk_overlap: data.chunk_overlap || 200,
      embed_model: data.embed_model || undefined,
      ...(data.enable_reference_filtering !== undefined && { enable_reference_filtering: data.enable_reference_filtering }),
    }),
  });
  // Throw on HTTP errors so the caller can handle them properly
  if (!response.ok) {
    // Fix errorData/message property access
      let message = "Failed to create knowledge base";
      try {
        const errorData = await response.json();
        message = (errorData as any)?.message || (errorData as any)?.error || message;
      } catch {
        // ignore JSON parse errors – we'll use the default message
      }
    throw new Error(message);
  }

  return response.json();
}

export async function updateKnowledgeBase(
  kbId: string,
  data: any,
): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/knowledge_bases/${kbId}`;
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error((error as any).detail || "Failed to update knowledge base");
  }
  return response.json();
}

export async function getActiveKnowledgeBases(): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/active-knowledge-bases`;
  const response = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error((error as any).detail || "Failed to get active knowledge bases");
  }
  return response.json();
}

export async function setActiveKnowledgeBases(
  knowledgeBaseIds: string[],
): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/active-knowledge-bases`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ knowledge_base_ids: knowledgeBaseIds }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error((error as any).detail || "Failed to set active knowledge bases");
  }
  return response.json();
}

export async function deleteKnowledgeBase(kbId: string): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/knowledge-bases/${kbId}`;
  const response = await fetch(url, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error((error as any).detail || "Failed to delete knowledge base");
  }
  return response.json();
}

export async function getKnowledgeBaseDocuments(kbId: string): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/knowledge-bases/${kbId}/documents`;
  const response = await fetch(url);
  return response.json();
}

export async function queryDocuments(data: {
  query_text: string;
  knowledge_base_names: string[];
  k?: number;
}): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/documents/query`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...data,
      query_text: data.query_text.trim().replace(/\s+/g, " "),
      k: data.k || 10,
    }),
  });
  return response.json();
}

export async function addDocuments(data: {
  documents: Array<{
    content: string;
    source: string;
    metadata?: Record<string, any>;
  }>;
  knowledge_base_name: string;
}): Promise<any> {
  const response = await fetch(`${PYTHON_BACKEND_URL}/rag/documents/add`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// ===== File Upload Functions =====
export async function uploadFile(formData: FormData): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/documents/upload`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  // Check if the HTTP response is successful
  if (!response.ok) {
    let errorMessage = "Upload failed";
    try {
      const errorData = await response.json();
      errorMessage = (errorData as any)?.error || (errorData as any)?.detail || errorMessage;
    } catch {
      // If we can't parse the error response, use the status text
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  const result = await response.json();
  if ((result as any).success === false) {
    throw new Error((result as any).error || (result as any).detail || "Upload failed");
  }
  return result;
}

export async function uploadPdfToKnowledgeBase(
  formData: FormData,
): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/documents/pdf`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  // Check if the HTTP response is successful
  if (!response.ok) {
    let errorMessage = "Upload failed";
    try {
      const errorData = await response.json();
      errorMessage = (errorData as any)?.error || (errorData as any)?.detail || errorMessage;
    } catch {
      // If we can't parse the error response, use the status text
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  const result = await response.json();
  if ((result as any).success === false) {
    throw new Error((result as any).error || (result as any).detail || "Upload failed");
  }
  return result;
}

export async function extractTextFromPdf(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);

  const url = `${PYTHON_BACKEND_URL}/rag/documents/extract-text`;
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  // Check if the HTTP response is successful
  if (!response.ok) {
    let errorMessage = "Text extraction failed";
    try {
      const errorData = await response.json();
      errorMessage = (errorData as any)?.error || (errorData as any)?.detail || errorMessage;
    } catch {
      // If we can't parse the error response, use the status text
      errorMessage = response.statusText || errorMessage;
    }
    throw new Error(errorMessage);
  }

  const result = await response.json();
  if ((result as any).success === false) {
    throw new Error((result as any).error || (result as any).detail || "Text extraction failed");
  }
  return result;
}

export async function getDocumentByKey(key: string): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/documents/${key}`;
  const response = await fetch(url);
  return response.json();
}

// ===== Zotero Bulk Add Functions =====
export async function bulkAddFromZotero(data: {
  collectionId?: string;
  collectionIds?: string[];
  zotero_keys?: string[];
  knowledge_base_name?: string;
  knowledgeBaseName?: string;
}): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/zotero/bulk-add-stream`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return response;
}

// ===== Document Management =====
export async function deleteDocument(id: string): Promise<any> {
  const url = `${PYTHON_BACKEND_URL}/rag/documents/${id}`;
  const response = await fetch(url, {
    method: "DELETE",
  });
  return response.json();
}

// ===== Provider Configuration =====
// Provider configuration is now handled through unified system config endpoints

// ===== MCP Configuration Functions =====
export async function getMCPConfig(): Promise<any> {
  const response = await fetch(`${PYTHON_BACKEND_URL}/mcp/config`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function updateMCPConfig(config: {
  transport?: string;
  port?: number;
}): Promise<any> {
  const response = await fetch(`${PYTHON_BACKEND_URL}/mcp/config`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function restartMCPServer(): Promise<any> {
  const response = await fetch(`${PYTHON_BACKEND_URL}/mcp/restart`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function getMCPStatus(): Promise<any> {
  const response = await fetch(`${PYTHON_BACKEND_URL}/mcp/status`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// Test embed_provider persistence

// ============ Provider API Key Management ============

export const providerToEnvKey: Record<string, { api: string; base?: string }> = {
  openai: { api: "OPENAI_API_KEY", base: "OPENAI_BASE_URL" },
  anthropic: { api: "ANTHROPIC_API_KEY", base: "ANTHROPIC_BASE_URL" },
  azure: { api: "AZURE_API_KEY" },
  replicate: { api: "REPLICATE_API_KEY" },
  cohere: { api: "COHERE_API_KEY" },
  openrouter: { api: "OPENROUTER_API_KEY", base: "OPENROUTER_BASE_URL" },
  together: { api: "TOGETHERAI_API_KEY" },
  huggingface: { api: "HF_TOKEN" },
  ollama: { api: "", base: "OLLAMA_API_BASE" },
  hosted_vllm: { api: "HOSTED_VLLM_API_KEY", base: "HOSTED_VLLM_API_BASE" },
};

