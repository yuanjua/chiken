import { store } from "./store";
import {
  sessionMessagesAtom,
  streamingStateAtom,
  chatSessionsMapAtom,
} from "../store/sessionAtoms";
import { selectedMentionDocumentsAtom } from "../store/ragAtoms";
import { selectedAgentAtom } from "../store/chatAtoms";
import {
  streamMessage,
  listSessions,
  convertBackendSessionsToMap,
} from "./api-client";
import type { ChatMessage } from "../store/sessionAtoms";
import { createParser, EventSourceMessage } from "eventsource-parser";

class BackgroundStreamingManager {
  private currentController: AbortController | null = null;

  private async refreshSessions(): Promise<void> {
    try {
      const response = await listSessions();
      const backendSessions = response.sessions || [];
      const existingSessions = store.get(chatSessionsMapAtom);
      const convertedSessions = convertBackendSessionsToMap(
        backendSessions,
        existingSessions,
      );
      store.set(chatSessionsMapAtom, convertedSessions);
    } catch (error) {
      console.error("Failed to refresh sessions:", error);
    }
  }

  async startStreaming(sessionId: string, userMessage: string): Promise<void> {
    this.stopStreaming();
    this.currentController = new AbortController();

    store.set(streamingStateAtom, { sessionId, isStreaming: true });

    const selectedMentionDocs = store.get(selectedMentionDocumentsAtom);
    const finalMessage =
      userMessage.trim() ||
      (selectedMentionDocs.length > 0 ? "..." : userMessage); // User mentioned documents

    const userTimestamp = Date.now();
    const userChatMessage: ChatMessage = {
      id: `${sessionId}-${userTimestamp}-user`,
      role: "user",
      content: finalMessage,
      timestamp: userTimestamp,
    };

    const existingMessages =
      store.get(sessionMessagesAtom)[sessionId]?.msgs || [];
    const isFirstMessage = existingMessages.length === 0;

    store.set(sessionMessagesAtom, (prev) => ({
      ...prev,
      [sessionId]: {
        msgs: [...(prev[sessionId]?.msgs || []), userChatMessage],
        oldest: prev[sessionId]?.oldest || null,
        hasMore: prev[sessionId]?.hasMore || false,
      },
    }));

    if (isFirstMessage) {
      store.set(chatSessionsMapAtom, (prev) => ({
        ...prev,
        [sessionId]: {
          ...prev[sessionId],
          title:
            finalMessage.substring(0, 50) +
            (finalMessage.length > 50 ? "..." : ""),
          preview: finalMessage,
          createdAt: new Date(userTimestamp),
          updatedAt: new Date(userTimestamp),
          messageCount: 1,
          id: sessionId,
        },
      }));
    }

    const assistantTimestamp = Date.now();
    const assistantId = `${sessionId}-${assistantTimestamp}-assistant`;
    const assistantChatMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: assistantTimestamp,
    };

    store.set(sessionMessagesAtom, (prev) => ({
      ...prev,
      [sessionId]: {
        msgs: [...(prev[sessionId]?.msgs || []), assistantChatMessage],
        oldest: prev[sessionId]?.oldest || null,
        hasMore: prev[sessionId]?.hasMore || false,
      },
    }));

    try {
      const selectedAgent = store.get(selectedAgentAtom);
      const context: any = {};
      if (selectedMentionDocs.length > 0) {
        context.mention_documents = selectedMentionDocs.map((doc) => ({
          id: doc.id,
          title: doc.title,
          source: doc.source,
          key: doc.key,
          content: doc.content,
        }));
      }

      const response = await streamMessage(
        sessionId,
        finalMessage,
        selectedAgent,
        this.currentController.signal,
        Object.keys(context).length > 0 ? context : undefined,
      );

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      let accumulatedContent = "";
      const onEvent = (event: EventSourceMessage) => {
        // The 'event' property of EventSourceMessage is the event name,
        // and 'data' is the payload. We are not using named events,
        // so we only need to process the data.
        if (event.data) {
          try {
            const eventPayload = JSON.parse(event.data);

            switch (eventPayload.type) {
              case "content":
                accumulatedContent += eventPayload.data;
                this.updateAssistantMessage(
                  sessionId,
                  assistantId,
                  accumulatedContent,
                );
                break;

              case "progress":
                store.set(streamingStateAtom, {
                  sessionId,
                  isStreaming: true,
                  progress: eventPayload.data,
                });
                break;

              case "error":
                console.error(
                  "Streaming error from backend:",
                  eventPayload.data.message,
                );
                this.updateAssistantMessage(
                  sessionId,
                  assistantId,
                  `Sorry, an error occurred: ${eventPayload.data.message}`,
                );
                break;
            }
          } catch (e) {
            // This can happen if the backend sends a non-JSON string, which we can treat as content
            if (typeof event.data === "string") {
              accumulatedContent += event.data;
              this.updateAssistantMessage(
                sessionId,
                assistantId,
                accumulatedContent,
              );
            } else {
              console.error("Failed to parse SSE event data:", event.data, e);
            }
          }
        }
      };

      const parser = createParser({ onEvent });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        if (this.currentController?.signal.aborted) break;
        const { done, value } = await reader.read(new Uint8Array());
        if (done) break;
        parser.feed(decoder.decode(value, { stream: true }));
      }
    } catch (error: any) {
      if (error.name !== "AbortError") {
        console.error("Streaming error:", error);
        this.updateAssistantMessage(
          sessionId,
          assistantId,
          "Sorry, there was an error generating the response.",
        );
      }
    } finally {
      this.finalizeStreaming(
        sessionId,
        assistantId,
        isFirstMessage,
        assistantTimestamp,
      );
    }
  }

  private updateAssistantMessage(
    sessionId: string,
    assistantId: string,
    content: string,
  ) {
    store.set(sessionMessagesAtom, (prev) => {
      const sessionMessages = prev[sessionId]?.msgs || [];
      const updatedMessages = sessionMessages.map((msg: any) =>
        msg.id === assistantId ? { ...msg, content } : msg,
      );
      return {
        ...prev,
        [sessionId]: {
          ...prev[sessionId],
          msgs: updatedMessages,
        },
      };
    });
  }

  private finalizeStreaming(
    sessionId: string,
    assistantId: string,
    isFirstMessage: boolean,
    assistantTimestamp: number,
  ) {
    store.set(streamingStateAtom, {
      sessionId: null,
      isStreaming: false,
      progress: undefined,
    });
    this.currentController = null;
    store.set(selectedMentionDocumentsAtom, []);

    store.set(chatSessionsMapAtom, (prev) => ({
      ...prev,
      [sessionId]: {
        ...prev[sessionId],
        updatedAt: new Date(assistantTimestamp),
        messageCount: isFirstMessage
          ? 2
          : (prev[sessionId]?.messageCount || 0) + 1,
      },
    }));
  }

  stopStreaming(): void {
    if (this.currentController) {
      this.currentController.abort();
      this.currentController = null;
    }

    store.set(streamingStateAtom, {
      sessionId: null,
      isStreaming: false,
    });
  }

  isStreamingForSession(sessionId: string): boolean {
    const streaming = store.get(streamingStateAtom);
    return streaming?.sessionId === sessionId && streaming.isStreaming === true;
  }
}

export const backgroundStreamingManager = new BackgroundStreamingManager();
