import { invoke } from "@tauri-apps/api/core";

const PYTHON_BACKEND_URL = process.env.NEXT_PUBLIC_PYTHON_BACKEND_URL || "http://localhost:8009";

function isTauri(): boolean {
  try {
    return (
      typeof globalThis !== "undefined" &&
      (globalThis as any).__TAURI_INTERNALS__ !== undefined
    );
  } catch {
    return false;
  }
}

export async function getEnvVars(): Promise<Record<string, string>> {
  if (!isTauri()) return {};
  
  const response = await fetch(`${PYTHON_BACKEND_URL}/config/env-vars/encrypted`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new Error(`Backend error: ${response.statusText}`);
  }
  return (await response.json()) as unknown as Record<string, string>;
}

export async function setEnvVar(name: string, value: string): Promise<void> {
  if (!isTauri()) return;
  
  const response = await fetch(`${PYTHON_BACKEND_URL}/config/env-vars/encrypted`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, value }),
  });
  if (!response.ok) {
    throw new Error(`Backend error: ${response.statusText}`);
  }
}

export async function deleteEnvVar(name: string): Promise<void> {
  if (!isTauri()) return;
  
  const response = await fetch(`${PYTHON_BACKEND_URL}/config/env-vars/encrypted`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    throw new Error(`Backend error: ${response.statusText}`);
  }
}

export async function getEnvVarNames(): Promise<string[]> {
  const envVars = await getEnvVars();
  return Object.keys(envVars);
}

export { isTauri };