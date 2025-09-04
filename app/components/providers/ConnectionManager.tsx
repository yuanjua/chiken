"use client";

import { useAtom, useSetAtom } from "jotai";
import { useEffect, useState, createContext, useContext } from "react";
import { listen } from "@tauri-apps/api/event";
import { checkBackendHealth, listSessions } from "@/lib/api-client";
import { TauriService } from "@/lib/tauri-service";
import {
  isBackendReadyAtom,
  isBackendLoadingAtom,
  resetLoadingStatesAtom,
} from "@/store/uiAtoms";

interface ConnectionState {
  isConnecting: boolean;
  isReady: boolean;
  status: string;
  errors: string[];
  attempts: number;
}

const ConnectionContext = createContext<ConnectionState>({
  isConnecting: true,
  isReady: false,
  status: "Checking connection...",
  errors: [],
  attempts: 0,
});

export const useConnection = () => useContext(ConnectionContext);

interface ConnectionManagerProps {
  children: React.ReactNode;
}

export function ConnectionManager({ children }: ConnectionManagerProps) {
  const [isBackendReady, setIsBackendReady] = useAtom(isBackendReadyAtom);
  const [, setIsBackendLoading] = useAtom(isBackendLoadingAtom);
  const resetLoadingStates = useSetAtom(resetLoadingStatesAtom);

  // Local connection state
  const [connectionStatus, setConnectionStatus] = useState("Starting backend...");
  const [sidecarErrors, setSidecarErrors] = useState<string[]>([]);
  const [connectionAttempts, setConnectionAttempts] = useState(0);

  // Initialize backend state
  useEffect(() => {
    if (typeof globalThis !== 'undefined' && (globalThis as any).window === undefined) return;
    
    console.log("🚀 ConnectionManager: Initializing backend state");
    
    // Only reset backend state if it's not already ready
    // This prevents unnecessary resets during locale changes
    if (isBackendReady !== true) {
      console.log("🔄 ConnectionManager: Backend not ready, starting initialization");
      setIsBackendLoading(true);
      setIsBackendReady(false);
      resetLoadingStates();
    } else {
      console.log("✅ ConnectionManager: Backend already ready, skipping reset");
    }

    return () => {
      // Only reset loading state if we set it
      if (isBackendReady !== true) {
        setIsBackendLoading(false);
      }
    };
  }, [setIsBackendLoading, setIsBackendReady, resetLoadingStates, isBackendReady]);

  // Setup sidecar event listeners
  useEffect(() => {
    if (typeof globalThis !== 'undefined' && (globalThis as any).window === undefined) return;

    const setupSidecarListeners = async () => {
      try {
        await listen("sidecar-resolve-error", (event) => {
          console.error("🔴 Sidecar Resolve Error:", event.payload);
          setSidecarErrors((prev) => [...prev, `Resolve Error: ${event.payload}`]);
        });

        await listen("sidecar-spawn-error", (event) => {
          console.error("🔴 Sidecar Spawn Error:", event.payload);
          setSidecarErrors((prev) => [...prev, `Spawn Error: ${event.payload}`]);
        });

        await listen("sidecar-stdout", (event) => {
          console.log("📤 Sidecar Stdout:", event.payload);
        });

        await listen("sidecar-stderr", (event) => {
          console.error("📥 Sidecar Stderr:", event.payload);
        });
      } catch (error) {
        console.warn("Failed to setup sidecar event listeners:", error);
      }
    };

    setupSidecarListeners();
  }, []);

  // Health check with infinite retries
  useEffect(() => {
    if (typeof globalThis !== 'undefined' && (globalThis as any).window === undefined) return;
    
    // Skip health check if backend is already ready
    if (isBackendReady === true) {
      console.log("✅ ConnectionManager: Backend already ready, skipping health check");
      return;
    }

    let timeoutId: NodeJS.Timeout;
    let attempts = 0;

    const checkHealth = async () => {
      attempts++;
      setConnectionAttempts(attempts);
      console.log(`🔍 Health check attempt ${attempts}`);
      
      try {
        const isHealthy = await checkBackendHealth();
        if (isHealthy) {
          // Ensure backend is fully ready with session check
          await listSessions();
          console.log("✅ Backend health and session checks succeeded");
          setConnectionStatus("Connected!");
          setIsBackendLoading(false);
          setIsBackendReady(true);
          
          // In Tauri, reload the page to ensure proper rendering
          const tauriService = TauriService.getInstance();
          if (tauriService.isTauriMode()) {
            const hasReloaded = sessionStorage.getItem('tauri_backend_reloaded');
            if (!hasReloaded) {
              console.log("🔄 Tauri detected: Reloading page after backend connection");
              sessionStorage.setItem('tauri_backend_reloaded', 'true');
              (globalThis as any).window.location.reload();
            } else {
              console.log("✅ Tauri: Already reloaded, continuing normally");
            }
          }
          
          return;
        }
      } catch (error) {
        console.log(`❌ Backend check attempt ${attempts} failed:`, error);
        setConnectionStatus(`Connection attempt ${attempts} failed, retrying...`);
      }

      // Retry every second
      timeoutId = setTimeout(checkHealth, 1000);
    };

    checkHealth();

    return () => {
      clearTimeout(timeoutId);
    };
  }, [setIsBackendLoading, setIsBackendReady, isBackendReady]);

  const connectionState: ConnectionState = {
    isConnecting: !isBackendReady,
    isReady: !!isBackendReady,
    status: connectionStatus,
    errors: sidecarErrors,
    attempts: connectionAttempts,
  };

  return (
    <ConnectionContext.Provider value={connectionState}>
      {children}
    </ConnectionContext.Provider>
  );
}

interface ConnectionOverlayProps {
  loadingText?: string;
  className?: string;
}

export function ConnectionOverlay({ 
  loadingText = "Connecting...", 
  className = "absolute inset-0 bg-background/80 backdrop-blur-sm z-10" 
}: ConnectionOverlayProps) {
  const { isConnecting, status } = useConnection();

  if (!isConnecting) {
    return null;
  }

  return (
    <div className={`${className} flex items-center justify-center`}>
      <div className="text-center space-y-2">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"></div>
        <p className="text-xs text-muted-foreground">{loadingText}</p>
        <p className="text-xs text-muted-foreground/60">{status}</p>
      </div>
    </div>
  );
}

interface ConnectionScreenProps {
  children?: React.ReactNode;
}

export function ConnectionScreen({ children }: ConnectionScreenProps) {
  const { isConnecting, status, errors } = useConnection();

  if (!isConnecting) {
    return <>{children}</>;
  }

  return (
    <div className="h-screen w-screen bg-background flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
        <p className="text-sm text-muted-foreground">{status}</p>
        {errors.length > 0 && (
          <div className="mt-2 text-xs text-destructive max-w-md mx-auto text-left">
            {errors.map((err, idx) => (
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
