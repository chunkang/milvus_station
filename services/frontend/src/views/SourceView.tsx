// Source view: browse MySQL databases -> tables -> table rows.
// Provides an "Index to Milvus" action per table (opens IndexModal).
import { useEffect, useState } from "react";
import {
  Database,
  DownloadCloud,
  FlaskConical,
  Loader2,
  Search,
  Sparkles,
  Table2,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";
import {
  getDatabases,
  getTables,
  getRows,
  getCollections,
  importSamples,
  type TableInfo,
  type RowsResponse,
} from "../api";
import DataTable from "../components/DataTable";
import IndexModal from "../components/IndexModal";
import SearchTestModal from "../components/SearchTestModal";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

// The application's own schema database. Sample tables can only be imported here.
const APP_DATABASE = "milvus_station";

// Replicate the backend's sanitize_collection_name(db, table): join db and
// table with "_", replace every char not in [0-9a-zA-Z_] with "_", and prefix
// "c_" if the result starts with a digit. Must match the backend exactly so we
// can tell whether a table already has a Milvus collection.
function collectionNameFor(db: string, table: string): string {
  let safe = `${db}_${table}`.replace(/[^0-9a-zA-Z_]/g, "_");
  if (/^[0-9]/.test(safe)) safe = `c_${safe}`;
  return safe;
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <TriangleAlert />
      <AlertTitle>Something went wrong</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-4/5" />
    </div>
  );
}

