"use client";

import { useEffect, useState } from "react";
import { useAtom } from "jotai";
import { listen } from "@tauri-apps/api/event";
import { checkBackendHealth, listSessions } from "@/lib/api-client";
import { isBackendLoadingAtom, isBackendReadyAtom } from "@/store/uiAtoms";

interface StartupScreenProps {
  onReady: () => void;
}

export function StartupScreen({ onReady }: StartupScreenProps) {
  const [status, setStatus] = useState("Checking backend connection...");
  const [sidecarErrors, setSidecarErrors] = useState<string[]>([]);
  const [, setIsBackendLoading] = useAtom(isBackendLoadingAtom);
  const [, setIsBackendReady] = useAtom(isBackendReadyAtom);

  useEffect(() => {
    // Set backend loading to true and ready to false when component mounts
    console.log(
      "🚀 StartupScreen: Initializing backend state (loading=true, ready=false)",
    );
    setIsBackendLoading(true);
    setIsBackendReady(false);

    // Clean up when component unmounts
    return () => {
      setIsBackendLoading(false);
    };
  }, [setIsBackendLoading, setIsBackendReady]);

  useEffect(() => {
    // Listen for sidecar error events from Rust backend
    const setupSidecarListeners = async () => {
      try {
        const unlistenResolveError = await listen(
          "sidecar-resolve-error",
          (event) => {
            console.error("🔴 Sidecar Resolve Error:", event.payload);
            setSidecarErrors((prev) => [
              ...prev,
              `Resolve Error: ${event.payload}`,
            ]);
          },
        );

        const unlistenSpawnError = await listen(
          "sidecar-spawn-error",
          (event) => {
            console.error("🔴 Sidecar Spawn Error:", event.payload);
            setSidecarErrors((prev) => [
              ...prev,
              `Spawn Error: ${event.payload}`,
            ]);
          },
        );

        const unlistenStdout = await listen("sidecar-stdout", (event) => {
          console.log("📤 Sidecar Stdout:", event.payload);
        });

        const unlistenStderr = await listen("sidecar-stderr", (event) => {
          console.error("📥 Sidecar Stderr:", event.payload);
        });

        // Return cleanup function
        return () => {
          unlistenResolveError();
          unlistenSpawnError();
          unlistenStdout();
          unlistenStderr();
        };
      } catch (error) {
        console.warn("Failed to setup sidecar event listeners:", error);
      }
    };

    setupSidecarListeners();
  }, []);

  useEffect(() => {
    let attempts = 0;
    let timeoutId: NodeJS.Timeout;

    const checkHealth = async () => {
      attempts++;
      console.log(`🔍 Health check attempt ${attempts} (infinite retries)`);
      try {
        const isHealthy = await checkBackendHealth();
        if (isHealthy) {
          // Added session check to ensure backend is fully ready
          await listSessions();
          console.log("✅ Backend health and session checks succeeded");
          setStatus("Connected!");
          setIsBackendLoading(false);
          setIsBackendReady(true);
          setTimeout(() => onReady(), 500); // Brief delay for "Connected!"
          return;
        }
      } catch (error) {
        console.log(`❌ Backend check attempt ${attempts} failed:`, error);
      }

      // Keep retrying infinitely every second
      timeoutId = setTimeout(checkHealth, 1000);
    };

    checkHealth();

    return () => {
      clearTimeout(timeoutId);
    };
  }, [onReady, setIsBackendLoading, setIsBackendReady]);

  return (
    <div className="h-screen w-screen bg-background flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
        <p className="text-sm text-muted-foreground">{status}</p>
        {sidecarErrors.length > 0 && (
          <div className="mt-2 text-xs text-destructive max-w-md mx-auto text-left">
            {sidecarErrors.map((err, idx) => (
              <div key={idx} className="truncate" title={err}>
                {err}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
