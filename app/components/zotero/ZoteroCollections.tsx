"use client";

import { useState, useEffect, useCallback } from "react";
import { useAtom } from "jotai";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Database,
  Minus,
  Check,
} from "lucide-react";
import {
  getZoteroCollections,
  type ZoteroCollection,
  type ZoteroCollectionsResponse,
} from "@/lib/api-client";
import {
  zoteroCollectionsLoadedAtom,
  zoteroCollectionsDataAtom,
  zoteroSelectedKeysAtom,
  isBackendReadyAtom,
  type TreeNode,
} from "@/store/uiAtoms";
import { Button } from "../ui/button";
import { useTranslations } from "next-intl";

interface CollectionTreeItemProps {
  node: TreeNode;
  onToggleExpand: (key: string) => void;
  onToggleSelect: (key: string, isSelected: boolean) => void;
  level: number;
}

function CollectionTreeItem({
  node,
  onToggleExpand,
  onToggleSelect,
  level,
}: CollectionTreeItemProps) {
  const hasChildren = node.children.length > 0;
  const indentLevel = level * 16; // 16px per level

  const handleToggleExpand = () => {
    if (hasChildren) {
      onToggleExpand(node.key);
    }
  };

  const handleToggleSelect = (checked: boolean) => {
    onToggleSelect(node.key, checked);
  };

  return (
    <div>
      <div
        className="flex items-center py-1 px-2 hover:bg-muted/50 rounded-sm cursor-pointer group"
        style={{ paddingLeft: `${indentLevel + 8}px` }}
      >
        {/* Expand/Collapse Icon */}
        <div
          className="flex items-center justify-center w-4 h-4 mr-1"
          onClick={handleToggleExpand}
        >
          {hasChildren ? (
            node.isExpanded ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
            )
          ) : (
            <div className="w-3 h-3" /> /* Spacer for leaf nodes */
          )}
        </div>

        {/* Icon (Library or Folder) */}
        <div className="mr-2">
          {node.nodeType === "library" ? (
            <Database className="h-4 w-4" />
          ) : hasChildren ? (
            node.isExpanded ? (
              <FolderOpen className="h-4 w-4 text-muted-foreground" />
            ) : (
              <Folder className="h-4 w-4 text-muted-foreground" />
            )
          ) : (
            <Folder className="h-4 w-4 text-muted-foreground" />
          )}
        </div>

        {/* Custom Checkbox with dash for indeterminate state */}
        <div
          className="mr-2 w-4 h-4 border border-input rounded-sm cursor-pointer flex items-center justify-center hover:bg-accent transition-colors"
          onClick={() => handleToggleSelect(!node.isSelected)}
          style={{
            backgroundColor: (node.isSelected || node.isPartiallySelected) ? 'hsl(var(--primary))' : 'transparent',
            borderColor: (node.isSelected || node.isPartiallySelected) ? 'hsl(var(--primary))' : 'hsl(var(--border))'
          }}
        >
          {node.isPartiallySelected && !node.isSelected ? (
            <Minus className="h-3 w-3 text-primary-foreground" />
          ) : node.isSelected ? (
            <Check className="h-3 w-3 text-primary-foreground" />
          ) : null}
        </div>

        {/* Collection Name and Item Count */}
        <div className="flex-1 min-w-0">
          <span 
            className={`truncate ${
              node.nodeType === "library" 
                ? "text-sm font-semibold" 
                : "text-sm"
            }`} 
            title={node.name}
          >
            {node.name}
          </span>
          {node.numItems > 0 && (
            <span className={`text-xs ml-1`}>
              ({node.numItems})
            </span>
          )}
        </div>
      </div>

      {/* Children */}
      {hasChildren && node.isExpanded && (
        <div>
          {node.children.map((child) => (
            <CollectionTreeItem
              key={child.key}
              node={child}
              onToggleExpand={onToggleExpand}
              onToggleSelect={onToggleSelect}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface ZoteroCollectionsProps {
  refreshTrigger?: number; // Used to trigger refresh from parent
}

export default function ZoteroCollections({
  refreshTrigger,
}: ZoteroCollectionsProps) {
  const t = useTranslations("Zotero");
  const [collections, setCollections] = useAtom(zoteroCollectionsDataAtom);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorVisible, setErrorVisible] = useState(false);
  const [selectedKeys, setSelectedKeys] = useAtom(zoteroSelectedKeysAtom);
  const [hasLoaded, setHasLoaded] = useAtom(zoteroCollectionsLoadedAtom);
  const [isBackendReady] = useAtom(isBackendReadyAtom);

  const loadCollections = useCallback(async () => {
    try {
      setLoading(true);
      setError(null); // Reset error state
      const response: ZoteroCollectionsResponse = await getZoteroCollections();

      // Check for errors or empty collections from the backend
      if (response.error || !Array.isArray(response.collections)) {
        setError(
          response.error ||
            "Failed to load collections. Is Zotero running and connected?",
        );
        setErrorVisible(true);
        setCollections([]); // Ensure collections is an empty array
        // Auto-hide the error after a delay and show the default empty state
        setTimeout(() => {
          setErrorVisible(false);
          setError(null);
        }, 3500);
      } else {
        const tree = buildCollectionTree(response.collections);
        setCollections(tree);
      }

      setHasLoaded(true);
    } catch (err: any) {
      console.error("Failed to load Zotero collections:", err);
      setError(err.message || "An unexpected error occurred.");
      setCollections([]); // Reset to empty array on catch
    } finally {
      setLoading(false);
    }
  }, [setCollections, setHasLoaded]);

  useEffect(() => {
    // Only load once on initial mount and when backend is ready
    if (!hasLoaded && isBackendReady === true) {
      console.log("🔄 ZoteroCollections: Loading collections (backend ready)");
      loadCollections();
    } else if (!hasLoaded && isBackendReady !== true) {
      console.log(
        "⏳ ZoteroCollections: Waiting for backend to be ready (status:",
        isBackendReady,
        ")",
      );
    }
  }, [hasLoaded, loadCollections, isBackendReady]);

  // Refresh when refreshTrigger changes
  useEffect(() => {
    if (refreshTrigger && hasLoaded) {
      // Clear selections when refreshing
      setSelectedKeys(new Set());
      loadCollections();
    }
  }, [refreshTrigger, hasLoaded, loadCollections, setSelectedKeys]);

  // Update selection states when selectedKeys changes (e.g., after KB creation)
  useEffect(() => {
    if (collections.length > 0) {
      const updatedCollections = updateSelectionStates(collections, selectedKeys);
      // Only update if the selection states actually changed
      const hasSelectionChanged = JSON.stringify(collections.map(n => ({key: n.key, selected: n.isSelected, partial: n.isPartiallySelected}))) !== 
                                   JSON.stringify(updatedCollections.map(n => ({key: n.key, selected: n.isSelected, partial: n.isPartiallySelected})));
      if (hasSelectionChanged) {
        setCollections(updatedCollections);
      }
    }
  }, [selectedKeys.size, Array.from(selectedKeys).sort().join(',')]); // More specific dependency

  const buildCollectionTree = (collections: ZoteroCollection[]): TreeNode[] => {
    // Group collections by library
    const libraryGroups = new Map<string, ZoteroCollection[]>();
    
    collections.forEach((collection) => {
      const libraryKey = `${collection.library.type}-${collection.library.id}`;
      if (!libraryGroups.has(libraryKey)) {
        libraryGroups.set(libraryKey, []);
      }
      libraryGroups.get(libraryKey)!.push(collection);
    });

    // Build tree with library nodes at the top level
    const rootNodes: TreeNode[] = [];

    libraryGroups.forEach((libraryCollections, libraryKey) => {
      if (libraryCollections.length === 0) return;
      
      const library = libraryCollections[0].library;
      
      // Create collections map for this library
      const collectionMap = new Map<string, TreeNode>();
      
      // Create collection nodes
      libraryCollections.forEach((collection) => {
        collectionMap.set(collection.key, {
          key: collection.key,
          name: collection.data.name,
          numItems: collection.meta.numItems,
          children: [],
          isExpanded: false,
          isSelected: false,
          isPartiallySelected: false,
          parentKey: collection.data.parentCollection || null,
          nodeType: "collection",
          libraryInfo: { type: library.type, id: library.id, name: library.name },
        });
      });

      // Build collection hierarchy within this library
      const libraryRootCollections: TreeNode[] = [];
      
      collectionMap.forEach((node) => {
        if (node.parentKey && collectionMap.has(node.parentKey)) {
          // This is a child collection
          const parent = collectionMap.get(node.parentKey)!;
          parent.children.push(node);
        } else {
          // This is a root collection in this library
          libraryRootCollections.push(node);
        }
      });

      // Sort collections within library
      const sortChildren = (nodes: TreeNode[]) => {
        nodes.sort((a, b) => a.name.localeCompare(b.name));
        nodes.forEach((node) => {
          if (node.children.length > 0) {
            sortChildren(node.children);
          }
        });
      };
      
      sortChildren(libraryRootCollections);

      // Library nodes should have 0 items to prevent double-counting 
      // when library nodes get selected alongside their collection children
      const libraryNode: TreeNode = {
        key: libraryKey,
        name: library.name,
        numItems: 0, // Set to 0 to prevent double-counting with collections
        children: libraryRootCollections,
        isExpanded: true, // Libraries expanded by default
        isSelected: false,
        isPartiallySelected: false,
        parentKey: null,
        nodeType: "library",
        libraryInfo: { type: library.type, id: library.id, name: library.name },
      };

      rootNodes.push(libraryNode);
    });

    // Sort libraries (user libraries first, then groups alphabetically)
    rootNodes.sort((a, b) => {
      const aIsUser = a.libraryInfo?.type === "user";
      const bIsUser = b.libraryInfo?.type === "user";
      
      if (aIsUser && !bIsUser) return -1;
      if (!aIsUser && bIsUser) return 1;
      
      return a.name.localeCompare(b.name);
    });
    
    // Update selection states based on current selectedKeys
    return updateSelectionStates(rootNodes, selectedKeys);
  };

  // Helper function to update selection states in the tree
  const updateSelectionStates = (nodes: TreeNode[], currentSelectedKeys: Set<string>): TreeNode[] => {
    return nodes.map((node) => {
      const updatedChildren = updateSelectionStates(node.children, currentSelectedKeys);

      // Check if this node is directly selected
      const isDirectlySelected = currentSelectedKeys.has(node.key);

      // For leaf nodes (no children), selection is straightforward
      if (updatedChildren.length === 0) {
        return {
          ...node,
          children: updatedChildren,
          isSelected: isDirectlySelected,
          isPartiallySelected: false,
        };
      }

      // For parent nodes, calculate selection state based on children
      const selectedChildrenCount = updatedChildren.filter(
        (child) => child.isSelected,
      ).length;
      const partialChildrenCount = updatedChildren.filter(
        (child) => child.isPartiallySelected,
      ).length;
      const totalChildren = updatedChildren.length;

      const allChildrenSelected = selectedChildrenCount === totalChildren;
      const someChildrenSelected =
        selectedChildrenCount > 0 || partialChildrenCount > 0;

      // A parent node is:
      // - Fully selected ONLY if it's directly selected AND all children are selected
      // - Partially selected if it's directly selected but not all children are selected, OR if some children are selected but the parent isn't
      const nodeIsSelected = isDirectlySelected && allChildrenSelected;
      const nodeIsPartiallySelected = 
        (isDirectlySelected && !allChildrenSelected) || // Parent selected but not all children
        (!isDirectlySelected && someChildrenSelected); // Children selected but not parent

      return {
        ...node,
        children: updatedChildren,
        isSelected: nodeIsSelected,
        isPartiallySelected: nodeIsPartiallySelected,
      };
    });
  };

  const handleToggleExpand = (key: string) => {
    const updateNodeExpansion = (nodes: TreeNode[]): TreeNode[] => {
      return nodes.map((node) => {
        if (node.key === key) {
          return { ...node, isExpanded: !node.isExpanded };
        }
        if (node.children.length > 0) {
          return { ...node, children: updateNodeExpansion(node.children) };
        }
        return node;
      });
    };

    setCollections(updateNodeExpansion(collections));
  };

  const handleToggleSelect = (key: string, isSelected: boolean) => {
    const newSelectedKeys = new Set(selectedKeys);

    // Helper function to find a node in the tree
    const findNode = (
      searchKey: string,
      nodes: TreeNode[],
    ): TreeNode | null => {
      for (const node of nodes) {
        if (node.key === searchKey) return node;
        const found = findNode(searchKey, node.children);
        if (found) return found;
      }
      return null;
    };

    // Helper function to get all descendant keys (including the node itself)
    const getAllDescendantKeys = (node: TreeNode): string[] => {
      const keys = [node.key];
      node.children.forEach((child) => {
        keys.push(...getAllDescendantKeys(child));
      });
      return keys;
    };

    const clickedNode = findNode(key, collections);
    if (!clickedNode) return;

    // Get all descendant keys for this node (including itself)
    const affectedKeys = getAllDescendantKeys(clickedNode);

    if (isSelected) {
      // Add all affected keys
      affectedKeys.forEach((k) => newSelectedKeys.add(k));
    } else {
      // Remove all affected keys
      affectedKeys.forEach((k) => newSelectedKeys.delete(k));
    }

    setSelectedKeys(newSelectedKeys);

    // Update the tree state with proper selection and partial selection
    const updateNodeSelection = (nodes: TreeNode[]): TreeNode[] => {
      return nodes.map((node) => {
        const updatedChildren = updateNodeSelection(node.children);

        // Check if this node is directly selected
        const isDirectlySelected = newSelectedKeys.has(node.key);

        // For leaf nodes (no children), selection is straightforward
        if (updatedChildren.length === 0) {
          return {
            ...node,
            children: updatedChildren,
            isSelected: isDirectlySelected,
            isPartiallySelected: false,
          };
        }

        // For parent nodes, calculate selection state based on children
        const selectedChildrenCount = updatedChildren.filter(
          (child) => child.isSelected,
        ).length;
        const partialChildrenCount = updatedChildren.filter(
          (child) => child.isPartiallySelected,
        ).length;
        const totalChildren = updatedChildren.length;

        const allChildrenSelected = selectedChildrenCount === totalChildren;
        const someChildrenSelected =
          selectedChildrenCount > 0 || partialChildrenCount > 0;

        // A parent node is:
        // - Fully selected ONLY if it's directly selected AND all children are selected
        // - Partially selected if it's directly selected but not all children are selected, OR if some children are selected but the parent isn't
        const nodeIsSelected = isDirectlySelected && allChildrenSelected;
        const nodeIsPartiallySelected = 
          (isDirectlySelected && !allChildrenSelected) || // Parent selected but not all children
          (!isDirectlySelected && someChildrenSelected); // Children selected but not parent

        return {
          ...node,
          children: updatedChildren,
          isSelected: nodeIsSelected,
          isPartiallySelected: nodeIsPartiallySelected,
        };
      });
    };

    setCollections(updateNodeSelection(collections));
  };

  return (
    <div className="p-2">
      {loading && <p>{t("loading")}</p>}
      {error && errorVisible && (
        <div
          className="p-4 my-2 text-sm text-red-700 bg-red-100 rounded-lg dark:bg-red-200 dark:text-red-800"
          role="alert"
        >
          <span className="font-medium">{t("errorPrefix")}</span> {error}
        </div>
      )}
      {!loading && !error && collections.length === 0 && hasLoaded && (
        <div className="text-center py-4">
          <Database className="mx-auto h-8 w-8 text-gray-400" />
          <p className="mt-2 text-sm text-gray-500">{t("empty")}</p>
        </div>
      )}
      {!loading && !error && collections.length > 0 && (
        <>
          {collections.map((node) => (
            <CollectionTreeItem
              key={node.key}
              node={node}
              onToggleExpand={handleToggleExpand}
              onToggleSelect={handleToggleSelect}
              level={0}
            />
          ))}
        </>
      )}
    </div>
  );
}
