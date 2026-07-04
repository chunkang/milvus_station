// Modal dialog for indexing a MySQL table column into Milvus.
// Fetches the table's columns, lets the user pick an embeddable column,
// then POSTs to /api/index and shows the result (toast + inline alert) or error.
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface IndexModalProps {
  database: string;
  table: string;
  onClose: () => void;
}

export default function IndexModal({
  database,
  table,
  onClose,
}: IndexModalProps) {
  const [columns, setColumns] = useState<ColumnInfo[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const [indexing, setIndexing] = useState(false);
  const [result, setResult] = useState<IndexResponse | null>(null);
  const [indexError, setIndexError] = useState<string | null>(null);

  // Load columns on mount.
  useEffect(() => {
    let active = true;
    setColumns(null);
    setLoadError(null);
    getColumns(database, table)
      .then((res) => {
        if (!active) return;
        setColumns(res.columns);
        const firstEmbeddable = res.columns.find((c) => c.embeddable);
        setSelected(firstEmbeddable ? firstEmbeddable.name : null);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setLoadError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      active = false;
    };
  }, [database, table]);

  async function handleIndex() {
    if (!selected) return;
    setIndexing(true);
    setIndexError(null);
    setResult(null);
    try {
      const res = await indexToMilvus({ database, table, column: selected });
      setResult(res);
      if (res.status === "ok") {
        toast.success(
          `Indexed ${res.indexed} rows (dim ${res.dim})` +
            (res.collection ? ` into ${res.collection}` : "")
        );
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
            Select an embeddable column to index. Non-embeddable columns are
            disabled.
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
            <RadioGroup
              value={selected ?? ""}
              onValueChange={setSelected}
              className="gap-1"
            >
              {columns.map((col) => {
                const id = `col-${col.name}`;
                return (
                  <div
                    key={col.name}
                    className="flex items-center gap-3 rounded-md border border-transparent px-2 py-1.5 hover:border-border hover:bg-muted/40 has-[:checked]:border-border has-[:checked]:bg-muted/60"
                  >
                    <RadioGroupItem
                      id={id}
                      value={col.name}
                      disabled={!col.embeddable}
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
            </RadioGroup>

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
            disabled={indexing || !selected || !columns}
          >
            {indexing && <Loader2 className="size-4 animate-spin" />}
            {indexing ? "Indexing…" : "Index"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