export default function SourceView() {
  // Databases
  const [databases, setDatabases] = useState<string[] | null>(null);
  const [dbError, setDbError] = useState<string | null>(null);
  const [activeDb, setActiveDb] = useState<string | null>(null);

  // Tables
  const [tables, setTables] = useState<TableInfo[] | null>(null);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);
  const [activeTable, setActiveTable] = useState<string | null>(null);

  // Rows
  const [rows, setRows] = useState<RowsResponse | null>(null);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Index modal target
  const [indexTarget, setIndexTarget] = useState<{
    database: string;
    table: string;
  } | null>(null);

  // Existing Milvus collection names. Used to decide whether a table already
  // has a collection and should therefore show a "Test" button.
  const [collections, setCollections] = useState<Set<string>>(new Set());

  // Search-test modal target (a Milvus collection name).
  const [testCollection, setTestCollection] = useState<string | null>(null);

  // Sample import
  const [importing, setImporting] = useState(false);

  // Load databases on mount.
  useEffect(() => {
    let active = true;
    getDatabases()
      .then((res) => active && setDatabases(res.databases))
      .catch(
        (err: unknown) =>
          active &&
          setDbError(err instanceof Error ? err.message : String(err))
      );
    return () => {
      active = false;
    };
  }, []);

  // Fetch the set of existing Milvus collection names. Failures (including an
  // "unreachable" Milvus) are swallowed into an empty set so the Source view
  // never crashes just because Milvus is down.
  function refreshCollections() {
    return getCollections()
      .then((res) => {
        if (res.status === "unreachable" || !Array.isArray(res.collections)) {
          setCollections(new Set());
          return;
        }
        setCollections(new Set(res.collections.map((c) => c.name)));
      })
      .catch(() => setCollections(new Set()));
  }

  function refreshTables(db: string) {
    setTablesError(null);
    setTablesLoading(true);
    // Refresh collections alongside tables so each row can decide whether to
    // show a "Test" button.
    void refreshCollections();
    return getTables(db)
      .then((res) => {
        setTables(res.tables);
      })
      .catch((err: unknown) =>
        setTablesError(err instanceof Error ? err.message : String(err))
      )
      .finally(() => setTablesLoading(false));
  }

  function selectDatabase(db: string) {
    setActiveDb(db);
    setActiveTable(null);
    setRows(null);
    setTables(null);
    refreshTables(db);
  }

  function handleImportSamples() {
    if (!activeDb) return;
    setImporting(true);
    importSamples(activeDb)
      .then((res) => {
        const names = res.tables.map((t) => t.name).join(", ");
        toast.success(
          `Imported ${res.tables.length} sample ${
            res.tables.length === 1 ? "table" : "tables"
          }${names ? `: ${names}` : ""}`
        );
        // Re-fetch tables so the newly imported ones appear.
        return refreshTables(activeDb);
      })
      .catch((err: unknown) =>
        toast.error(err instanceof Error ? err.message : String(err))
      )
      .finally(() => setImporting(false));
  }

  function loadRows(db: string, table: string, nextPage: number) {
    setRowsLoading(true);
    setRowsError(null);
    getRows(db, table, nextPage, PAGE_SIZE)
      .then((res) => {
        setRows(res);
        setPage(res.page);
      })
      .catch((err: unknown) =>
        setRowsError(err instanceof Error ? err.message : String(err))
      )
      .finally(() => setRowsLoading(false));
  }

  function selectTable(table: string) {
    if (!activeDb) return;
    setActiveTable(table);
    setPage(1);
    loadRows(activeDb, table, 1);
  }

  function changePage(nextPage: number) {
    if (!activeDb || !activeTable) return;
    loadRows(activeDb, activeTable, nextPage);
  }

  return (
    <section aria-label="Source" className="mx-auto max-w-6xl px-4 pb-16">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Database className="size-6 text-muted-foreground" />
          Source
        </h1>
        <p className="text-sm text-muted-foreground">
          Browse MySQL databases and tables, then index a column into Milvus.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(200px,240px)_1fr]">
        {/* Databases column */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-sm">Databases</CardTitle>
          </CardHeader>
          <CardContent>
            {dbError && <ErrorAlert message={dbError} />}
            {!databases && !dbError && <ListSkeleton />}
            {databases && databases.length === 0 && (
              <p className="text-sm italic text-muted-foreground">
                No databases
              </p>
            )}
            {databases && databases.length > 0 && (
              <ul className="flex flex-col gap-1">
                {databases.map((db) => (
                  <li key={db}>
                    <Button
                      type="button"
                      variant={activeDb === db ? "secondary" : "ghost"}
                      size="sm"
                      className="w-full justify-start"
                      onClick={() => selectDatabase(db)}
                    >
                      <Database className="size-4 text-muted-foreground" />
                      {db}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Tables column */}
        <Card className={cn(!activeDb && "hidden md:block")}>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-col gap-1.5">
                <CardTitle className="text-sm">
                  {activeDb ? `Tables in ${activeDb}` : "Tables"}
                </CardTitle>
                <CardDescription>
                  {activeDb
                    ? "Select a table to preview rows, or index a column."
                    : "Pick a database to see its tables."}
                </CardDescription>
              </div>
              {activeDb === APP_DATABASE && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                  onClick={handleImportSamples}
                  disabled={importing}
                >
                  {importing ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <DownloadCloud className="size-4" />
                  )}
                  {importing ? "Importing…" : "Import sample tables"}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {!activeDb && (
              <p className="text-sm italic text-muted-foreground">
                No database selected
              </p>
            )}
            {tablesError && <ErrorAlert message={tablesError} />}
            {tablesLoading && <ListSkeleton />}
            {tables && tables.length === 0 && !tablesLoading && (
              <p className="text-sm italic text-muted-foreground">No tables</p>
            )}
            {activeDb && tables && tables.length > 0 && (
              <ScrollArea className="max-h-80">
                <ul className="flex flex-col gap-1 pr-2">
                  {tables.map((t) => {
                    const collectionName = collectionNameFor(activeDb, t.name);
                    const hasCollection = collections.has(collectionName);
                    return (
                      <li
                        key={t.name}
                        className={cn(
                          "flex items-center justify-between gap-2 rounded-md border border-transparent px-1 py-0.5",
                          activeTable === t.name && "border-border bg-muted/50"
                        )}
                      >
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="flex-1 justify-start"
                          onClick={() => selectTable(t.name)}
                        >
                          <Table2 className="size-4 text-muted-foreground" />
                          <span>{t.name}</span>
                          <Badge variant="secondary" className="ml-auto">
                            {t.rows}
                          </Badge>
                        </Button>
                        {hasCollection && (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => setTestCollection(collectionName)}
                          >
                            <FlaskConical className="size-3.5" />
                            Test
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setIndexTarget({
                              database: activeDb,
                              table: t.name,
                            })
                          }
                        >
                          <Sparkles className="size-3.5" />
                          Index to Milvus
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Rows */}
      {activeTable && (
        <Card className="mt-6">
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base">
                {activeDb} · {activeTable}
              </CardTitle>
              {activeDb &&
                collections.has(collectionNameFor(activeDb, activeTable)) && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setTestCollection(
                        collectionNameFor(activeDb, activeTable)
                      )
                    }
                  >
                    <Search className="size-4" />
                    Test
                  </Button>
                )}
            </div>
          </CardHeader>
          <CardContent>
            {rowsError && <ErrorAlert message={rowsError} />}
            {rowsLoading && !rows && (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            )}
            {rows && (
              <DataTable
                columns={rows.columns}
                rows={rows.rows}
                page={page}
                pageSize={rows.page_size}
                total={rows.total}
                onPageChange={changePage}
                emptyMessage="No rows in this table"
              />
            )}
          </CardContent>
        </Card>
      )}

      {indexTarget && (
        <IndexModal
          database={indexTarget.database}
          table={indexTarget.table}
          onClose={() => setIndexTarget(null)}
          onIndexed={() => {
            // A new collection may now exist; refresh so its Test button shows.
            void refreshCollections();
          }}
        />
      )}

      {testCollection && (
        <SearchTestModal
          collection={testCollection}
          open
          onOpenChange={(open) => !open && setTestCollection(null)}
        />
      )}
    </section>
  );
}
