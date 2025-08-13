import { useState, useEffect } from "react";
import * as apiClient from "@/lib/api-client";
import { useToast } from "./use-toast";

interface Session {
  session_id: string;
  title: string;
  created_at: string;
  last_activity: string;
  message_count: number;
}

export function useSessionsStatus() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const fetchSessions = async () => {
      try {
        const response = await apiClient.listSessions();
        if (isMounted) {
          setSessions(response.sessions);
          setIsLoading(false);
        }
      } catch (error) {
        console.error("Failed to fetch sessions:", error);
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchSessions();

    return () => {
      isMounted = false;
    };
  }, []);

  return { sessions, isLoading };
}
