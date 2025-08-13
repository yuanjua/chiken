import { Button } from "../ui/button";
import { MCPConfigDialog } from "./MCPConfigDialog";
import { MonitorCog, X } from "lucide-react";
import { useTranslations } from "next-intl";

export function MCPSection() {
  const t = useTranslations("MCP");
  return (
    <div className=" flex pl-4 pr-4">
      <div className="flex-1">
        <div className="flex justify-between">
          <h3 className="text-sm font-medium">{t("Section.title")}</h3>
          <MCPConfigDialog>
            <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
              <MonitorCog className="h-3 w-3" />
            </Button>
          </MCPConfigDialog>
        </div>
        <div className="text-xs text-gray-500">{t("Section.desc")}</div>
      </div>
    </div>
  );
}
