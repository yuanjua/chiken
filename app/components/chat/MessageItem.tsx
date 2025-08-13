"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { type Message } from "@ai-sdk/react";
import { cn } from "@/lib/utils";
import MarkdownText from "./MarkdownBubble";
import { UserIcon, BotIcon } from "lucide-react";
import AiGenerating from "../ui/ai-generating";
import React from "react";
import { useTranslations } from "next-intl";

interface MessageItemProps {
  message: Message;
  isLoading: boolean;
  progressMessage?: string | null;
}

function MessageItemComponent({
  message,
  isLoading,
  progressMessage = null,
}: MessageItemProps) {
  const t = useTranslations("Common");
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  const copyToClipboard = (text: string) => {
    const nav = (globalThis as any).navigator as Navigator | undefined;
    if (nav && nav.clipboard) {
      nav.clipboard.writeText(text);
    }
  };

  const formatTimestamp = (timestamp?: number) => {
    if (!timestamp) return "";
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div
      className={cn(
        "flex w-full gap-3 group",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      {!isUser && (
        <Avatar className="h-8 w-8 border">
          <AvatarImage src="/ai-avatar.png" alt="AI" />
          <AvatarFallback className="bg-primary/10">
            <BotIcon className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}

      <div
        className={cn(
          "flex flex-col min-w-0",
          isUser ? "items-end" : "items-start",
        )}
      >
        <Card
          className={cn(
            "border-0 shadow-sm max-w-full",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted/50",
          )}
        >
          <CardContent className="p-3 w-full overflow-hidden">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0 overflow-hidden">
                {isAssistant ? (
                  <MarkdownText content={message.content} />
                ) : (
                  <p className="text-sm">{message.content}</p>
                )}

                {/* Display sources if available */}
                {message.annotations && message.annotations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-border/50">
                    <p className="text-xs font-medium mb-2">{t("sourcesLabel")}</p>
                    <div className="flex flex-wrap gap-1">
                      {message.annotations.map(
                        (annotation: any, index: number) => (
                          <span
                            key={index}
                            className="text-xs bg-muted/50 rounded px-2 py-1"
                          >
                            {annotation.name || `Source ${index + 1}`}
                          </span>
                        ),
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {isLoading && (
          <div className="flex items-center gap-1 animate-pulse">
            <span className="text-xs text-muted-foreground mt-1 px-1">
              {progressMessage || <AiGenerating />}
            </span>
          </div>
        )}
        {!isLoading && (
          <span className="text-xs text-muted-foreground mt-1 px-1">
            {formatTimestamp(message.createdAt?.getTime())}
          </span>
        )}
      </div>

      {isUser && (
        <Avatar className="h-8 w-8 border">
          <AvatarImage src="/user-avatar.png" alt="User" />
          <AvatarFallback className="bg-secondary">
            <UserIcon className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}

// Memoize to avoid unnecessary re-renders when props haven't changed
export const MessageItem = React.memo(MessageItemComponent, (prev, next) => {
  return (
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.isLoading === next.isLoading &&
    prev.progressMessage === next.progressMessage
  );
});
