"use client";

import { useAtom } from "jotai";
import { useState, useEffect } from "react";
import {
  selectedKnowledgeBaseIdsAtom,
  knowledgeBasesAtom,
} from "../../store/ragAtoms";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Loader2, FileText, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { queryDocuments } from "@/lib/api-client";
import { useKnowledgeBaseActions } from "@/hooks/useKnowledgeBaseActions";
import { useTranslations } from "next-intl";

export function KnowledgeBaseQuerySection() {
  const t = useTranslations("KB.Query");
  const [activeKnowledgeBaseIds] = useAtom(selectedKnowledgeBaseIdsAtom);
  const [knowledgeBases] = useAtom(knowledgeBasesAtom);

  const [searchQuery, setSearchQuery] = useState("");
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryResults, setQueryResults] = useState<any[]>([]);
  const [selectedResult, setSelectedResult] = useState<any>(null);
  const [isResultDialogOpen, setIsResultDialogOpen] = useState(false);
  const { exportResultsAsPrompt } = useKnowledgeBaseActions();

  // Clear results when query input is emptied
  useEffect(() => {
    if (searchQuery.trim() === "") {
      setQueryResults([]);
    }
  }, [searchQuery]);

  const handleResultClick = (result: any) => {
    setSelectedResult(result);
    setIsResultDialogOpen(true);
  };

  const handleExportPrompt = () => {
    const prompt = exportResultsAsPrompt(
      searchQuery,
      queryResults.map((r) => ({ content: r.content, metadata: r.metadata })),
    );
    // Optionally keep dialog with prompt display in future
  };


  const getDisplayTitle = (result: any) => {
    if (result.metadata?.title) return result.metadata.title;
    if (result.metadata?.source) return result.metadata.source;
    return (
      knowledgeBases.find((kb) => kb.id === result.knowledge_base_name)?.name ||
      "Document"
    );
  };

  const truncateText = (text: string, maxLength: number = 200) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + "...";
  };

  const handleQueryKnowledgeBases = async () => {
    if (!searchQuery.trim() || activeKnowledgeBaseIds.length === 0) return;
    try {
      setIsQuerying(true);
      const requestBody = {
        query_text: searchQuery.trim().replace(/\s+/g, " "),
        knowledge_base_names: activeKnowledgeBaseIds,
        k: 10,
      };
      const data = await queryDocuments(requestBody);
      if (data.results && Array.isArray(data.results)) {
        setQueryResults(data.results);
      } else {
        setQueryResults([]);
      }
    } catch (error) {
      console.error("Error querying knowledge bases:", error);
      setQueryResults([]);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="p-4 flex-shrink-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">{t("title")}</h3>
          <Badge variant="outline">
            {activeKnowledgeBaseIds.reduce(
              (total, kbId) =>
                total +
                (knowledgeBases.find((kb) => kb.id === kbId)?.documentCount ||
                  0),
              0,
            )}{" "}{t("totalDocs")}
          </Badge>
        </div>
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleQueryKnowledgeBases();
            }}
            className="pl-9 pr-20 text-gray-500"
            disabled={isQuerying}
          />
          <Button
            onClick={handleQueryKnowledgeBases}
            disabled={
              isQuerying ||
              !searchQuery.trim() ||
              activeKnowledgeBaseIds.length === 0
            }
            size="sm"
            className="absolute right-1 top-1/2 transform -translate-y-1/2 h-7"
          >
            {isQuerying ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              t("query")
            )}
          </Button>
        </div>
        {/* <div className="text-xs text-gray-400">
          Results are based on similarity score between the query and the documents.
        </div> */}
      </div>
      <div className="flex-1 flex flex-col min-h-0">
        {queryResults.length > 0 && (
          <div className="p-2 flex-shrink-0">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium">{t("results", { count: queryResults.length })}</h4>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={handleExportPrompt}>
                  <Copy className="h-3 w-3 mr-1" /> 
                  <span className="text-xs">{t("exportAsPrompt")}</span>
                </Button>
              </div>
            </div>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-4">
          {queryResults.length > 0 && (
            <div className="space-y-3">
              {queryResults.map((result, index) => (
                <div
                  key={index}
                  className="p-3 border rounded-md bg-card hover:bg-accent/50 cursor-pointer transition-colors"
                  onClick={() => handleResultClick(result)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <h5 className="text-sm font-medium truncate">
                        {getDisplayTitle(result)}
                      </h5>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {knowledgeBases.find(
                            (kb) => kb.id === result.knowledge_base_name,
                          )?.name || t("unknownKb")}
                        </Badge>
                        {result.metadata?.page_number && (
                          <span className="text-xs text-muted-foreground">
                            {t("page")} {result.metadata.page_number}
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground ml-2">
                      {(1 - result.distance).toFixed(3)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {truncateText(result.content)}
                  </p>
                  <div className="mt-2 text-xs text-blue-600">
                    {t("view")}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Full Text Dialog */}
      <Dialog open={isResultDialogOpen} onOpenChange={setIsResultDialogOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[80vh] flex flex-col">
          <DialogHeader className="shrink-0">
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {selectedResult ? getDisplayTitle(selectedResult) : t("document")}
            </DialogTitle>
            <DialogDescription asChild>
              {selectedResult && (
                <div className="text-sm text-muted-foreground">
                  <span className="flex items-center gap-4">
                    <span>
                      {t("knowledgeBase")}:{" "}
                      {knowledgeBases.find(
                        (kb) => kb.id === selectedResult.knowledge_base_name,
                      )?.name || t("unknown")}
                    </span>
                    {selectedResult.metadata?.page_number && (
                      <span>{t("page")} : {selectedResult.metadata.page_number}</span>
                    )}
                    <span>
                      {t("relevanceScore")} {" "}
                      {((1 - selectedResult.distance)).toFixed(3)}
                    </span>
                  </span>
                </div>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto mt-4">
            {selectedResult && (
              <div className="prose prose-sm max-w-none">
                <div className="whitespace-pre-wrap text-xs leading-relaxed">
                  {selectedResult.content}
                </div>
                {selectedResult.metadata &&
                  Object.keys(selectedResult.metadata).length > 0 && (
                    <div className="mt-6 pt-4 border-t">
                      <h4 className="text-sm font-medium mb-2">Metadata</h4>
                      <div className="text-xs text-muted-foreground space-y-1">
                        {Object.entries(selectedResult.metadata).map(
                          ([key, value]) => (
                            <div key={key} className="flex gap-2">
                              <span className="font-medium">{key}:</span>
                              <span>{String(value)}</span>
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  )}
              </div>
            )}
          </div>
          <div className="flex justify-end pt-4 border-t">
            <Button
              variant="outline"
              onClick={() => setIsResultDialogOpen(false)}
            >
              {t("close")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
