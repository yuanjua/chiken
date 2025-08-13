"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea, ScrollAreaViewport } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Settings,
  Loader2,
  MonitorCog,
  XCircle,
  RefreshCw,
  Circle,
  Copy,
  Check,
  FileCode,
} from "lucide-react";
import {
  getMCPConfig,
  updateMCPConfig,
  restartMCPServer,
  getMCPStatus,
} from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { generateMCPConfig, formatMCPConfigJSON } from "@/lib/mcp-utils";

interface MCPConfigDialogProps {
  children?: React.ReactNode;
}

export function MCPConfigDialog({ children }: MCPConfigDialogProps) {
  const [open, setOpen] = useState(false);
  const [transport, setTransport] = useState("stdio");
  const [port, setPort] = useState(8000);
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [mcpStatus, setMcpStatus] = useState<{ is_running: boolean } | null>(
    null,
  );
  const [configJSON, setConfigJSON] = useState<string>("");
  const [isCopied, setIsCopied] = useState(false);
  const { toast } = useToast();

  // Load current configuration when dialog opens
  useEffect(() => {
    if (open) {
      loadConfig();
    }
  }, [open]);

  // Update JSON config when transport or port changes
  useEffect(() => {
    const updateConfigJSON = async () => {
      try {
        // Map frontend transport names to backend names
        let backendTransportType: string;
        switch (transport) {
          case 'streamable-http':
            backendTransportType = 'streamableHttp';
            break;
          case 'sse':
            backendTransportType = 'sse';
            break;
          default:
            backendTransportType = 'stdio';
            break;
        }
        
        const config = await generateMCPConfig({
          type: backendTransportType as 'stdio' | 'streamableHttp' | 'sse',
          port: transport === "stdio" ? undefined : port,
        });
        setConfigJSON(formatMCPConfigJSON(config));
      } catch (error) {
        console.error("Failed to generate MCP config JSON:", error);
      }
    };

    updateConfigJSON();
  }, [transport, port]);

  const loadConfig = async () => {
    try {
      setIsLoading(true);
      const [config, status] = await Promise.all([
        getMCPConfig(),
        getMCPStatus(),
      ]);
      
      // Map backend transport names to frontend names
      let frontendTransportType: string;
      switch (config.transport) {
        case 'streamableHttp':
          frontendTransportType = 'streamable-http';
          break;
        case 'sse':
          frontendTransportType = 'sse';
          break;
        default:
          frontendTransportType = 'stdio';
          break;
      }
      
      setTransport(frontendTransportType);
      setPort(config.port || 8000);
      setMcpStatus(status);
    } catch (error) {
      console.error("Failed to load MCP config:", error);
      toast({
        title: "Error",
        description: "Failed to load MCP configuration",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveAndRestart = async () => {
    try {
      setIsProcessing(true);

      // Map frontend transport names to backend names
      let backendTransportType: string;
      switch (transport) {
        case 'streamable-http':
          backendTransportType = 'streamableHttp';
          break;
        case 'sse':
          backendTransportType = 'sse';
          break;
        default:
          backendTransportType = 'stdio';
          break;
      }

      // First save the configuration
      await updateMCPConfig({
        transport: backendTransportType,
        port: transport === "stdio" ? undefined : port,
      });

      // Then restart the server
      await restartMCPServer();

      // Update status
      const status = await getMCPStatus();
      setMcpStatus(status);

      toast({
        title: "Success",
        description:
          "MCP configuration saved and server restarted successfully",
      });
    } catch (error) {
      console.error("Failed to save and restart MCP server:", error);
      toast({
        title: "Error",
        description: "Failed to save configuration and restart MCP server",
        variant: "destructive",
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCopyJSON = async () => {
    try {
      // Only run in browser
      const nav = (globalThis as any).navigator;
      if (nav && nav.clipboard) {
        await nav.clipboard.writeText(configJSON);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
        toast({
          title: "Copied",
          description: "MCP configuration copied to clipboard",
        });
      } else {
        throw new Error("Clipboard API not available");
      }
    } catch (error) {
      console.error("Failed to copy to clipboard:", error);
      toast({
        title: "Error",
        description: "Failed to copy configuration to clipboard",
        variant: "destructive",
      });
    }
  };

  const requiresPort = transport === "streamable-http" || transport === "sse";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button variant="ghost" size="sm">
            <Settings className="h-4 w-4" />
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] flex flex-col pl-10">
        <DialogHeader>
          <DialogTitle>MCP Server Configuration</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="ml-2">Loading configuration...</span>
          </div>
        ) : (
          <ScrollArea className="flex-1 min-h-0 max-w-full overflow-y-auto">
            <ScrollAreaViewport>
              <div className="space-y-2 p-1 max-w-130">
                {/* MCP Status */}
                {mcpStatus && transport !== 'stdio' && (
                  <div className="flex items-center gap-2 p-2 bg-muted rounded">
                    <Circle
                      className={`h-2 w-2 ${mcpStatus.is_running ? "fill-green-500 text-green-500" : "fill-red-500 text-red-500"}`}
                    />
                    <span className="text-sm">
                      MCP Server: {mcpStatus.is_running ? "Running" : "Stopped"}
                    </span>
                  </div>
                )}

                {/* Configuration Settings */}
                <div className="space-y-4">
                  <h3 className="text-sm font-medium">Server Settings</h3>
                  
                  {/* Transport Type */}
                  <div className="space-y-2">
                    <Label htmlFor="transport">Transport Type</Label>
                    <Select value={transport} onValueChange={setTransport}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select transport type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="stdio">stdio</SelectItem>
                        <SelectItem value="streamable-http">
                          streamable-http
                        </SelectItem>
                        <SelectItem value="sse">sse</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Port (only for HTTP and SSE) */}
                  {requiresPort && (
                    <div className="space-y-2">
                      <Label htmlFor="port">Port</Label>
                      <Input
                        id="port"
                        type="number"
                        value={port}
                        onChange={(e) => setPort(parseInt(e.target.value) || 8000)}
                        placeholder="8000"
                        min="1"
                        max="65535"
                      />
                    </div>
                  )}
                </div>

                <Separator />

                {/* JSON Configuration */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileCode className="h-4 w-4" />
                      <h3 className="text-sm font-medium">MCP Client Configuration</h3>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCopyJSON}
                      className="h-8 px-2"
                    >
                      {isCopied ? (
                        <>
                          <Check className="h-4 w-4 mr-1 text-green-600" />
                          <span className="text-xs text-green-600">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4 mr-1" />
                          <span className="text-xs">Copy JSON</span>
                        </>
                      )}
                    </Button>
                  </div>
                  
                  <div className="text-xs text-muted-foreground">
                    Copy this configuration for use in MCP clients (Claude Desktop, IDEs, etc.)
                  </div>

                  <div className="rounded-lg bg-muted/30 border">
                    <ScrollArea className="h-48 w-full">
                      <ScrollAreaViewport>
                        <pre className="p-3 text-xs font-mono overflow-auto max-w-full">
                          <code className="text-foreground">{configJSON}</code>
                        </pre>
                      </ScrollAreaViewport>
                    </ScrollArea>
                  </div>
                </div>

                {/* Action Button - Show for all transport types */}
                <div className="flex justify-end pt-4">
                  <Button
                    onClick={handleSaveAndRestart}
                    disabled={isProcessing}
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Save and Restart MCP Server
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </ScrollAreaViewport>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
