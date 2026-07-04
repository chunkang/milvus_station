// Milvus view: list collections -> browse a collection's entities.
import { useEffect, useState } from "react";
import { Layers, TriangleAlert, WifiOff } from "lucide-react";
import {
  getCollections,
  getCollectionData,
  type CollectionInfo,
  type CollectionDataResponse,
} from "../api";
import DataTable from "../components/DataTable";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

const PAGE_SIZE = 25;

function ErrorAlert({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <TriangleAlert />
      <AlertTitle>Something went wrong</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

export default function MilvusView() {
  const [collections, setCollections] = useState<CollectionInfo[] | null>(null);
  const [unreachable, setUnreachable] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);

  const [data, setData] = useState<CollectionDataResponse | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataUnreachable, setDataUnreachable] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let live = true;
    getCollections()
      .then((res) => {
        if (!live) return;
        if (res.status === "unreachable") {
          setUnreachable(true);
          setCollections([]);
        } else {
          setCollections(res.collections);
        }
      })
      .catch(
        (err: unknown) =>
          live && setListError(err instanceof Error ? err.message : String(err))
      );
    return () => {
      live = false;
    };
  }, []);

  function loadData(name: string, nextPage: number) {
    setDataLoading(true);
    setDataError(null);
    setDataUnreachable(false);
    getCollectionData(name, nextPage, PAGE_SIZE)
      .then((res) => {
        if (res.status === "unreachable") {
          setDataUnreachable(true);
          setData(null);
          return;
        }
        setData(res);
        setPage(res.page);
      })
      .catch((err: unknown) =>
        setDataError(err instanceof Error ? err.message : String(err))
      )
      .finally(() => setDataLoading(false));
  }

  function selectCollection(name: string) {
    setActive(name);
    setData(null);
    setPage(1);
    loadData(name, 1);
  }

  function changePage(nextPage: number) {
    if (active) loadData(active, nextPage);
  }

  // Convert array-of-objects rows into positional arrays aligned with fields.
  const tableRows: unknown[][] = data
    ? data.rows.map((row) => data.fields.map((f) => row[f]))
    : [];

  return (
    <section aria-label="Milvus" className="mx-auto max-w-6xl px-4 pb-16">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Layers className="size-6 text-muted-foreground" />
          Milvus
        </h1>
        <p className="text-sm text-muted-foreground">
          Inspect vector collections and page through their stored entities.
        </p>
      </div>

      {unreachable && (
        <Alert variant="destructive" className="mb-4">
          <WifiOff />
          <AlertTitle>Milvus not reachable</AlertTitle>
          <AlertDescription>
            Please check the Milvus service and try again.
          </AlertDescription>
        </Alert>
      )}
      {listError && (
        <div className="mb-4">
          <ErrorAlert message={listError} />
        </div>
      )}
      {!collections && !listError && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      )}

      {collections && !unreachable && (
        <>
          {collections.length === 0 ? (
            <p className="text-sm italic text-muted-foreground">
              No collections
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {collections.map((c) => (
                <Card
                  key={c.name}
                  className={
                    active === c.name
                      ? "border-primary/60 ring-1 ring-primary/30"
                      : ""
                  }
                >
                  <CardContent className="flex items-center justify-between gap-2 py-4">
                    <Button
                      type="button"
                      variant="link"
                      className="h-auto p-0 text-base font-medium"
                      onClick={() => selectCollection(c.name)}
                    >
                      <Layers className="size-4 text-muted-foreground" />
                      {c.name}
                    </Button>
                    <Badge variant="secondary">{c.count} entities</Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {active && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-base">{active}</CardTitle>
          </CardHeader>
          <CardContent>
            {dataUnreachable && (
              <Alert variant="destructive">
                <WifiOff />
                <AlertTitle>Milvus not reachable</AlertTitle>
                <AlertDescription>
                  Milvus not reachable while loading this collection.
                </AlertDescription>
              </Alert>
            )}
            {dataError && <ErrorAlert message={dataError} />}
            {dataLoading && !data && (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            )}
            {data && (
              <DataTable
                columns={data.fields}
                rows={tableRows}
                page={page}
                pageSize={data.page_size}
                total={data.total}
                onPageChange={changePage}
                emptyMessage="No entities in this collection"
              />
            )}
          </CardContent>
        </Card>
      )}
    </section>
  );
}
