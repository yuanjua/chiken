import React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FileText } from "lucide-react";
import { ModelConfig } from "@/store/chatAtoms";
import { FaGithub } from "react-icons/fa";

interface PdfParserConfigProps {
  selectedModel: ModelConfig;
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void;
}

export function PdfParserConfig({
  selectedModel,
  updateSelectedModelConfig,
}: PdfParserConfigProps) {
  const isParserServer = selectedModel.pdfParserType === "remote";
  const isKreuzbergParser = selectedModel.pdfParserType === "kreuzberg";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileText className="w-4 h-4" />
        <Label className="text-sm font-medium">PDF Parser Configuration</Label>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Left side - Configuration */}
        <div className="lg:col-span-2 space-y-2">
          {/* Parser Type Selection */}
          <div>
            <Label htmlFor="pdfParserType">Parser Type</Label>
            <Select
              value={selectedModel.pdfParserType || "kreuzberg"}
              onValueChange={(value: "kreuzberg" | "remote") =>
                updateSelectedModelConfig("pdfParserType", value)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select PDF parser type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="kreuzberg">Kreuzberg (Local)</SelectItem>
                <SelectItem value="remote">Parser Server</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Parser Server URL */}
          {isParserServer && (
            <div>
              <Label htmlFor="pdfParserUrl">Parser Server URL</Label>
              <Input
                id="pdfParserUrl"
                value={selectedModel.pdfParserUrl || "http://127.0.0.1:24008"}
                onChange={(e) =>
                  updateSelectedModelConfig("pdfParserUrl", e.target.value)
                }
                placeholder="http://127.0.0.1:24008"
              />
            </div>
          )}
        </div>

        {/* Right side - Description */}
        <div className="lg:col-span-2">
          <div className="text-sm p-3 bg-muted rounded-lg h-full flex flex-col justify-center">
            {isParserServer ? (
              <div>
                <strong className="text-foreground">Parser Server</strong>
                <p className="text-muted-foreground mt-1">
                  Uses advanced AI models for superior layout-aware text extraction, formula
                  recognition, table parsing, and OCR capabilities. Requires a
                  running remote or local server and longer parsing time.
                </p>
                <a
                  href="https://github.com/yuanjua/MinerU-API"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:text-blue-600 flex items-center"
                >
                  <span className="inline-block mr-1">
                    <FaGithub />
                  </span>
                  <span>MinerU-API</span>
                </a>
              </div>
            ) : (
              <div>
                <strong className="text-foreground">Kreuzberg Parser</strong>
                <p className="text-muted-foreground mt-1">
                  Local text extraction using Kreuzberg library with
                  support for complex layouts and tables. 
                  (OCR currently not implemented. Limited support for Latex formulas.
                  For math heavy documents, consider using the Parser Server.)
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
