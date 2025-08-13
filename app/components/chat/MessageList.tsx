"use client";

import { useEffect, useRef, useState } from "react";
import { ScrollArea, ScrollAreaViewport } from "@/components/ui/scroll-area";
import { type Message } from "@ai-sdk/react";
import { MessageItem } from "./MessageItem";
import { AlertCircle } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { useTranslations } from "next-intl";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  error?: Error;
  progressMessage?: string;
  onLoadOlder?: () => Promise<boolean>; // returns true if loaded
  hasMore?: boolean; // backend has more older messages
}

// Only render a subset of messages initially to speed up session switching
const INITIAL_VISIBLE = 20; // Number of most-recent messages shown right away
const LOAD_MORE_STEP = 20; // How many more to reveal when user asks

export function MessageList({
  messages,
  isLoading,
  error,
  progressMessage,
  onLoadOlder,
  hasMore = false,
}: MessageListProps) {
  const t = useTranslations("Common");
  const viewportRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE);

  const scrollToBottom = () => {
    if (viewportRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    // When switching sessions (fewer messages than visibleCount), reset
    if (visibleCount > messages.length || messages.length <= INITIAL_VISIBLE) {
      setVisibleCount(INITIAL_VISIBLE);
    }

    if (!userScrolledUp.current) {
      scrollToBottom();
    }
  }, [messages, progressMessage, visibleCount]);

  useEffect(() => {
    if (isLoading) {
      userScrolledUp.current = false;
      scrollToBottom();
    }
  }, [isLoading]);

  const handleScroll = async () => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const isAtBottom =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight <= 1;
    userScrolledUp.current = !isAtBottom;

    const totalMessages = messages.length;
    const nearTop = viewport.scrollTop <= 50; // px from top considered near

    if (nearTop) {
      if (totalMessages > visibleCount) {
        setVisibleCount((c) => Math.min(totalMessages, c + LOAD_MORE_STEP));
      } else if (hasMore && onLoadOlder) {
        const loaded = await onLoadOlder();
        if (loaded) {
          // loadOlder brings older messages, so increase visibleCount to reveal them
          setVisibleCount((c) =>
            Math.min(totalMessages + LOAD_MORE_STEP, c + LOAD_MORE_STEP),
          );
        }
      }
    }
  };

  if (messages.length === 0 && !isLoading && !error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center">
        <img src="/bachelor-cap.png" alt={t("botAlt")} className="h-32 mb-4" onContextMenu={e => e.preventDefault()}/>
        <h3 className="text-lg font-semibold mb-2">{t("startConversation")}</h3>
        <p className="text-muted-foreground">{t("emptyHint")}</p>
      </div>
    );
  }

  // Slice the messages so we only render the last N (visibleCount) by default
  const totalMessages = messages.length;
  const visibleMessages =
    totalMessages > visibleCount
      ? messages.slice(totalMessages - visibleCount)
      : messages;
  const lastAssistantMessageId = messages
    .filter((m) => m.role === "assistant")
    .pop()?.id;

  return (
    <ScrollArea className="h-full">
      <ScrollAreaViewport ref={viewportRef} onScroll={handleScroll}>
        <div className="flex flex-col space-y-4 p-4 max-w-[86%] mx-auto">
          {/* Optional manual control retained but hidden; auto loading in scroll */}
          {visibleMessages.map((message) => {
            const isLastAssistantMessage =
              message.role === "assistant" &&
              lastAssistantMessageId === message.id;
            const isAssistantBeingGenerated =
              isLastAssistantMessage && isLoading;

            return (
              <MessageItem
                key={message.id}
                message={message}
                isLoading={isAssistantBeingGenerated}
                progressMessage={
                  isAssistantBeingGenerated ? progressMessage : null
                }
              />
            );
          })}

          {error && (
            <div className="flex gap-3 justify-start">
              <Avatar className="h-8 w-8 mt-1">
                <AvatarFallback>
                  <AlertCircle className="h-4 w-4 text-destructive" />
                </AvatarFallback>
              </Avatar>
              <Card className="max-w-[85%] p-4 bg-destructive/10 border-destructive/20">
                <p className="text-destructive text-sm break-normal">
                  {error.message ||
                    "An error occurred while generating the response."}
                </p>
              </Card>
            </div>
          )}
        </div>
      </ScrollAreaViewport>
    </ScrollArea>
  );
}
