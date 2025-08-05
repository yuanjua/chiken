import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export interface FileUpload {
  id: string;
  file: File;
  progress: number;
  status: "pending" | "uploading" | "success" | "error";
  error?: string;
  url?: string;
}

export type Theme = "light" | "dark" | "system";

// UI state atoms
export const fileUploadsAtom = atom<FileUpload[]>([]);
export const isSidebarOpenAtom = atomWithStorage("is-sidebar-open", true);
export const isKnowledgeBaseSidebarOpenAtom = atomWithStorage(
  "is-knowledge-base-sidebar-open",
  true,
);

// Backend health loading state
export const isBackendLoadingAtom = atom<boolean>(false);
export const isBackendReadyAtom = atom<boolean | null>(null); // null = unknown, false = not ready, true = ready

// Theme management
export const themeAtom = atomWithStorage("theme", "light");

// Panel layout state
export const panelLayoutAtom = atomWithStorage<number[]>(
  "panel-layout",
  [20, 55, 25],
);

// Global loading and error states
export const isAppBusyAtom = atom((get) => {
  const uploads = get(fileUploadsAtom);
  const isConfigLoading = get(isConfigLoadingAtom);
  const isBackendLoading = get(isBackendLoadingAtom);

  const hasActiveUploads = uploads.some(
    (upload) => upload.status === "uploading",
  );

  return hasActiveUploads || isConfigLoading || isBackendLoading;
});

// Import the config loading atom
import { isConfigLoadingAtom } from "./configAtoms";

// Global loading states for sidebar components to prevent re-loading on session switches
export const zoteroCollectionsLoadedAtom = atomWithStorage(
  "zotero-collections-loaded",
  false,
);
export const knowledgeBaseLoadedAtom = atomWithStorage(
  "knowledge-base-loaded",
  false,
);

// Reset loading states that should not persist between sessions
export const resetLoadingStatesAtom = atom(null, (get, set) => {
  set(zoteroCollectionsLoadedAtom, false);
  set(knowledgeBaseLoadedAtom, false);
});

// App initialization state - persisted to prevent re-showing startup screen
export const isAppInitializedAtom = atomWithStorage("app-initialized", false);

// TreeNode interface for Zotero collections
export interface TreeNode {
  key: string;
  name: string;
  numItems: number;
  children: TreeNode[];
  isExpanded: boolean;
  isSelected: boolean;
  isPartiallySelected: boolean;
  parentKey: string | null;
}

// Custom storage for Set<string>
const setStorage = {
  getItem: (key: string) => {
    const value = localStorage.getItem(key);
    if (!value) return new Set<string>();
    try {
      const array = JSON.parse(value);
      return new Set<string>(array);
    } catch {
      return new Set<string>();
    }
  },
  setItem: (key: string, value: Set<string>) => {
    localStorage.setItem(key, JSON.stringify(Array.from(value)));
  },
  removeItem: (key: string) => {
    localStorage.removeItem(key);
  },
};

// Persistent data storage for sidebar components
export const zoteroCollectionsDataAtom = atom<TreeNode[]>([]);
export const zoteroSelectedKeysAtom = atomWithStorage(
  "zotero-selected-keys",
  new Set<string>(),
  setStorage,
);
