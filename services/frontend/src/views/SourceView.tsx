// Source view: browse MySQL databases -> tables -> table rows.
// Provides an "Index to Milvus" action per table (opens IndexModal).
import { useEffect, useState } from "react";
import { Database, Sparkles, Table2, TriangleAlert } from "lucide-react";
import {
  getDatabases,
  getTables,
  getRows,
  type TableInfo,
  type RowsResponse,
} from "../api";
import DataTable from "../components/DataTable";
import IndexModal from "../components/IndexModal";
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

  function selectDatabase(db: string) {
    setActiveDb(db);
    setActiveTable(null);
    setRows(null);
    setTables(null);
    setTablesError(null);
    setTablesLoading(true);
    getTables(db)
      .then((res) => {
        setTables(res.tables);
      })
      .catch((err: unknown) =>
        setTablesError(err instanceof Error ? err.message : String(err))
      )
      .finally(() => setTablesLoading(false));
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
            <CardTitle className="text-sm">
              {activeDb ? `Tables in ${activeDb}` : "Tables"}
            </CardTitle>
            <CardDescription>
              {activeDb
                ? "Select a table to preview rows, or index a column."
                : "Pick a database to see its tables."}
            </CardDescription>
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
                  {tables.map((t) => (
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
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setIndexTarget({ database: activeDb, table: t.name })
                        }
                      >
                        <Sparkles className="size-3.5" />
                        Index to Milvus
                      </Button>
                    </li>
                  ))}
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
            <CardTitle className="text-base">
              {activeDb} · {activeTable}
            </CardTitle>
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
        />
      )}
    </section>
  );
}
