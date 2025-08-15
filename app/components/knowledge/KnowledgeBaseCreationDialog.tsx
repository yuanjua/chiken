"use client";

import { useState, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useAtom } from "jotai";
import {
  zoteroSelectedKeysAtom,
  zoteroCollectionsDataAtom,
} from "@/store/uiAtoms";
import {
  knowledgeBasesAtom,
  activeKnowledgeBaseIdAtom,
  selectedKnowledgeBaseIdsAtom,
} from "@/store/ragAtoms";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import {
  Database,
  Loader2,
  Egg,
  AlertCircle,
  Settings,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useZoteroStreaming } from "@/hooks/useZoteroStreaming";
import type { TreeNode } from "@/store/uiAtoms";
import {
  createKnowledgeBase,
  getKnowledgeBases,
  getZoteroCollectionItems,
  getSystemConfig,
  updateSystemConfig,
} from "@/lib/api-client";

interface KnowledgeBaseCreationDialogProps {
  children: React.ReactNode;
  mode?: "standalone" | "collections"; // 'standalone' for new KB button, 'collections' for Zotero
}

export function KnowledgeBaseCreationDialog({
  children,
  mode = "collections",
}: KnowledgeBaseCreationDialogProps) {
  const t = useTranslations("KB.Create");
  const [selectedKeys, setSelectedKeys] = useAtom(zoteroSelectedKeysAtom);
  const [collections] = useAtom(zoteroCollectionsDataAtom);
  const [knowledgeBases, setKnowledgeBases] = useAtom(knowledgeBasesAtom);
  const [, setActiveKnowledgeBaseId] = useAtom(activeKnowledgeBaseIdAtom);
  const [selectedKnowledgeBaseIds, setSelectedKnowledgeBaseIds] = useAtom(
    selectedKnowledgeBaseIdsAtom,
  );
  const [isOpen, setIsOpen] = useState(false);
  const [knowledgeBaseName, setKnowledgeBaseName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Chunk parameters with defaults from user config
  const [chunkSize, setChunkSize] = useState<number>(1600);
  const [chunkOverlap, setChunkOverlap] = useState<number>(300);
  const [defaultChunkSize, setDefaultChunkSize] = useState<number>(1600);
  const [defaultChunkOverlap, setDefaultChunkOverlap] = useState<number>(300);
  
  // Reference filtering with default from user config
  const [enableReferenceFiltering, setEnableReferenceFiltering] = useState<boolean>(true);
  const [defaultEnableReferenceFiltering, setDefaultEnableReferenceFiltering] = useState<boolean>(true);

  // Load user config defaults when dialog opens
useEffect(() => {
  if (!isOpen) return;
  (async () => {
    try {
      const config = await getSystemConfig();
      if (config) {
        const cs = config.chunk_size || 1600;
        const co = config.chunk_overlap || 300;
        setDefaultChunkSize(cs);
        setDefaultChunkOverlap(co);
        setDefaultEnableReferenceFiltering(config.enable_reference_filtering);
        setChunkSize(cs);
        setChunkOverlap(co);
        setEnableReferenceFiltering(config.enable_reference_filtering);
      }
    } catch (e) {
      console.debug('error getting chunk config');
    }
  })();
  // Reset toggle to user config value every time dialog opens
}, [isOpen]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  // Track if user manually edited the KB name
  const [userEditedName, setUserEditedName] = useState(false);

  const { toast } = useToast();
  const { streamZoteroItems } = useZoteroStreaming();

  // Collect all selected collections (matching the selected keys from ZoteroCollections)
  const getSelectedCollections = (nodes: TreeNode[]): TreeNode[] => {
    const result: TreeNode[] = [];
    
    const traverse = (node: TreeNode) => {
      // If this node is selected, include it
      if (selectedKeys.has(node.key)) {
        result.push(node);
      }
      
      // Recursively check children
      node.children.forEach(child => traverse(child));
    };

    nodes.forEach(node => traverse(node));
    return result;
  };

  const selectedCollections = useMemo(
    () => (mode === "collections" ? getSelectedCollections(collections) : []),
    [mode, collections, selectedKeys],
  );
  const totalItems = selectedCollections.reduce(
    (sum, coll) => sum + coll.numItems,
    0,
  );

  // Auto-generate a KB name whenever the top-level selection changes (unless the user has typed their own)
  useEffect(() => {
    if (mode !== "collections") return;
    if (userEditedName) return; // don't overwrite manual edits

    if (selectedCollections.length === 0) {
      setKnowledgeBaseName("");
      return;
    }

    const namesToShow = selectedCollections.slice(0, 3).map((c) => c.name);
    const remaining = selectedCollections.length - namesToShow.length;
    const suffix = remaining > 0 ? ` +${remaining} more` : "";
    setKnowledgeBaseName(`${namesToShow.join(", ")}${suffix}`);
  }, [mode, selectedCollections, userEditedName]);

  // Function to refresh knowledge bases list
  const refreshKnowledgeBases = async () => {
    try {
      const data = await getKnowledgeBases();
      if (data.knowledgeBases) {
        setKnowledgeBases(data.knowledgeBases);
      }
    } catch (error) {
      console.error("Failed to refresh knowledge bases:", error);
    }
  };

  const handleCreate = async () => {
    if (!knowledgeBaseName.trim()) {
      toast({ title: t("error"), description: t("enterName"), variant: "destructive" });
      return;
    }

    if (mode === "collections" && selectedCollections.length === 0) {
      toast({ title: t("error"), description: t("selectOneCollection"), variant: "destructive" });
      return;
    }

    setIsCreating(true);

    try {
      // Create the knowledge base with chunk parameters
      // The embed_model will be determined by the backend using system config
      const newKB = await createKnowledgeBase({
        name: knowledgeBaseName.trim(),
        description:
          mode === "collections"
            ? `Knowledge base created from ${selectedCollections.length} Zotero collection(s)`
            : `Knowledge base: ${knowledgeBaseName.trim()}`,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        enable_reference_filtering: enableReferenceFiltering,
      });

      // Add the new knowledge base to the list and select it by default
      if (newKB.knowledgeBase) {
        setKnowledgeBases((prev) => [...prev, newKB.knowledgeBase]);

        // Set as primary active knowledge base
        setActiveKnowledgeBaseId(newKB.knowledgeBase.id);

        // Add to selected knowledge bases for multiple selection
        setSelectedKnowledgeBaseIds((prev) => {
          if (!prev.includes(newKB.knowledgeBase.id)) {
            return [...prev, newKB.knowledgeBase.id];
          }
          return prev;
        });
      }

      // Re-fetch config and reset form fields to latest values
      try {
        const config = await getSystemConfig();
        if (config) {
          const cs = config.chunk_size || 1600;
          const co = config.chunk_overlap || 300;
          setDefaultChunkSize(cs);
          setDefaultChunkOverlap(co);
          setDefaultEnableReferenceFiltering(config.enable_reference_filtering);
          setChunkSize(cs);
          setChunkOverlap(co);
          setEnableReferenceFiltering(config.enable_reference_filtering);
        }
      } catch (e) {
        console.debug('error getting chunk config');
      }
      setKnowledgeBaseName("");
      setUserEditedName(false);
      setShowAdvanced(false);

      if (mode === "standalone") {
        // For standalone mode, just close the dialog
        setIsOpen(false);
        setIsCreating(false);
        toast({ title: t("success"), description: t("created", { name: knowledgeBaseName.trim() }) });
        return;
      }

      // For collections mode, continue with Zotero processing
      setIsOpen(false);
      setIsCreating(false);

      // Clear selected collections after successful KB creation
      setSelectedKeys(new Set());

      // Get all individual Zotero item keys from selected collections
      const allZoteroKeys = new Set<string>();

      for (const collection of selectedCollections) {
        try {
          const data = await getZoteroCollectionItems(collection.key);

          if (data.items && Array.isArray(data.items)) {
            data.items.forEach((item: any) => {
              if (item.key) {
                allZoteroKeys.add(item.key);
              }
            });
          }
        } catch (error) {
          console.error(
            `Failed to fetch items from collection ${collection.name}:`,
            error,
          );
        }
      }

      const uniqueKeys = Array.from(allZoteroKeys);

      if (uniqueKeys.length === 0) {
        toast({ title: t("warning"), description: t("noItems"), variant: "default" });
        return;
      }

      // Start the background streaming process
      await streamZoteroItems(
        knowledgeBaseName.trim(),
        newKB.knowledgeBase.id,
        uniqueKeys,
      );

      // Refresh the KB list to show final document count after a delay
      setTimeout(() => {
        refreshKnowledgeBases();
      }, 2000);
    } catch (err: any) {
      console.error("Error creating knowledge base:", err);
      toast({ title: t("error"), description: err instanceof Error ? err.message : t("createFailed"), variant: "destructive" });
      setIsCreating(false); // Only disable on error during setup
    }
  };

const handleParamChange = async (params: Partial<{chunkSize: number; chunkOverlap: number; enableReferenceFiltering: boolean}>) => {
  if (params.chunkSize !== undefined) setChunkSize(params.chunkSize);
  if (params.chunkOverlap !== undefined) setChunkOverlap(params.chunkOverlap);
  if (params.enableReferenceFiltering !== undefined) setEnableReferenceFiltering(params.enableReferenceFiltering);
  await updateSystemConfig({
    chunk_size: params.chunkSize !== undefined ? params.chunkSize : chunkSize,
    chunk_overlap: params.chunkOverlap !== undefined ? params.chunkOverlap : chunkOverlap,
    enable_reference_filtering: params.enableReferenceFiltering !== undefined ? params.enableReferenceFiltering : enableReferenceFiltering,
  });
};

  const getDialogTitle = () => {
    if (mode === "standalone") {
      return t("titleNew");
    }
    return t("titleFromCollections");
  };

  const getDialogDescription = () => {
    if (mode === "standalone") {
      return t("descNew");
    }
    return t("descFromCollections");
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] flex flex-col">
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            {getDialogTitle()}
          </DialogTitle>
          <DialogDescription>{getDialogDescription()}</DialogDescription>
        </DialogHeader>

        <ScrollArea
          className="flex-1 pr-4 -mr-4 overflow-y-auto"
          style={{ minHeight: 0 }}
        >
          <div className="space-y-4 pb-6 px-1">
          {/* Knowledge Base Name Input */}
          <div className="space-y-2">
            <Label htmlFor="kb-name">{t("nameLabel")}</Label>
            <Input
              id="kb-name"
              placeholder={t("namePlaceholder")}
              value={knowledgeBaseName}
              onChange={(e) => {
                setKnowledgeBaseName(e.target.value);
                setUserEditedName(true);
              }}
              disabled={isCreating}
            />
          </div>

          {/* Advanced Settings Toggle */}
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium">{t("processingParams")}</Label>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="h-8 px-2 text-xs"
            >
              <Settings className="h-3 w-3 mr-1" />
              {showAdvanced ? t("hideAdvanced") : t("showAdvanced")}
            </Button>
          </div>

          {/* Advanced Settings */}
          {showAdvanced && (
            <div className="space-y-4 p-4 border rounded-lg bg-muted/20">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="chunk-size" className="text-sm">{t("chunkSize")}</Label>
                  <Input
                    id="chunk-size"
                    type="number"
                    min="100"
                    max="4000"
                    value={chunkSize}
                    onChange={async (e) => {
                      const val = parseInt(e.target.value) || defaultChunkSize;
                      await handleParamChange({ chunkSize: val });
                    }}
                    disabled={isCreating}
                  />
                  <p className="text-xs text-muted-foreground">{t("chunkSizeHelp")}</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="chunk-overlap" className="text-sm">{t("chunkOverlap")}</Label>
                  <Input
                    id="chunk-overlap"
                    type="number"
                    min="0"
                    max="1000"
                    value={chunkOverlap}
                    onChange={async (e) => {
                      const val = parseInt(e.target.value) || defaultChunkOverlap;
                      await handleParamChange({ chunkOverlap: val });
                    }}
                    disabled={isCreating}
                  />
                  <p className="text-xs text-muted-foreground">{t("chunkOverlapHelp")}</p>
                </div>
              </div>

              {/* <div className="flex items-center justify-between py-2">
                <div className="space-y-1">
                  <Label className="text-sm">{t("enableRefFiltering")}</Label> 
                  <span className="text-xs text-gray-500">{t("refFilteringBadge")}</span>
                  <p className="text-xs text-muted-foreground">{t("refFilteringHelp")}</p>
                </div>
                <Switch
                  id="reference-filtering"
                  checked={enableReferenceFiltering}
                  onCheckedChange={async (val) => {
                    await handleParamChange({ enableReferenceFiltering: val });
                  }}
                  disabled={isCreating}
                  className="data-[state=checked]:bg-blue-400 data-[state=unchecked]:bg-black-300 dark:data-[state=checked]:bg-green-500 dark:data-[state=unchecked]:bg-gray-600 [&>span]:bg-white [&>span]:shadow-md"
                />
              </div> */}

            </div>
          )}

          {mode === "collections" && (
            <>
              <Separator />

              {/* Selected Collections Summary */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-medium">{t("selectedCollections")}</Label>
                  <Badge variant="secondary">
                    {t("collectionsCount", { count: selectedCollections.length })}, {totalItems} {t("items", { count: totalItems })}
                  </Badge>
                </div>

                {selectedCollections.length === 0 ? (
                  <div className="text-sm text-muted-foreground text-center py-4">
                    {t("noCollectionsSelected")}
                  </div>
                ) : (
                  <ScrollArea className="h-32 border rounded-md p-3">
                    <div className="space-y-2">
                      {selectedCollections.map((collection) => (
                        <div
                          key={collection.key}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="truncate flex-1">
                            {collection.name}
                          </span>
                          <Badge variant="outline" className="ml-2 text-xs">{t("items", { count: collection.numItems })}</Badge>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </div>
            </>
          )}
          </div>
        </ScrollArea>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2 pt-4 border-t border-gray-200">
          <Button
            size="sm"
            className="gap-2"
            onClick={() => setIsOpen(false)}
            disabled={isCreating}
          >
            {t("cancel")}
          </Button>
          <Button
            size="sm"
            className="w-full justify-start gap-2"
            onClick={handleCreate}
            disabled={
              isCreating ||
              !knowledgeBaseName.trim() ||
              (mode === "collections" && selectedCollections.length === 0)
            }
          >
            {isCreating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {t("creating")}
              </>
            ) : (
              <>
                <Database className="h-4 w-4 mr-2" />
                {t("createKb")}
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
