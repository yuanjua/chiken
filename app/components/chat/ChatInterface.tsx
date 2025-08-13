"use client";

import React, { useEffect } from "react";
import { useAtom } from "jotai";
import {
  chatSessionsMapAtom,
  activeSessionIdAtom,
  sessionMessagesAtom,
  streamingStateAtom,
  SessionMessagesBlock,
} from "@/store/sessionAtoms";
import { selectedMentionDocumentsAtom } from "@/store/ragAtoms";
import { getSessionMessages } from "@/lib/api-client";
import { backgroundStreamingManager } from "@/lib/background-streaming";
import { ChatInput } from "./ChatInput";
import { ChatHeader } from "./ChatHeader";
import { MessageList } from "./MessageList";
import { type Message } from "@ai-sdk/react";
import { type ChatMessage } from "@/store/sessionAtoms";

interface ChatInterfaceProps {
  sessionId: string;
}

// Rename and update this function to convert from stored ChatMessage to display Message
const convertStoredMessageToDisplay = (storedMsg: ChatMessage): Message => {
  return {
    id: storedMsg.id,
    role: storedMsg.role,
    content: storedMsg.content,
    createdAt: new Date(storedMsg.timestamp), // Use stored timestamp for display
  };
};

// Limit how many messages we keep per session in memory to avoid unbounded growth
const MAX_MESSAGES_PER_SESSION = 200;

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [chatSessionsMap, setChatSessionsMap] = useAtom(chatSessionsMapAtom);
  const [, setActiveSessionId] = useAtom(activeSessionIdAtom);
  const [sessionMessages, setSessionMessages] = useAtom(sessionMessagesAtom);
  const [streamingState] = useAtom(streamingStateAtom);
  const [selectedMentionDocs] = useAtom(
    selectedMentionDocumentsAtom,
  );

  const isLoading =
    streamingState?.sessionId === sessionId &&
    streamingState?.isStreaming === true;
  const progressMessage = streamingState?.progress?.message;

  const messages =
    sessionMessages[sessionId]?.msgs.map(convertStoredMessageToDisplay) ?? [];

  useEffect(() => {
    if (sessionId) {
      setActiveSessionId(sessionId);

      const loadMessages = async () => {
        if (!sessionMessages[sessionId]) {
          try {
            const {
              messages: backendMessages,
              has_more,
              oldest,
            } = await getSessionMessages(sessionId);
            if (Array.isArray(backendMessages) && backendMessages.length > 0) {
              let storeMessages = backendMessages.map(
                (msg: any, index: number) => ({
                  id: `${sessionId}-${msg.role}-${typeof msg.id === "string" && msg.id ? msg.id : typeof msg.timestamp === "number" ? msg.timestamp : "auto_gen"}-${index}-${Math.random().toString(36).substring(2, 9)}`,
                  role: msg.role,
                  content: msg.content,
                  timestamp: new Date(msg.timestamp || Date.now()).getTime(),
                }),
              );

              if (storeMessages.length > MAX_MESSAGES_PER_SESSION) {
                storeMessages = storeMessages.slice(-MAX_MESSAGES_PER_SESSION);
              }

              const block: SessionMessagesBlock = {
                msgs: storeMessages,
                oldest: oldest ?? null,
                hasMore: has_more,
              };

              setSessionMessages((prev) => ({ ...prev, [sessionId]: block }));
            }
          } catch (error) {
            console.error("Error loading session messages:", error);
          }
        }
      };

      loadMessages();
    }
  }, [sessionId, setActiveSessionId, sessionMessages, setSessionMessages]);

  const handleSubmit = async (inputValue: string) => {
    if ((!inputValue.trim() && selectedMentionDocs.length === 0) || isLoading) {
      return;
    }

    try {
      await backgroundStreamingManager.startStreaming(
        sessionId,
        inputValue.trim(),
      );
    } catch (error) {
      console.error("Error sending message:", error);
      // Optionally, display an error message to the user
    }
  };

  const stop = () => {
    backgroundStreamingManager.stopStreaming();
  };

  // Function to load older messages from backend when needed
  const loadOlderMessages = async () => {
    const block = sessionMessages[sessionId];
    if (!block || !block.hasMore) return false;

    try {
      const {
        messages: backendMessages,
        has_more,
        oldest,
      } = await getSessionMessages(sessionId, block.oldest ?? undefined);

      if (backendMessages.length === 0) {
        setSessionMessages((prev) => ({
          ...prev,
          [sessionId]: { ...block, hasMore: false },
        }));
        return false;
      }

      const newMsgs = backendMessages.map((msg: any, index: number) => ({
        id: `${sessionId}-${msg.role}-${typeof msg.id === "string" && msg.id ? msg.id : typeof msg.timestamp === "number" ? msg.timestamp : "auto_gen"}-${index}-${Math.random().toString(36).substring(2, 9)}`,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.timestamp || Date.now()).getTime(),
      }));

      const merged = [...newMsgs, ...block.msgs]; // oldest -> newest
      const sliced = merged.slice(0, MAX_MESSAGES_PER_SESSION);

      const newBlock: SessionMessagesBlock = {
        msgs: sliced,
        oldest: oldest ?? block.oldest,
        hasMore: has_more,
      };

      setSessionMessages((prev) => ({ ...prev, [sessionId]: newBlock }));
      return true;
    } catch (error) {
      console.error("Failed loading older messages", error);
      return false;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ChatHeader sessionId={sessionId} messagesLength={messages.length} />

      <div className="flex-1 flex flex-col min-h-0">
        {/* key forces MessageList to remount on session switch, guaranteeing scroll-to-bottom */}
        <MessageList
          key={sessionId}
          messages={messages}
          isLoading={isLoading}
          progressMessage={progressMessage}
          onLoadOlder={loadOlderMessages}
          hasMore={sessionMessages[sessionId]?.hasMore ?? false}
        />
      </div>

      <div className="px-4 pb-4 pt-2 w-full border-t border-gray-300">
        <ChatInput
          onSubmit={handleSubmit}
          isLoading={isLoading}
          stop={stop}
          selectedRAGDocs={[]}
        />
      </div>
    </div>
  );
}
