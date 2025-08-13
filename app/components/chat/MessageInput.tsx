import { useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Send, Square } from "lucide-react";
import { useTranslations } from "next-intl";

interface MessageInputProps {
  input: string;
  handleInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  isLoading: boolean;
  stop: () => void;
  selectedMentionDocsCount: number;
}

export function MessageInput({
  input,
  handleInputChange,
  handleSubmit,
  isLoading,
  stop,
  selectedMentionDocsCount,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const t = useTranslations("Common");

  const autoResize = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "36px"; // Reset to min height
      const newHeight = Math.min(textarea.scrollHeight, 96); // Max 4 rows (96px)
      textarea.style.height = `${newHeight}px`;
    }
  };

  // Reset textarea height when input is cleared (after sending)
  useEffect(() => {
    if (!input.trim()) {
      const textarea = textareaRef.current;
      if (textarea) {
        textarea.style.height = "36px";
      }
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if ((input.trim() || selectedMentionDocsCount > 0) && !isLoading) {
        // Create a synthetic form event
        const formEvent = new Event("submit", {
          bubbles: true,
          cancelable: true,
        }) as any;
        formEvent.preventDefault = () => {};
        handleSubmit(formEvent);
      }
    }
  };

  return (
    <div className="flex-1 flex items-end gap-1">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => {
          handleInputChange(e);
          autoResize();
        }}
        onKeyDown={handleKeyDown}
        placeholder={
          selectedMentionDocsCount > 0
            ? t("askAboutDocs", { count: selectedMentionDocsCount })
            : t("typeMessagePlaceholder")
        }
        className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        rows={1}
        style={{
          height: "36px",
          minHeight: "36px",
          maxHeight: "96px",
          overflowY: "auto",
        }}
      />

      {isLoading ? (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={stop}
          className="h-9 w-9 p-0 shrink-0"
        >
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          type="submit"
          size="sm"
          variant="ghost"
          disabled={!input.trim() && selectedMentionDocsCount === 0}
          className="h-9 w-9 p-0 shrink-0"
        >
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
