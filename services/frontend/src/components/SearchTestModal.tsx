// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

// Modal dialog for running a semantic-search test against a Milvus collection.
// Takes a query (+ optional top_k), POSTs to /api/milvus/collections/{name}/search,
// and renders the ranked results (toast + inline alert on error).
import { useState } from "react";
import { Loader2, Search, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { searchCollection, type SearchResponse } from "../api";
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

interface SearchTestModalProps {
  collection: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
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

  async function runTest() {
    const trimmed = query.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setError(null);
    setResponse(null);
    try {
      const res = await searchCollection(collection, trimmed, topK);
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
                          <p className="break-words text-sm">{r.text}</p>
                          <p className="text-xs text-muted-foreground">
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
