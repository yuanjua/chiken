"use client";

import React, { useState, useEffect } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
} from "lucide-react";
import { getZoteroCollections } from "@/lib/api-client";
import { useTranslations } from "next-intl";

// Types for the tree structure
interface TreeNode {
  id: string;
  name: string;
  type: "collection";
  children: TreeNode[];
  itemCount: number;
  expanded?: boolean;
}

interface ZoteroCollectionTreeProps {
  onCollectionSelect?: (collectionId: string) => void;
  className?: string;
}

export default function ZoteroCollectionTree({
  onCollectionSelect,
  className = "",
}: ZoteroCollectionTreeProps) {
  const tZ = useTranslations("Zotero");
  const tSidebar = useTranslations("Sidebar");
  const [collections, setCollections] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      setLoading(true);
      const data = await getZoteroCollections();

      if (data.error) {
        setError(data.error);
      } else {
        // Convert ZoteroCollection[] to TreeNode[]
        const treeNodes: TreeNode[] = data.collections.map((collection) => ({
          id: collection.key,
          name: collection.data.name,
          type: "collection" as const,
          children: [], // Collections API doesn't include hierarchy, would need separate call
          itemCount: collection.meta.numItems,
        }));

        setCollections(treeNodes);
        setError(null);
      }
    } catch (err) {
      console.error("Error loading Zotero collections:", err);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const toggleExpanded = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  const handleCollectionClick = (collectionId: string) => {
    onCollectionSelect?.(collectionId);
  };

  const renderTreeNode = (
    node: TreeNode,
    level: number = 0,
  ): React.ReactNode => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children.length > 0;
    const indent = level * 20;

    return (
      <div key={node.id} className="select-none">
        {/* Node row */}
        <div
          className="flex items-center py-1 px-2 hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer rounded text-sm"
          style={{ paddingLeft: `${8 + indent}px` }}
          onClick={() => handleCollectionClick(node.id)}
        >
          {/* Expand/collapse icon */}
          <div
            className="flex items-center justify-center w-4 h-4 mr-1"
            onClick={(e) => {
              e.stopPropagation();
              if (hasChildren) {
                toggleExpanded(node.id);
              }
            }}
          >
            {hasChildren ? (
              isExpanded ? (
                <ChevronDown className="w-3 h-3 text-gray-500" />
              ) : (
                <ChevronRight className="w-3 h-3 text-gray-500" />
              )
            ) : (
              <div className="w-3 h-3" /> // Spacer for alignment
            )}
          </div>

          {/* Folder icon */}
          <div className="flex items-center justify-center w-4 h-4 mr-2">
            {hasChildren ? (
              isExpanded ? (
                <FolderOpen className="w-4 h-4 text-blue-500" />
              ) : (
                <Folder className="w-4 h-4 text-blue-600" />
              )
            ) : (
              <Folder className="w-4 h-4 text-gray-500" />
            )}
          </div>

          {/* Collection name and item count */}
          <span className="flex-1 truncate">{node.name}</span>
          {node.itemCount > 0 && (
            <span className="ml-2 text-xs text-gray-500 bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded">
              {node.itemCount}
            </span>
          )}
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div className="ml-4">
            {node.children.map((child) => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <span className="text-sm text-gray-600">{tZ("loading")}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="text-red-600 text-sm">
          <p className="font-medium">{tZ("errorPrefix")} {tZ("loading")}</p>
          <p>{error}</p>
          <button
            onClick={loadCollections}
            className="mt-2 px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
          >
            {tSidebar("refreshCollections")}
          </button>
        </div>
      </div>
    );
  }

  if (collections.length === 0) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="text-gray-500 text-sm text-center">
          <Folder className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          <p>{tZ("empty")}</p>
          <p className="text-xs mt-1">{tZ("connectHint")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${className}`}>
      <div className="border-b border-gray-200 dark:border-gray-700 pb-2 mb-2">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 px-2">
          {tZ("collectionsHeader", { count: collections.length })}
        </h3>
      </div>

      <div className="space-y-0.5 max-h-96 overflow-y-auto">
        {collections.map((collection) => renderTreeNode(collection))}
      </div>

      <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={loadCollections}
          className="text-xs text-blue-600 hover:text-blue-800 px-2"
        >
          {tSidebar("refreshCollections")}
        </button>
      </div>
    </div>
  );
}
