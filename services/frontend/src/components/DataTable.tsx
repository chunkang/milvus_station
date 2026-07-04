// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

// Reusable data grid built on TanStack Table.
// Accepts columns + rows where each row is an array of cell values, aligned
// positionally with the columns array. Pagination is SERVER-SIDE: the parent
// fetches one page at a time and passes page/pageSize/total; the Prev/Next
// controls simply ask the parent for another page. Column headers are
// client-side sortable for the currently loaded page.
import { useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface DataTableProps {
  columns: string[];
  rows: unknown[][];
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  emptyMessage?: string;
}

type Row = unknown[];

function renderCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DataTable({
  columns,
  rows,
  page,
  pageSize,
  total,
  onPageChange,
  emptyMessage = "No rows",
}: DataTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columnDefs = useMemo<ColumnDef<Row>[]>(
    () =>
      columns.map((col, ci) => ({
        id: `c${ci}`,
        header: col,
        accessorFn: (row) => row[ci],
        cell: (info) => renderCell(info.getValue()),
        sortingFn: "alphanumeric",
      })),
    [columns]
  );

  const table = useReactTable({
    data: rows,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
  });

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <div className="flex flex-col gap-3">
      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-10 text-center text-sm italic text-muted-foreground">
          {emptyMessage}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    const sorted = header.column.getIsSorted();
                    return (
                      <TableHead key={header.id} className="whitespace-nowrap">
                        <button
                          type="button"
                          className="-ml-1 inline-flex items-center gap-1 rounded px-1 py-0.5 font-medium hover:text-foreground"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                          {sorted === "asc" ? (
                            <ArrowUp className="size-3.5 text-foreground" />
                          ) : sorted === "desc" ? (
                            <ArrowDown className="size-3.5 text-foreground" />
                          ) : (
                            <ChevronsUpDown className="size-3.5 opacity-40" />
                          )}
                        </button>
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className="max-w-[320px] truncate font-mono text-xs"
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={!canPrev}
        >
          Prev
        </Button>
        <span aria-live="polite" className="text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={!canNext}
        >
          Next
        </Button>
        <span className="ml-auto text-xs text-muted-foreground">
          {total} total
        </span>
      </div>
    </div>
  );
}
