"use client";

import { useAtom } from "jotai";
import { Button } from "@/components/ui/button";
  import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import {
  PanelLeft,
  PanelRight,
  FileText,
  Settings,
  Languages,
} from "lucide-react";
import {
  isSidebarOpenAtom,
  isKnowledgeBaseSidebarOpenAtom,
  isBackendLoadingAtom,
} from "@/store/uiAtoms";
import { selectedRAGDocumentsAtom } from "@/store/ragAtoms";
import { chatSessionsMapAtom } from "@/store/sessionAtoms";
import { useTranslations } from "next-intl";
import { usePathname, useRouter } from "next/navigation";

interface ChatHeaderProps {
  sessionId: string;
  messagesLength: number;
}

export function ChatHeader({ sessionId, messagesLength }: ChatHeaderProps) {
  const t = useTranslations("Common");
  const router = useRouter();
  const pathname = usePathname();
  const [selectedRAGDocs] = useAtom(selectedRAGDocumentsAtom);
  const [isSidebarOpen, setIsSidebarOpen] = useAtom(isSidebarOpenAtom);
  const [isKnowledgeBaseSidebarOpen, setIsKnowledgeBaseSidebarOpen] = useAtom(
    isKnowledgeBaseSidebarOpenAtom,
  );
  const [chatSessionsMap] = useAtom(chatSessionsMapAtom);
  const [isBackendLoading] = useAtom(isBackendLoadingAtom);

  const _formatTimestamp = (timestamp: string | null) => {
    if (!timestamp || timestamp === "1970-01-01T00:00:00.000Z") return "";
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  };

  const changeLocale = (locale: "en" | "zh") => {
    const segments = pathname.split("/");
    const supported = new Set(["en", "zh"]);
    if (segments.length > 1 && supported.has(segments[1])) {
      segments[1] = locale;
      router.push(segments.join("/") || `/${locale}`);
    } else {
      router.push(`/${locale}`);
    }
  };

  return (
    <div className="flex items-center justify-between p-3 border-b border-gray-300 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-3">
        {/* Left Sidebar Toggle - positioned left of chat title */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={`h-6 w-6 p-0 sidebar-button ${
            isSidebarOpen ? "bg-muted/30" : ""
          }`}
          title={t("toggleChatSidebar")}
        >
          <PanelLeft
            className={`h-3 w-3 sidebar-icon ${
              isSidebarOpen ? "sidebar-icon-rotate" : ""
            }`}
          />
        </Button>

        {/* Chat Title */}
        <div className="flex items-center gap-2">
          {/* <MessageSquareText className="h-4 w-4 text-primary" /> */}
          <h2 className="font-semibold">
            {chatSessionsMap[sessionId]?.title || t("chatSession")}
          </h2>
        </div>

        {/* RAG Status */}
        {selectedRAGDocs.length > 0 && (
          <Badge variant="secondary" className="flex items-center gap-1">
            <FileText className="h-3 w-3" />
            {t("documentCount", { count: selectedRAGDocs.length })}
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Chat info */}

        {/* Language Selector */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              title="Language"
            >
              <Languages className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-background dark:bg-gray-800">
            <DropdownMenuItem onClick={() => changeLocale("en")}>English</DropdownMenuItem>
            <DropdownMenuItem onClick={() => changeLocale("zh")}>中文</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Settings Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            // Open settings dialog
            const settingsEvent = new CustomEvent("open-settings");
            if (typeof globalThis !== "undefined" && (globalThis as any).window) {
              (globalThis as any).window.dispatchEvent(settingsEvent);
            }
          }}
          className="h-6 w-6 p-0"
          title={t("settings")}
        >
          <Settings className="h-3 w-3" />
        </Button>

        {/* Right Sidebar Toggle - positioned right of chat info */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            setIsKnowledgeBaseSidebarOpen(!isKnowledgeBaseSidebarOpen)
          }
          className={`h-6 w-6 p-0 sidebar-button ${
            isKnowledgeBaseSidebarOpen ? "bg-muted/30" : ""
          }`}
          title={t("toggleKnowledgeSidebar")}
        >
          <PanelRight
            className={`h-3 w-3 sidebar-icon ${
              isKnowledgeBaseSidebarOpen ? "sidebar-icon-rotate" : ""
            }`}
          />
        </Button>
      </div>
    </div>
  );
}
