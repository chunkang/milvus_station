// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

// Modal dialog for indexing one or more MySQL table columns into Milvus.
// Fetches the table's columns, lets the user pick one or more embeddable
// columns (their values are combined into one text per row), then POSTs to
// /api/index and shows the result (toast + inline alert) or error.
import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import {
  getColumns,
  indexToMilvus,
  type ColumnInfo,
  type IndexResponse,
} from "../api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface IndexModalProps {
  database: string;
  table: string;
  onClose: () => void;
  // Called after a successful index so the caller can refresh derived state
  // (e.g. the set of existing Milvus collections).
  onIndexed?: () => void;
}

export default function IndexModal({
  database,
  table,
  onClose,
  onIndexed,
}: IndexModalProps) {
  const [columns, setColumns] = useState<ColumnInfo[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // One or more selected column names (combined into a single text per row).
  const [selected, setSelected] = useState<string[]>([]);

  const [indexing, setIndexing] = useState(false);
  const [result, setResult] = useState<IndexResponse | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);

  // Load columns on mount; pre-select the first embeddable column.
  useEffect(() => {
    let active = true;
    setColumns(null);
    setLoadError(null);
    setSelected([]);
    getColumns(database, table)
      .then((res) => {
        if (!active) return;
        setColumns(res.columns);
        const firstEmbeddable = res.columns.find((c) => c.embeddable);
        setSelected(firstEmbeddable ? [firstEmbeddable.name] : []);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setLoadError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      active = false;
    };
  }, [database, table]);

  function toggle(name: string, checked: boolean) {
    setSelected((prev) =>
      checked ? [...prev, name] : prev.filter((c) => c !== name)
    );
  }

  async function handleIndex() {
    if (selected.length === 0) return;
    setIndexing(true);
    setIndexError(null);
    setResult(null);
    try {
      const res = await indexToMilvus({ database, table, columns: selected });
      setResult(res);
      if (res.status === "ok") {
        toast.success(
          `Indexed ${res.indexed} rows (dim ${res.dim})` +
            (res.collection ? ` into ${res.collection}` : "")
        );
        onIndexed?.();
      } else {
        toast.error(res.message ?? "Indexing failed");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setIndexError(message);
      toast.error(message);
    } finally {
      setIndexing(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Index <code className="font-mono">{table}</code> to Milvus
          </DialogTitle>
          <DialogDescription>
            Select one or more embeddable columns. Their values are combined
            into a single text per row before embedding. Non-embeddable columns
            are disabled.
          </DialogDescription>
        </DialogHeader>

        {loadError && (
          <Alert variant="destructive">
            <TriangleAlert />
            <AlertTitle>Could not load columns</AlertTitle>
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
        )}

        {!columns && !loadError && (
          <div className="flex flex-col gap-2 py-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-2/3" />
          </div>
        )}

        {columns && (
          <div className="flex flex-col gap-4">
            <div
              role="group"
              aria-label="Columns to embed"
              className="flex flex-col gap-1"
            >
              {columns.map((col) => {
                const id = `col-${col.name}`;
                const checked = selected.includes(col.name);
                return (
                  <div
                    key={col.name}
                    className="flex items-center gap-3 rounded-md border border-transparent px-2 py-1.5 hover:border-border hover:bg-muted/40 has-[:checked]:border-border has-[:checked]:bg-muted/60"
                  >
                    <input
                      type="checkbox"
                      id={id}
                      className="size-4 accent-primary disabled:opacity-50"
                      checked={checked}
                      disabled={!col.embeddable}
                      onChange={(e) => toggle(col.name, e.target.checked)}
                    />
                    <Label
                      htmlFor={id}
                      className="flex flex-1 items-center justify-between gap-2 font-normal data-[disabled]:opacity-60"
                      data-disabled={!col.embeddable ? "" : undefined}
                    >
                      <span className="font-medium">{col.name}</span>
                      <span className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono">{col.type}</span>
                        {col.embeddable ? (
                          <Badge variant="secondary">embeddable</Badge>
                        ) : (
                          <span>not embeddable</span>
                        )}
                      </span>
                    </Label>
                  </div>
                );
              })}
            </div>

            {result && result.status === "ok" && (
              <Alert>
                <CheckCircle2 />
                <AlertTitle>Indexing complete</AlertTitle>
                <AlertDescription>
                  Indexed {result.indexed} rows (dim {result.dim})
                  {result.collection ? ` into ${result.collection}` : ""}.
                </AlertDescription>
              </Alert>
            )}
            {result && result.status === "error" && (
              <Alert variant="destructive">
                <TriangleAlert />
                <AlertTitle>Indexing failed</AlertTitle>
                <AlertDescription>
                  {result.message ?? "Indexing failed"}
                </AlertDescription>
              </Alert>
            )}
            {indexError && (
              <Alert variant="destructive">
                <TriangleAlert />
                <AlertTitle>Indexing failed</AlertTitle>
                <AlertDescription>{indexError}</AlertDescription>
              </Alert>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            type="button"
            onClick={handleIndex}
            disabled={indexing || selected.length === 0 || !columns}
          >
            {indexing && <Loader2 className="size-4 animate-spin" />}
            {indexing ? "Indexing…" : "Index"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
