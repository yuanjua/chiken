import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Copy, Check, FileCode, Info, ExternalLink } from 'lucide-react';
import { generateExampleConfigs, getSidecarBinaryPath } from '@/lib/mcp-utils';
import { useTranslations } from "next-intl";

export function MCPConfigJSON() {
  const t = useTranslations("MCP.JSON");
  const [configs, setConfigs] = useState<{
    stdio: string;
    http: string;
    sse: string;
  } | null>(null);
  const [copiedStates, setCopiedStates] = useState<Record<string, boolean>>({});
  const [binaryPath, setBinaryPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadConfigs = async () => {
      try {
        const [exampleConfigs, sidecarPath] = await Promise.all([
          generateExampleConfigs(),
          getSidecarBinaryPath(),
        ]);
        
        setConfigs(exampleConfigs);
        setBinaryPath(sidecarPath);
      } catch (error) {
        console.error('Failed to load MCP configs:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadConfigs();
  }, []);

  const handleCopy = async (text: string, configType?: string) => {
    try {
      const nav = (globalThis as any).navigator as Navigator | undefined;
      if (nav && nav.clipboard) {
        await nav.clipboard.writeText(text);
      } else {
        throw new Error("Clipboard API not available");
      }
      if (configType) {
        setCopiedStates((prev) => ({ ...prev, [configType]: true }));
        setTimeout(() => {
          setCopiedStates((prev) => ({ ...prev, [configType]: false }));
        }, 2000);
      }
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  const CopyButton = ({ text, configType }: { text: string; configType: string }) => {
    const isCopied = copiedStates[configType];
    
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => handleCopy(text, configType)}
        className="h-8 px-2"
      >
        {isCopied ? (
          <>
            <Check className="h-4 w-4 mr-1 text-green-600" />
            <span className="text-xs text-green-600">{t("copied")}</span>
          </>
        ) : (
          <>
            <Copy className="h-4 w-4 mr-1" />
            <span className="text-xs">{t("copy")}</span>
          </>
        )}
      </Button>
    );
  };

  const ConfigCard = ({ 
    title, 
    description, 
    config, 
    configType,
    badge 
  }: { 
    title: string; 
    description: string; 
    config: string; 
    configType: string;
    badge?: string;
  }) => (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm">{title}</CardTitle>
            {badge && <Badge variant="outline" className="text-xs">{badge}</Badge>}
          </div>
          <CopyButton text={config} configType={configType} />
        </div>
        <CardDescription className="text-xs">{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <ScrollArea className="h-48 w-full rounded border bg-muted/30">
            <pre className="p-3 text-xs font-mono overflow-x-auto">
              <code className="text-foreground">{config}</code>
            </pre>
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <FileCode className="h-5 w-5" />
          <h3 className="text-sm font-medium">{t("title")}</h3>
          <Badge variant="outline" className="text-xs">{t("loading")}</Badge>
        </div>
        <div className="text-xs text-muted-foreground">
          {t("generating")}
        </div>
      </div>
    );
  }

  if (!configs) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <FileCode className="h-5 w-5" />
          <h3 className="text-sm font-medium">{t("title")}</h3>
          <Badge variant="destructive" className="text-xs">{t("error")}</Badge>
        </div>
        <div className="text-xs text-red-500">
          {t("failed")}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileCode className="h-5 w-5" />
        <h3 className="text-sm font-medium">{t("title")}</h3>
        <Badge variant="outline" className="text-xs">JSON</Badge>
      </div>

      <div className="text-xs text-muted-foreground space-y-2">
        <p>{t("desc")}</p>
        {binaryPath && binaryPath !== 'python' && (
          <div className="flex items-start gap-2 p-2 bg-blue-50 rounded text-blue-700 border border-blue-200">
            <Info className="h-3 w-3 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <p className="font-medium">{t("sidecarBinary")}</p>
              <code className="text-xs bg-blue-100 px-1 py-0.5 rounded">{binaryPath}</code>
            </div>
          </div>
        )}
      </div>

      <Tabs defaultValue="stdio" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="stdio" className="text-xs">
            STDIO
          </TabsTrigger>
          <TabsTrigger value="http" className="text-xs">
            HTTP
          </TabsTrigger>
          <TabsTrigger value="sse" className="text-xs">
            SSE
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stdio" className="space-y-3">
          <ConfigCard
            title="STDIO Transport"
            description={t("stdioDesc")}
            config={configs.stdio}
            configType="stdio"
            badge={t("recommended")}
          />
        </TabsContent>

        <TabsContent value="http" className="space-y-3">
          <ConfigCard
            title="HTTP Transport"
            description={t("httpDesc")}
            config={configs.http}
            configType="http"
          />
        </TabsContent>

        <TabsContent value="sse" className="space-y-3">
          <ConfigCard
            title="Server-Sent Events"
            description={t("sseDesc")}
            config={configs.sse}
            configType="sse"
          />
        </TabsContent>
      </Tabs>

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <ExternalLink className="h-3 w-3" />
        <a
          href="https://modelcontextprotocol.io/docs/concepts/clients"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-foreground underline"
        >
          {t("learnMore")}
        </a>
      </div>
    </div>
  );
}