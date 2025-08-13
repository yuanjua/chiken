import { invoke } from "@tauri-apps/api/core";

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
  try {
    const result = (await invoke("get_secret")) as string | null;
    if (!result) return {};
    return JSON.parse(result);
  } catch {
    return {};
  }
}

export async function setEnvVar(name: string, value: string): Promise<void> {
  if (!isTauri()) return;
  const envVars = await getEnvVars();
  envVars[name] = value;
  await invoke("set_secret", { value: JSON.stringify(envVars) });
}

export async function deleteEnvVar(name: string): Promise<void> {
  if (!isTauri()) return;
  const envVars = await getEnvVars();
  delete envVars[name];
  await invoke("set_secret", { value: JSON.stringify(envVars) });
}

export async function getEnvVarNames(): Promise<string[]> {
  const envVars = await getEnvVars();
  return Object.keys(envVars);
}

