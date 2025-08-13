"use client";

import { useState, useRef, useEffect } from "react";
import { useAtom } from "jotai";
import {
  isRAGActiveAtom,
  ragDocumentsAtom,
  activeKnowledgeBaseIdAtom,
  selectedMentionDocumentsAtom,
} from "@/store/ragAtoms";
import { selectedAgentAtom } from "@/store/chatAtoms";
import { isBackendReadyAtom } from "@/store/uiAtoms";
import { InputControls } from "./InputControls";
import { MessageInput } from "./MessageInput";
import { MentionDisplay } from "./MentionDisplay";
import { UploadStatusDisplay } from "./UploadStatusDisplay";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { FileText } from "lucide-react";

interface ChatInputProps {
  onSubmit: (value: string) => void;
  isLoading: boolean;
  stop: () => void;
  selectedRAGDocs: string[];
  error?: string | null;
}

export function ChatInput({
  onSubmit,
  isLoading,
  stop,
  selectedRAGDocs,
  error,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isRAGActive] = useAtom(isRAGActiveAtom);
  const [ragDocuments] = useAtom(ragDocumentsAtom);
  const [selectedMentionDocs, setSelectedMentionDocs] = useAtom(
    selectedMentionDocumentsAtom,
  );

  const handleRemoveMentionDoc = (docId: string) => {
    setSelectedMentionDocs((prev) => prev.filter((doc) => doc.id !== docId));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSubmit(input);
    setInput("");
  };

  return (
    <div className="space-y-2">
      {/* Upload Status Display */}
      <UploadStatusDisplay />

      {/* Selected Mention Documents Bubbles */}
      <MentionDisplay handleRemoveMentionDoc={handleRemoveMentionDoc} />

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Input Controls and Message Input in a form */}
      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <InputControls isLoading={isLoading} />

        {/* Textarea and Send Button */}
        <MessageInput
          input={input}
          handleInputChange={(e) => setInput(e.target.value)}
          handleSubmit={handleSubmit}
          isLoading={isLoading}
          stop={stop}
          selectedMentionDocsCount={selectedMentionDocs.length}
        />
      </form>
    </div>
  );
}
