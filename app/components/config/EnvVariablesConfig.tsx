"use client";

import { useEffect, useState } from "react";
// Frontend loads and persists environment variables via Tauri keychain only
import * as secretStore from "@/lib/secret-store";
import { reloadBackendConfig } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Minus, Plus, Key, Eye, EyeOff } from "lucide-react";
import { EnvVarInfoCard } from "./EnvVarInfoCard";
import { useTranslations } from "next-intl";

type EditableVar = {
  name: string;
  value: string;
  description?: string;
  present?: boolean;
};

export function EnvVariablesConfig() {
  const t = useTranslations("EnvVars");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<(EditableVar & { originalName?: string })[]>([]);
  const [newName, setNewName] = useState("");
  const [newValue, setNewValue] = useState("");
  const [recommendedVars, setRecommendedVars] = useState<{ name: string; description?: string }[]>([]);
  const [showValues, setShowValues] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        // Recommended variables (local, no backend dependency)
        const recommended = [
          { name: "OPENAI_API_KEY", description: t("descOpenAI") },
          { name: "ANTHROPIC_API_KEY", description: t("descAnthropic") },
          { name: "AZURE_API_KEY", description: t("descAzure") },
          { name: "REPLICATE_API_KEY", description: t("descReplicate") },
          { name: "COHERE_API_KEY", description: t("descCohere") },
          { name: "OPENROUTER_API_KEY", description: t("descOpenRouter") },
          { name: "TOGETHERAI_API_KEY", description: t("descTogether") },
          { name: "HF_TOKEN", description: t("descHF") },
          { name: "OPENAI_BASE_URL", description: t("descOpenAIBase") },
          { name: "OLLAMA_API_BASE", description: t("descOllamaBase") },
          { name: "ACADEMIC_MAILTO", description: t("descAcademicMailto") },
          { name: "SEMANTIC_SCHOLAR_API_KEY", description: t("descS2") },
          { name: "NCBI_API_KEY", description: t("descNCBI") },
          { name: "HOSTED_VLLM_API_KEY", description: t("descHostedVLLM") }
        ];

        const recMap = new Map<string, string | undefined>();
        for (const r of recommended) recMap.set(r.name, r.description);

        // Load stored variables from keychain only
        const storedDict = await secretStore.getEnvVars();
        const storedNames = Object.keys(storedDict);
        const allVarNames = new Set([...recommended.map(r => r.name), ...storedNames]);

        const finalUnified: (EditableVar & { originalName?: string })[] = [];
        for (const varName of allVarNames) {
          const description = recMap.get(varName);
          const isStored = storedNames.includes(varName);
          const actualValue = isStored ? storedDict[varName] || "" : "";
          finalUnified.push({ name: varName, value: actualValue, description, present: isStored, originalName: varName });
        }

        setItems(finalUnified.filter(it => !!it.present));
        setRecommendedVars(recommended);
      } catch (e: any) {
        setError(e?.message || String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const persistValue = async (name: string, value: string) => {
    try {
      // Persist to keychain JSON
      await secretStore.setEnvVar(name, value);
      
      // Trigger backend reload to sync os.environ immediately
      try {
        await reloadBackendConfig();
      } catch (e) {
        console.warn('Failed to trigger backend env reload after persistValue:', e);
      }
      
      // Update local state to show the var is present
      setItems((prev) => {
        const exists = prev.some((p) => p.name === name);
        if (exists) {
          return prev.map((p) => p.name === name ? { ...p, present: true, value } : p);
        } else {
          const desc = recommendedVars.find(r => r.name === name)?.description;
          return [...prev, { name, value: "", present: true, description: desc, originalName: name }];
        }
      });
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  // Renaming disabled: names are immutable after saved

  const updateValue = (name: string, value: string) => {
    setItems((prev) => prev.map(it => it.name === name ? { ...it, value } : it));
  };

  const onRemoveByName = async (name: string) => {
    setItems((prev) => prev.filter((it) => it.name !== name));
    if (name) {
      // Remove locally
      try {
        await secretStore.deleteEnvVar(name);
        
        // Trigger backend reload to sync os.environ immediately
        try {
          await reloadBackendConfig();
        } catch (e) {
          console.warn('Failed to trigger backend env reload after delete:', e);
        }
      } catch {}
      // Refresh from keychain
      try {
        const storedDict = await secretStore.getEnvVars();
        const storedNames = Object.keys(storedDict);
        const finalUnified: (EditableVar & { originalName?: string })[] = [];
        const allVarNames = new Set([...
          recommendedVars.map(r => r.name),
          ...storedNames
        ]);
        for (const varName of allVarNames) {
          const description = recommendedVars.find(r => r.name === varName)?.description;
          const isStored = storedNames.includes(varName);
          finalUnified.push({ name: varName, value: "", description, present: isStored, originalName: varName });
        }
        setItems(finalUnified.filter(it => !!it.present));
      } catch (e: any) {
        setError(e?.message || String(e));
      }
    }
  };

  const addNew = async () => {
    const name = newName.trim().toUpperCase();
    if (!name) return;
    setSaving(true);
    try {
      if (newValue && newValue.trim()) {
        // Save to keychain JSON
        await secretStore.setEnvVar(name, newValue);
        
        // Trigger backend reload to sync os.environ immediately  
        try {
          await reloadBackendConfig();
        } catch (e) {
          console.warn('Failed to trigger backend env reload after add:', e);
        }
        
        // Update local state to show the var is present
        const desc = recommendedVars.find(r => r.name === name)?.description;
        setItems((prev) => [...prev, { name, value: newValue, description: desc, present: true, originalName: name }]);
      }
      setNewName("");
      setNewValue("");
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Key className="h-4 w-4" />
          <Label className="text-sm font-medium"> {t("title")} </Label>
          <EnvVarInfoCard
            envVars={recommendedVars}
            title={t("recommended")}
            compact={true}
          />
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowValues(!showValues)}
          className="h-6 px-2 text-xs"
        >
          {showValues ? (
            <>
              <EyeOff className="h-3 w-3 mr-1" />
              Hide
            </>
          ) : (
            <>
              <Eye className="h-3 w-3 mr-1" />
              Show
            </>
          )}
        </Button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="border rounded-md overflow-hidden">
        {/* Floating header outside the scroll area with solid background */}
        <div className="bg-card border-b px-0">
          <table className="w-full text-xs table-fixed">
            <colgroup>
              <col style={{ width: '45%' }} />
              <col style={{ width: '45%' }} />
              <col style={{ width: '10%' }} />
            </colgroup>
            <thead>
              <tr className="bg-card">
                <th className="text-left px-3 py-1.5">Name</th>
                <th className="text-left px-3 py-1.5">Value</th>
                <th className="text-right px-3 py-1.5">Actions</th>
              </tr>
            </thead>
          </table>
        </div>

        {/* Scrollable body without header */}
        <div className="max-h-64 overflow-auto">
          <table className="w-full text-xs table-fixed">
            <colgroup>
              <col style={{ width: '45%' }} />
              <col style={{ width: '45%' }} />
              <col style={{ width: '10%' }} />
            </colgroup>
            <tbody>
              {[...items].filter((it) => !!it.present)
                .sort((a, b) => Number(!!b.present) - Number(!!a.present) || a.name.localeCompare(b.name))
                .map((it) => (
                <tr key={it.name} className="border-b">
                  <td className="px-2 py-1 align-middle" title={it.description || ''}>
                    <div className="font-mono text-xs h-8 px-2 w-full bg-muted text-muted-foreground rounded-none flex items-center">
                      {it.name}
                    </div>
                  </td>
                  <td className="px-2 py-1 align-middle">
                    <Input
                      placeholder={it.value ? (showValues ? "Enter value" : "****** (click to edit)") : "Enter value"}
                      value={it.value}
                      onChange={(e) => updateValue(it.name, e.target.value)}
                      onBlur={(e) => persistValue(it.name, e.currentTarget.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
                      className="font-mono text-xs h-8 px-2 w-full bg-muted text-foreground placeholder:text-muted-foreground border border-transparent focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none rounded-none"
                      type={showValues ? "text" : "password"}
                    />
                  </td>
                  <td className="px-2 py-1 align-middle">
                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        onClick={() => onRemoveByName(it.name)}
                        aria-label="Remove variable"
                        title="Remove"
                      >
                        <Minus className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {/* New variable row */}
              <tr className="bg-transparent">
                <td className="px-2 py-1 align-middle">
                  <Input
                    placeholder="NAME"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value.toUpperCase())}
                    className="font-mono text-xs h-8 px-2 w-full bg-muted text-muted-foreground placeholder:text-muted-foreground border border-transparent focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none rounded-none"
                  />
                </td>
                <td className="px-2 py-1 align-middle">
                  <Input
                    placeholder="value"
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    className="font-mono text-xs h-8 px-2 w-full bg-muted text-foreground placeholder:text-muted-foreground border border-transparent focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none rounded-none"
                    type="text"
                  />
                </td>
                <td className="px-2 py-1 align-middle">
                  <div className="flex justify-end">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={addNew}
                      aria-label="Add variable"
                      title="Add"
                      disabled={!newName.trim()}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Removed external Add/Save buttons; use plus on last row */}

      <Separator />
    </div>
  );
}


