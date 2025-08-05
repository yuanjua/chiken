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
import { Search } from "lucide-react";

interface SearchEngineConfigProps {
  searchEngine: any;
  searchEndpoint: any;
  searchApiKey: any;
  updateSearchEngineConfig: (field: string, value: any) => void;
}

export function SearchEngineConfig({
  searchEngine,
  searchEndpoint,
  searchApiKey,
  updateSearchEngineConfig,
}: SearchEngineConfigProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Search className="w-4 h-4" />
        <Label className="text-sm font-medium">
          Search Engine Configuration
        </Label>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Left side - Configuration */}
        <div className="lg:col-span-2 space-y-3">
          <div>
            <Label htmlFor="searchEngine">Search Engine</Label>
            <Select
              value={searchEngine || "searxng"}
              onValueChange={(value) =>
                updateSearchEngineConfig("searchEngine", value)
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select search engine" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="searxng">SearXNG</SelectItem>
                <SelectItem value="duckduckgo">DuckDuckGo</SelectItem>
                <SelectItem value="google">Google</SelectItem>
                <SelectItem value="bing">Bing</SelectItem>
                <SelectItem value="tavily">Tavily</SelectItem>
                <SelectItem value="serper">Serper</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="searchEndpoint">Search Endpoint</Label>
            <Input
              id="searchEndpoint"
              value={searchEndpoint || ""}
              onChange={(e) =>
                updateSearchEngineConfig("searchEndpoint", e.target.value)
              }
              placeholder="http://localhost:8080"
            />
          </div>

          <div>
            <Label htmlFor="searchApiKey">Search API Key (Optional)</Label>
            <Input
              id="searchApiKey"
              type="password"
              value={searchApiKey || ""}
              onChange={(e) =>
                updateSearchEngineConfig("searchApiKey", e.target.value)
              }
              placeholder="Enter API key if required"
            />
          </div>
        </div>

        {/* Right side - Description */}
        <div className="lg:col-span-2">
          <div className="text-sm p-3 bg-muted rounded-lg h-full flex flex-col justify-center">
            <strong className="text-foreground">Search Engine Setup</strong>
            <p className="text-muted-foreground mt-1">
              Configure your preferred search engine for web searches. SearXNG
              provides privacy-focused search, while commercial APIs like
              Google, Bing, Tavily, and Serper offer enhanced results.
            </p>
            <div className="mt-2 text-xs text-muted-foreground">
              <p>
                <strong>SearXNG:</strong> Self-hosted, privacy-focused (no API
                key needed)
              </p>
              <p>
                <strong>Google/Bing:</strong> High-quality results (API key
                required)
              </p>
              <p>
                <strong>Tavily/Serper:</strong> AI-optimized search APIs
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
