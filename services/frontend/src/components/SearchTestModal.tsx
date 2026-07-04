// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

// Modal dialog for running a semantic-search test against a Milvus collection.
// Takes a query (+ optional top_k) plus optional numeric range filters, POSTs to
// /api/milvus/collections/{name}/search, and renders the ranked results
// (toast + inline alert on error).
import { useEffect, useState } from "react";
import { Loader2, Plus, Search, TriangleAlert, X } from "lucide-react";
import { toast } from "sonner";
import {
  getFilterFields,
  searchCollection,
  type FilterField,
  type SearchFilter,
  type SearchResponse,
} from "../api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SearchTestModalProps {
  collection: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Operator options shown to the user, mapped to the op values the backend expects.
const OPERATORS: { value: string; label: string }[] = [
  { value: "lt", label: "<" },
  { value: "lte", label: "<=" },
  { value: "eq", label: "=" },
  { value: "gte", label: ">=" },
  { value: "gt", label: ">" },
  { value: "ne", label: "!=" },
];

// A single filter row in the UI. `value` is kept as a raw string while editing
// and coerced to a number only when the search is submitted.
interface FilterRow {
  field: string;
  op: string;
  value: string;
}

function newRow(field: string): FilterRow {
  return { field, op: "gte", value: "" };
}

// Render a single source value as a tidy string, truncating long text so the
// results list stays compact.
function formatSourceValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  const str =
    typeof value === "object" ? JSON.stringify(value) : String(value);
  const MAX = 120;
  return str.length > MAX ? `${str.slice(0, MAX)}…` : str;
}

export default function SearchTestModal({
  collection,
  open,
  onOpenChange,
}: SearchTestModalProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<FilterField[]>([]);
  const [rows, setRows] = useState<FilterRow[]>([]);

  // Load the numeric fields available for filtering whenever the dialog opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setRows([]);
    // Wrapped in Promise.resolve so a missing/empty response never throws.
    Promise.resolve(getFilterFields(collection))
      .then((res) => {
        if (cancelled) return;
        // Missing body, status:"unreachable", or an empty list => no filters.
        if (!res || res.status === "unreachable") {
          setFields([]);
          return;
        }
        setFields(res.fields ?? []);
      })
      .catch(() => {
        if (!cancelled) setFields([]);
      });
    return () => {
      cancelled = true;
    };
  }, [collection, open]);

  function addRow() {
    if (fields.length === 0) return;
    setRows((prev) => [...prev, newRow(fields[0].name)]);
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  function updateRow(index: number, patch: Partial<FilterRow>) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, ...patch } : row))
    );
  }

  function collectFilters(): SearchFilter[] {
    return rows
      .filter((row) => row.value.trim() !== "" && row.field)
      .map((row) => ({
        field: row.field,
        op: row.op,
        value: Number(row.value),
      }));
  }

  async function runTest() {
    const trimmed = query.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setError(null);
    setResponse(null);
    try {
      const filters = collectFilters();
      const res = await searchCollection(
        collection,
        trimmed,
        topK,
        filters.length ? filters : undefined
      );
      if (res.status === "error") {
        const message = res.message ?? "Search failed";
        setError(message);
        toast.error(message);
        return;
      }
      setResponse(res);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      toast.error(message);
    } finally {
      setRunning(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    runTest();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Search test on <code className="font-mono">{collection}</code>
          </DialogTitle>
          <DialogDescription>
            Run a semantic-search query against this collection and inspect the
            ranked matches.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="search-query">Query text</Label>
            <Input
              id="search-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. how do I reset my password?"
              autoFocus
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="search-topk">Top K</Label>
            <Input
              id="search-topk"
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Math.max(1, Number(e.target.value) || 1))}
              className="w-24"
            />
          </div>

          {fields.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <Label>Filters</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addRow}
                >
                  <Plus className="size-4" />
                  Add filter
                </Button>
              </div>

              {rows.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Optionally narrow results by numeric field.
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {rows.map((row, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <Select
                        value={row.field}
                        onValueChange={(value) => updateRow(i, { field: value })}
                      >
                        <SelectTrigger
                          aria-label="Filter field"
                          className="w-32"
                        >
                          <SelectValue placeholder="Field" />
                        </SelectTrigger>
                        <SelectContent>
                          {fields.map((f) => (
                            <SelectItem key={f.name} value={f.name}>
                              {f.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Select
                        value={row.op}
                        onValueChange={(value) => updateRow(i, { op: value })}
                      >
                        <SelectTrigger
                          aria-label="Filter operator"
                          className="w-20"
                        >
                          <SelectValue placeholder="Op" />
                        </SelectTrigger>
                        <SelectContent>
                          {OPERATORS.map((op) => (
                            <SelectItem key={op.value} value={op.value}>
                              {op.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Input
                        type="number"
                        aria-label="Filter value"
                        value={row.value}
                        onChange={(e) => updateRow(i, { value: e.target.value })}
                        placeholder="value"
                        className="flex-1"
                      />

                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="Remove filter"
                        onClick={() => removeRow(i)}
                      >
                        <X className="size-4" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <TriangleAlert />
              <AlertTitle>Search failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {response && (
            <div className="flex flex-col gap-2">
              {response.results.length === 0 ? (
                <p className="text-sm italic text-muted-foreground">
                  No matches
                </p>
              ) : (
                <ol className="flex flex-col gap-2">
                  {response.results.map((r, i) => (
                    <li
                      key={r.pk}
                      className="flex items-start justify-between gap-3 rounded-md border px-3 py-2"
                    >
                      <div className="flex min-w-0 items-start gap-2">
                        <span className="text-sm font-medium text-muted-foreground">
                          #{i + 1}
                        </span>
                        <div className="min-w-0">
                          {r.source && Object.keys(r.source).length > 0 ? (
                            <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-sm">
                              {Object.entries(r.source).map(([key, value]) => (
                                <div
                                  key={key}
                                  className="contents"
                                >
                                  <dt className="font-medium text-muted-foreground">
                                    {key}
                                  </dt>
                                  <dd className="min-w-0 break-words">
                                    {formatSourceValue(value)}
                                  </dd>
                                </div>
                              ))}
                            </dl>
                          ) : (
                            <p className="break-words text-sm">{r.text}</p>
                          )}
                          <p className="mt-1 text-xs text-muted-foreground">
                            pk {r.pk}
                          </p>
                        </div>
                      </div>
                      <Badge variant="secondary" className="shrink-0 font-mono">
                        {r.score.toFixed(4)}
                      </Badge>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Close
            </Button>
            <Button type="submit" disabled={running || !query.trim()}>
              {running && <Loader2 className="size-4 animate-spin" />}
              {!running && <Search className="size-4" />}
              {running ? "Running…" : "Run test"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
