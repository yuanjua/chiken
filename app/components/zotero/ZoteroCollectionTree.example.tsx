"use client";

import React, { useState } from "react";
import ZoteroCollectionTree from "./ZoteroCollectionTree";
import { getZoteroCollections } from "@/lib/api-client";

export default function ZoteroExample() {
  const [selectedCollection, setSelectedCollection] = useState<string | null>(
    null,
  );
  const [collectionItems, setCollectionItems] = useState<any[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);

  const handleCollectionSelect = async (collectionId: string) => {
    setSelectedCollection(collectionId);
    setLoadingItems(true);

    try {
      const data = await getZoteroCollections();
      setCollectionItems(data.collections || []);
    } catch (error) {
      console.error("Error loading collection items:", error);
      setCollectionItems([]);
    } finally {
      setLoadingItems(false);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar with collection tree */}
      <div className="w-80 border-r border-gray-200 bg-gray-50">
        <ZoteroCollectionTree
          onCollectionSelect={handleCollectionSelect}
          className="h-full p-4"
        />
      </div>

      {/* Main content area */}
      <div className="flex-1 p-6">
        {selectedCollection ? (
          <div>
            <h2 className="text-lg font-semibold mb-4">
              Collection Items ({selectedCollection})
            </h2>

            {loadingItems ? (
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span>Loading items...</span>
              </div>
            ) : (
              <div className="space-y-2">
                {collectionItems.length > 0 ? (
                  collectionItems.map((item, index) => (
                    <div
                      key={index}
                      className="p-3 border border-gray-200 rounded"
                    >
                      <h3 className="font-medium">
                        {item.data?.title || "Untitled"}
                      </h3>
                      <p className="text-sm text-gray-600">
                        {item.data?.itemType}
                      </p>
                      {item.data?.creators && item.data.creators.length > 0 && (
                        <p className="text-sm text-gray-500">
                          By:{" "}
                          {item.data.creators
                            .map((c: any) =>
                              `${c.firstName || ""} ${c.lastName || ""}`.trim(),
                            )
                            .join(", ")}
                        </p>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500">No items in this collection</p>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-gray-500 text-center mt-20">
            <p>Select a collection from the sidebar to view its items</p>
          </div>
        )}
      </div>
    </div>
  );
}
