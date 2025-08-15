"use client";

import { useEffect, useState } from "react";
import { JotaiProvider } from "@/components/providers/JotaiProvider";
import { ConnectionManager } from "@/components/providers/ConnectionManager";

interface ClientProvidersProps {
  children: React.ReactNode;
}

export function ClientProviders({ children }: ClientProvidersProps) {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // During SSR, render children without client-side providers
  if (!isClient) {
    return <>{children}</>;
  }

  // On client-side, wrap with full provider chain
  return (
    <JotaiProvider>
      <ConnectionManager>
        {children}
      </ConnectionManager>
    </JotaiProvider>
  );
}
