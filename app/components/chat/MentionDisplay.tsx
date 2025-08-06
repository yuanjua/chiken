import { useAtom } from "jotai";
import { selectedMentionDocumentsAtom } from "@/store/ragAtoms";
import { FileText, X } from "lucide-react";

interface MentionDisplayProps {
  handleRemoveMentionDoc: (docId: string) => void;
}

export function MentionDisplay({
  handleRemoveMentionDoc,
}: MentionDisplayProps) {
  const [selectedMentionDocs] = useAtom(selectedMentionDocumentsAtom);

  return (
    <>
      {selectedMentionDocs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedMentionDocs.map((doc) => (
            <div
              key={doc.id}
              className="inline-flex items-center gap-2 px-3 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 text-sm rounded-md border border-green-300"
            >
              <FileText className="h-3 w-3" />
              <span className="max-w-[200px] truncate" title={doc.title}>
                {doc.title}
              </span>
              <button
                onClick={() => handleRemoveMentionDoc(doc.id)}
                className="hover:bg-green-200 dark:hover:bg-green-800 rounded-full p-0.5"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
