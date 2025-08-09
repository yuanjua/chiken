// Tauri-independent helpers to extract a rendered HTML table and save CSV

export type CsvExtraction = {
  headers: string[];
  records: Array<Record<string, string>>;
  csv: string;
};

export type SaveMode = "tauri_v2" | "web" | "none";

export function findFirstTable(container: Element | null): HTMLTableElement | null {
  if (!container) return null;
  const table = container.querySelector("table");
  return (table as HTMLTableElement) || null;
}
// New: find all tables in a container
export function findAllTables(container: Element | null): HTMLTableElement[] {
  if (!container) return [];
  return Array.from(container.querySelectorAll("table")) as HTMLTableElement[];
}

export function extractTableToCsv(tableEl: HTMLTableElement): CsvExtraction {
  const extractCell = (cell: HTMLTableCellElement): string => {
    const link = cell.querySelector<HTMLAnchorElement>("a[href]");
    if (link && link.getAttribute("href")) return link.getAttribute("href") || "";
    return (cell.textContent || "").trim();
  };

  let headers: string[] = [];
  const thead = (tableEl.tHead as HTMLTableSectionElement | null) || null;
  if (thead && thead.rows && thead.rows.length > 0) {
    const headerRow = thead.rows.item(0) as HTMLTableRowElement | null;
    const headerCellsEls = headerRow ? Array.from(headerRow.cells) : [];
    headers = headerCellsEls
      .map((c) => extractCell(c as HTMLTableCellElement))
      .filter((v) => !!v);
  }

  const tBodies = tableEl.tBodies as HTMLCollectionOf<HTMLTableSectionElement> | undefined;
  const bodyRows: HTMLTableRowElement[] = tBodies && tBodies.length > 0 ? (Array.from(tBodies[0].rows) as unknown as HTMLTableRowElement[]) : [];

  if (headers.length === 0 && bodyRows.length > 0) {
    headers = Array.from(bodyRows[0].cells).map((_, i) => `Col${i + 1}`);
  }

  const records: Array<Record<string, string>> = [];
  for (let r = 0; r < bodyRows.length; r++) {
    const tr = bodyRows[r] as HTMLTableRowElement;
    const cells = Array.from(tr.cells).map((c) => extractCell(c as HTMLTableCellElement));
    const rec: Record<string, string> = {};
    for (let i = 0; i < headers.length; i++) {
      rec[headers[i]] = cells[i] ?? "";
    }
    records.push(rec);
  }

  const csvBody = records
    .map((rec) =>
      headers
        .map((h) => {
          let cell: any = rec[h] ?? "";
          if (typeof cell === "string") cell = '"' + cell.replace(/"/g, '""') + '"';
          return cell;
        })
        .join(","),
    )
    .join("\n");
  const csv = [headers.join(","), csvBody].join("\n");

  return { headers, records, csv };
}

// New: extract as structured headers+records without csv string
export function extractTableToData(tableEl: HTMLTableElement): { headers: string[]; records: Array<Record<string, string>> } {
  const { headers, records } = extractTableToCsv(tableEl);
  return { headers, records };
}

// New: helpers to render to CSV/Markdown from structured data
export function toCsv(headers: string[], records: Array<Record<string, string>>): string {
  const csvBody = records
    .map((rec) =>
      headers
        .map((h) => {
          let cell: any = rec[h] ?? "";
          if (typeof cell === "string") cell = '"' + cell.replace(/"/g, '""') + '"';
          return cell;
        })
        .join(","),
    )
    .join("\n");
  return [headers.join(","), csvBody].join("\n");
}

export function toMarkdown(headers: string[], records: Array<Record<string, string>>): string {
  const escape = (s: string = "") => s.replace(/\|/g, "\\|").replace(/\n/g, " ").trim();
  const headerLine = `| ${headers.map(escape).join(" | ")} |`;
  const sepLine = `| ${headers.map(() => "---").join(" | ")} |`;
  const bodyLines = records.map((rec) => `| ${headers.map((h) => escape(String(rec[h] ?? ""))).join(" | ")} |`);
  return [headerLine, sepLine, ...bodyLines].join("\n");
}

function downloadCsvInBrowser(filename: string, csvContent: string): void {
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const doc = (globalThis as any)?.document as Document | undefined;
  if (!doc) return;
  const link = doc.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", filename);
  if (!doc.body) return;
  doc.body.appendChild(link);
  link.click();
  if (doc.body) doc.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export async function saveRenderedTableCsv(
  container: Element,
  defaultFilename: string = `search-results-${Date.now()}.csv`
): Promise<SaveMode> {
  const table = findFirstTable(container);
  if (!table) return "none";
  const { csv } = extractTableToCsv(table);

  // Detect Tauri environment
  const isTauri = typeof globalThis !== "undefined" && (
    !!(globalThis as any).__TAURI__ || ((globalThis as any).window && "__TAURI_INTERNALS__" in (globalThis as any).window)
  );

  if (isTauri) {
    try {
      // Use Tauri v2 plugins only
      const dynImport = new Function("s", "return import(s)") as (s: string) => Promise<any>;
      const dialogV2: any = await dynImport("@tauri-apps/plugin-dialog");
      const fsV2: any = await dynImport("@tauri-apps/plugin-fs");
      if (dialogV2 && fsV2 && dialogV2.save && fsV2.writeTextFile) {
        const selected = await dialogV2.save({
          defaultPath: defaultFilename,
          title: "Save CSV",
          filters: [{ name: "CSV", extensions: ["csv"] }],
        });
        if (!selected) return "none"; // user cancelled
        await fsV2.writeTextFile(selected as string, csv);
        return "tauri_v2";
      }
    } catch {
      // fall through to web download
    }
  }

  // Web fallback: trigger browser download
  downloadCsvInBrowser(defaultFilename, csv);
  return "web";
}


