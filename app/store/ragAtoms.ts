import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export interface RAGDocument {
  id: string;
  name: string;
  type: string;
  size: number;
  url: string;
  uploadedAt: Date;
  status: "processing" | "uploading" | "ready" | "error" | string;
  knowledgeBaseId: string;
  isDuplicate?: boolean;
  fileHash?: string;
  fromCache?: boolean;
  error?: string;
  progress?: number;
  chunks?: number;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  documentCount: number;
  isActive: boolean;
}

export interface RAGQuery {
  query: string;
  documents: string[];
  sources?: RAGSource[];
}

export interface RAGSource {
  id: string;
  documentId: string;
  documentName: string;
  content: string;
  score: number;
  page?: number;
  chunk?: number;
}

// Stable initial knowledge base data
const defaultKnowledgeBase: KnowledgeBase = {
  id: "kb-default",
  name: "Default Knowledge Base",
  description: "Default knowledge base for documents",
  createdAt: new Date().toISOString(),
  documentCount: 0,
  isActive: true,
};

// Knowledge bases management
export const knowledgeBasesAtom = atomWithStorage<KnowledgeBase[]>(
  "knowledge-bases",
  [],
);

// Current active knowledge base
export const activeKnowledgeBaseIdAtom = atomWithStorage<string | null>(
  "active-knowledge-base",
  "uploaded-documents",
);

// Multiple selected knowledge bases for querying (persistent)
export const selectedKnowledgeBaseIdsAtom = atomWithStorage<string[]>(
  "selected-knowledge-base-ids",
  [],
);

// RAG documents management
// This atom holds all documents from various knowledge bases, acting as a client-side cache.
// It is NOT persisted to localStorage to avoid exceeding storage quotas.
export const ragDocumentsAtom = atom<RAGDocument[]>([]);

// Selected documents for current context
export const selectedRAGDocumentsAtom = atom<string[]>([]);

// RAG panel state
export const isRAGPanelOpenAtom = atomWithStorage<boolean>(
  "rag-panel-open",
  false,
);

// Current RAG query and results
export const currentRAGQueryAtom = atom<RAGQuery | null>(null);

// Derived atom for active knowledge base
export const activeKnowledgeBaseAtom = atom((get) => {
  const knowledgeBases = get(knowledgeBasesAtom);
  const activeId = get(activeKnowledgeBaseIdAtom);
  if (!activeId) return knowledgeBases[0] || defaultKnowledgeBase;
  return (
    knowledgeBases.find((kb) => kb.id === activeId) ||
    knowledgeBases[0] ||
    defaultKnowledgeBase
  );
});

// Derived atom for documents in active knowledge base
export const activeKnowledgeBaseDocumentsAtom = atom((get) => {
  const allDocs = get(ragDocumentsAtom);
  const activeKbId = get(activeKnowledgeBaseIdAtom);
  if (!activeKbId) return [];
  return allDocs.filter((doc) => doc.knowledgeBaseId === activeKbId);
});

// Derived atom for selected documents
export const selectedDocumentsAtom = atom((get) => {
  const allDocs = get(ragDocumentsAtom);
  const selectedIds = get(selectedRAGDocumentsAtom);
  return allDocs.filter((doc) => selectedIds.includes(doc.id));
});

// RAG context active indicator
export const isRAGActiveAtom = atom((get) => {
  const selectedDocs = get(selectedRAGDocumentsAtom);
  const activeKb = get(activeKnowledgeBaseAtom);
  return selectedDocs.length > 0 && activeKb.isActive;
});

// Atom to track IDs of documents being actively processed or uploaded
export const processingDocumentIdsAtom = atom<Set<string>>(new Set<string>());

// Document upload progress
export const documentUploadProgressAtom = atom<Record<string, number>>({});

// Document interface for @ mentions
export interface MentionDocument {
  id: string;
  title: string;
  source: string;
  key?: string;
  content?: string;
}

// Selected documents for @ mentions in chat
export const selectedMentionDocumentsAtom = atom<MentionDocument[]>([]);
