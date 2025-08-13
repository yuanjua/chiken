"use client";

import { useAtom } from "jotai";
import { useState, useEffect } from "react";
import {
  isSidebarOpenAtom,
  isKnowledgeBaseSidebarOpenAtom,
} from "@/store/uiAtoms";
import Sidebar from "./Sidebar";
import { KnowledgeBaseSidebar } from "../knowledge/KnowledgeBaseSidebar";
import { SettingsDialog } from "../settings/SettingsDialog";
import { Button } from "@/components/ui/button";

interface AppLayoutProps {
  children?: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const [isSidebarOpen] = useAtom(isSidebarOpenAtom);
  const [isKnowledgeBaseSidebarOpen] = useAtom(isKnowledgeBaseSidebarOpenAtom);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Listen for the custom 'open-settings' event
  useEffect(() => {
    const handleOpenSettings = () => {
      setIsSettingsOpen(true);
    };

    // Use globalThis.window to avoid TypeScript errors and ensure browser-only event listeners
    const win =
      typeof globalThis !== "undefined" && (globalThis as any).window
        ? (globalThis as any).window
        : undefined;
    if (win) {
      win.addEventListener("open-settings", handleOpenSettings);
    }

    return () => {
      if (win) {
        win.removeEventListener("open-settings", handleOpenSettings);
      }
    };
  }, []);

  return (
    <div className="h-screen bg-background flex main-content">
      {/* Left Sidebar */}
      <aside
        className={`
          h-full bg-background border-r border-gray-300 overflow-hidden
          transition-all duration-300 ease-in-out
          ${
            isSidebarOpen
              ? "w-64 opacity-100 translate-x-0"
              : "w-0 opacity-0 -translate-x-full pointer-events-none"
          }
        `}
        aria-hidden={!isSidebarOpen}
      >
        {/* Only render content when sidebar is open to prevent space allocation */}
        {isSidebarOpen && (
          <div className="w-64 h-full">
            <Sidebar />
          </div>
        )}
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 h-full overflow-hidden">{children}</main>

      {/* Right Sidebar (Knowledge Base) */}
      <aside
        className={`
          h-full bg-background border-l border-gray-300 overflow-hidden
          transition-all duration-300 ease-in-out
          ${
            isKnowledgeBaseSidebarOpen
              ? "w-80 opacity-100 translate-x-0"
              : "w-0 opacity-0 translate-x-full pointer-events-none"
          }
        `}
        aria-hidden={!isKnowledgeBaseSidebarOpen}
      >
        {isKnowledgeBaseSidebarOpen && (
          <div className="w-80 h-full">
            <KnowledgeBaseSidebar />
          </div>
        )}
      </aside>

      {/* Settings Dialog */}
      <SettingsDialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />
    </div>
  );
}
