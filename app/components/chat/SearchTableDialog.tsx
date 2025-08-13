"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toCsv, toMarkdown } from "@/lib/dom-table";
import { toast } from "@/hooks/use-toast";
import { Checkbox } from "@/components/ui/checkbox";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  headers: string[];
  records: Array<Record<string, string>>;
};

export function SearchTableDialog({ open, onOpenChange, headers, records }: Props) {
  const [selected, setSelected] = useState<boolean[]>([]);
  const [threshold, setThreshold] = useState<number>(7);

  useEffect(() => {
    // Initialize selection by threshold
    const relevanceKey = headers.find((h) => /relevance/i.test(h));
    const getRel = (rec: Record<string, string>) => {
      const raw = relevanceKey ? rec[relevanceKey] : undefined;
      const num = parseFloat(String(raw ?? ""));
      return isNaN(num) ? 0 : num;
    };
    setSelected(records.map((r) => getRel(r) >= threshold));
  }, [records, headers, threshold]);

  const selectedRecords = useMemo(
    () => records.filter((_, idx) => selected[idx]),
    [records, selected]
  );

  const handleCopyMarkdown = async () => {
    const md = toMarkdown(headers, selectedRecords);
    await (globalThis as any).navigator?.clipboard?.writeText(md);
    toast({ title: "Copied", description: "Table copied as Markdown" });
  };
  const handleCopyCsv = async () => {
    const csv = toCsv(headers, selectedRecords);
    await (globalThis as any).navigator?.clipboard?.writeText(csv);
    toast({ title: "Copied", description: "Table copied as CSV" });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export Table</DialogTitle>
        </DialogHeader>
        <div className="max-h-[68vh] w-full overflow-auto border border-gray-300 dark:border-gray-500 rounded mb-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/40">
                <th className="p-2 w-8"></th>
                <th className="p-2 text-left">Title</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec, idx) => (
                <tr key={idx} className="border-t border-gray-100 dark:border-gray-700">
                  <td className="p-2 align-top">
                    <Checkbox
                      checked={selected[idx] || false}
                      onCheckedChange={(v) => {
                        const next = [...selected];
                        next[idx] = Boolean(v);
                        setSelected(next);
                      }}
                    />
                  </td>
                  <td className="p-2">
                    <div className="line-clamp-2">
                      {rec[headers[0]] || rec["Title"] || Object.values(rec)[0] || "Untitled"}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-3 mb-2">
          <label className="text-sm text-muted-foreground">Relevance ≥</label>
          <input
            type="number"
            className="w-16 border rounded px-2 py-1 text-sm bg-transparent"
            min={0}
            max={10}
            step={1}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
          />
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={handleCopyMarkdown}>Copy Markdown</Button>
          <Button variant="secondary" size="sm" onClick={handleCopyCsv}>Copy CSV</Button>
          <Button variant="secondary" size="sm" onClick={() => toast({ title: "In development", description: "Add to Zotero collection feature coming soon" })}>Add to Zotero collection</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}


