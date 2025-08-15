"use client";

import { useState } from "react";
import { useAtom } from "jotai";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  isSidebarOpenAtom,
  zoteroSelectedKeysAtom,
  zoteroCollectionsDataAtom,
} from "@/store/uiAtoms";
import { MessagesSquare, SquareLibrary, Binary, RefreshCw } from "lucide-react";
import ZoteroCollections from "../zotero/ZoteroCollections";
import ChatSessions from "./ChatSessions";
import { KnowledgeBaseCreationDialog } from "../knowledge/KnowledgeBaseCreationDialog";
import { ConnectionOverlay } from "../providers/ConnectionManager";
import type { TreeNode } from "@/store/uiAtoms";
import { useTranslations } from "next-intl";

function SelectedItemsCount() {
  const [selectedKeys] = useAtom(zoteroSelectedKeysAtom);
  const [collections] = useAtom(zoteroCollectionsDataAtom);
  const t = useTranslations("Sidebar");

  if (selectedKeys.size === 0) {
    return null;
  }

  // Calculate total number of items in selected collections
  const getTotalItems = (nodes: TreeNode[]): number => {
    let total = 0;
    for (const node of nodes) {
      if (selectedKeys.has(node.key)) {
        total += node.numItems;
      }
      if (node.children.length > 0) {
        total += getTotalItems(node.children);
      }
    }
    return total;
  };

  const totalItems = getTotalItems(collections);

  return (
    <div className="p-2 bg-muted/30 rounded text-xs text-muted-foreground">
      {t("itemsSelected", { count: totalItems })}
    </div>
  );
}

export default function Sidebar() {
  const t = useTranslations("Sidebar");
  const [isSidebarOpen, setIsSidebarOpen] = useAtom(isSidebarOpenAtom);
  const [, setSelectedKeys] = useAtom(zoteroSelectedKeysAtom);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleRefreshZotero = () => {
    setSelectedKeys(new Set()); // Clear selected state
    setRefreshTrigger((prev) => prev + 1); // Trigger refresh
  };

  return (
    <div className="flex flex-col h-full w-full bg-background relative">
      <ConnectionOverlay loadingText="Loading sessions..." />
      {/* Chat Sessions - Takes 50% of available space */}
      <div className="flex flex-col h-1/2">
        <div className="px-4 py-2 flex-shrink-0">
          <h3 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
            <MessagesSquare className="h-4 w-4" />
            {t("chatSessions")}
          </h3>
        </div>

        <div className="flex-1 overflow-hidden">
          <ChatSessions />
        </div>
      </div>

      <Separator className="flex-shrink-0" />

      {/* Zotero Collections - Takes 50% of available space */}
      <div className="flex flex-col h-1/2">
        <div className="px-4 py-2 flex-shrink-0">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <SquareLibrary className="h-4 w-4" />
              {t("zoteroCollections")}
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefreshZotero}
              className="h-6 w-6 p-0 hover:bg-muted/50"
              title={t("refreshCollections")}
            >
              <RefreshCw className="h-3 w-3" />
            </Button>
          </div>
        </div>

        <div className="flex-1 h-full overflow-hidden overflow-y-auto">
          <ZoteroCollections refreshTrigger={refreshTrigger} />
        </div>

        {/* Selected Items Count - Fixed position above button */}
        <div className="px-4 py-2 flex-shrink-0">
          <SelectedItemsCount />
        </div>

        {/* Knowledge Base Creation - Fixed at bottom */}
        <div className="px-4 py-2 flex-shrink-0">
          <KnowledgeBaseCreationDialog>
            <Button size="sm" className="w-full justify-start gap-2">
              <Binary className="h-4 w-4 text-gray-500" />
              <span className="text-xs text-muted-foreground truncate">
                {t("createKbFromCollections")}
              </span>
            </Button>
          </KnowledgeBaseCreationDialog>
        </div>
      </div>
    </div>
  );
}
