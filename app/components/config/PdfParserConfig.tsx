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
import { useTranslations } from "next-intl";

interface PdfParserConfigProps {
  selectedModel: ModelConfig;
  updateSelectedModelConfig: (field: keyof ModelConfig, value: any) => void;
}

export function PdfParserConfig({
  selectedModel,
  updateSelectedModelConfig,
}: PdfParserConfigProps) {
  const t = useTranslations("PDF");
  const isParserServer = selectedModel.pdfParserType === "remote";
  const isKreuzbergParser = selectedModel.pdfParserType === "kreuzberg";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileText className="w-4 h-4" />
        <Label className="text-sm font-medium">{t("title")}</Label>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Left side - Configuration */}
        <div className="lg:col-span-2 space-y-2">
          {/* Parser Type Selection */}
          <div>
            <Label htmlFor="pdfParserType">{t("parserType")}</Label>
            <Select
              value={selectedModel.pdfParserType || "kreuzberg"}
              onValueChange={(value: "kreuzberg" | "remote") =>
                updateSelectedModelConfig("pdfParserType", value)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder={t("selectParserType")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="kreuzberg">{t("kreuzbergLocal")}</SelectItem>
                <SelectItem value="remote">{t("parserServer")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Parser Server URL */}
          {isParserServer && (
            <div>
              <Label htmlFor="pdfParserUrl">{t("serverUrl")}</Label>
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
                <strong className="text-foreground">{t("parserServer")}</strong>
                <p className="text-muted-foreground mt-1">{t("parserServerDesc")}</p>
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
                <strong className="text-foreground">{t("kreuzberg")}</strong>
                <p className="text-muted-foreground mt-1">{t("kreuzbergDesc")}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
