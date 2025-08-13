import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
/**
 * Tauri Service for Sidecar Management
 *
 * This service automatically finds an available port and manages the Python sidecar
 * process when running in Tauri mode.
 */

export interface SidecarConfig {
  host: string;
  port: number;
}

export class TauriService {
  private static instance: TauriService;
  private isTauri: boolean = false;
  private currentPort: number = 8009;
  private sidecarStarted: boolean = false;

  constructor() {
    // Check if we're running in Tauri
    this.isTauri =
      typeof globalThis !== "undefined" &&
      (globalThis as any).window &&
      "__TAURI_INTERNALS__" in (globalThis as any).window;
  }

  static getInstance(): TauriService {
    if (!TauriService.instance) {
      TauriService.instance = new TauriService();
    }
    return TauriService.instance;
  }

  /**
   * Check if we're running in Tauri mode
   */
  isTauriMode(): boolean {
    return this.isTauri;
  }

  /**
   * Find an available port starting from the given port
   */
  private async findAvailablePort(startPort: number = 8009): Promise<number> {
    const maxTries = 20;
    for (let port = startPort; port < startPort + maxTries; port++) {
      try {
        const response = await fetch(`http://localhost:${port}/health`, {
          method: "GET",
          signal: AbortSignal.timeout(1000),
        });
        // If we get a response, port is in use, try next one
      } catch (error) {
        // Port is available if fetch fails
        return port;
      }
    }
    throw new Error(
      `No available ports found in range ${startPort}-${startPort + maxTries}`,
    );
  }

  /**
   * Start the sidecar and wait for it to be ready
   */
  async startSidecar(): Promise<{
    success: boolean;
    port: number;
    message: string;
  }> {
    if (!this.isTauri) {
      return {
        success: false,
        port: 8009,
        message: "Not running in Tauri mode",
      };
    }

    if (this.sidecarStarted) {
      return {
        success: true,
        port: this.currentPort,
        message: "Sidecar already started",
      };
    }

    try {
      const result = (await invoke("start_sidecar")) as string;

      // Wait for the sidecar to actually start up
      const isReady = await this.waitForSidecarReady();
      if (isReady) {
        this.sidecarStarted = true;
        return { success: true, port: this.currentPort, message: result };
      } else {
        throw new Error("Sidecar started but failed health check");
      }
    } catch (error) {
      throw new Error(`Failed to start sidecar: ${error}`);
    }
  }

  /**
   * Wait for sidecar to be ready by polling health endpoint
   */
  private async waitForSidecarReady(
    maxAttempts: number = 30,
    intervalMs: number = 1000,
  ): Promise<boolean> {
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const response = await fetch(
          `http://localhost:${this.currentPort}/health`,
          {
            method: "GET",
            signal: AbortSignal.timeout(2000),
          },
        );

        if (response.ok) {
          console.log(`Sidecar health check passed on attempt ${attempt}`);
          return true;
        }
      } catch (error) {
        // Expected while sidecar is starting up
        console.log(
          `Sidecar health check attempt ${attempt}/${maxAttempts} failed:`,
          error instanceof Error ? error.message : String(error),
        );
      }

      // Wait before next attempt
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
      }
    }

    console.error(
      `Sidecar failed to become ready after ${maxAttempts} attempts`,
    );
    return false;
  }

  /**
   * Shutdown the sidecar
   */
  async shutdownSidecar(): Promise<{ success: boolean; message: string }> {
    if (!this.isTauri) {
      return { success: false, message: "Not running in Tauri mode" };
    }

    try {
      const result = (await invoke("shutdown_sidecar")) as string;
      this.sidecarStarted = false;
      return { success: true, message: result };
    } catch (error) {
      return {
        success: false,
        message: `Failed to shutdown sidecar: ${error}`,
      };
    }
  }

  /**
   * Check if sidecar is running
   */
  async isSidecarRunning(): Promise<boolean> {
    if (!this.isTauri) {
      return false;
    }

    try {
      const response = await fetch(
        `http://localhost:${this.currentPort}/health`,
        {
          method: "GET",
          signal: AbortSignal.timeout(2000),
        },
      );
      const isRunning = response.ok;
      this.sidecarStarted = isRunning;
      return isRunning;
    } catch {
      this.sidecarStarted = false;
      return false;
    }
  }

  /**
   * Listen to sidecar stdout events
   */
  async listenToSidecarStdout(
    callback: (data: string) => void,
  ): Promise<() => void> {
    if (!this.isTauri) {
      throw new Error("Not running in Tauri mode");
    }

    try {
      const unlisten = await listen("sidecar-stdout", (event) => {
        callback(event.payload as string);
      });
      return unlisten;
    } catch (error) {
      throw new Error(`Failed to listen to sidecar stdout: ${error}`);
    }
  }

  /**
   * Listen to sidecar stderr events
   */
  async listenToSidecarStderr(
    callback: (data: string) => void,
  ): Promise<() => void> {
    if (!this.isTauri) {
      throw new Error("Not running in Tauri mode");
    }

    try {
      const unlisten = await listen("sidecar-stderr", (event) => {
        callback(event.payload as string);
      });
      return unlisten;
    } catch (error) {
      throw new Error(`Failed to listen to sidecar stderr: ${error}`);
    }
  }

  /**
   * Get the current backend URL
   */
  getBackendUrl(): string {
    if (this.isTauri) {
      return `http://localhost:${this.currentPort}`;
    }

    // Default for web mode
    return process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8009";
  }

  /**
   * Get the current port being used by the sidecar
   */
  getCurrentPort(): number {
    return this.currentPort;
  }
}

// Export singleton instance
export const tauriService = TauriService.getInstance();
