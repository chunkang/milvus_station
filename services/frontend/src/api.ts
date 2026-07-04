// Typed fetch wrapper for the milvus_station backend API.
// All calls hit relative /api/... paths (same-origin, proxied by nginx).

// ---------- Response types ----------

export interface DatabasesResponse {
  databases: string[];
}

export interface TableInfo {
  name: string;
  rows: number;
}

export interface TablesResponse {
  database: string;
  tables: TableInfo[];
}

export interface ColumnInfo {
  name: string;
  type: string;
  embeddable: boolean;
}

export interface ColumnsResponse {
  database: string;
  table: string;
  columns: ColumnInfo[];
}

export interface RowsResponse {
  database: string;
  table: string;
  page: number;
  page_size: number;
  total: number;
  columns: string[];
  rows: unknown[][];
}

export interface IndexRequest {
  database: string;
  table: string;
  column: string;
}

export interface IndexResponse {
  status: "ok" | "error";
  collection?: string;
  indexed?: number;
  dim?: number;
  message?: string;
}

export interface CollectionInfo {
  name: string;
  count: number;
}

export interface CollectionsResponse {
  collections: CollectionInfo[];
  status?: "unreachable";
}

export interface CollectionDataResponse {
  collection: string;
  page: number;
  page_size: number;
  total: number;
  fields: string[];
  rows: Record<string, unknown>[];
  status?: "unreachable";
}

// ---------- Core request helper ----------

/**
 * Perform a JSON request against the backend.
 * Throws an Error carrying a human-readable message on network failure
 * or a non-2xx response, so the UI can surface it directly.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (err) {
    // Network-level failure (DNS, offline, CORS, etc.)
    const detail = err instanceof Error ? err.message : String(err);
    throw new Error(`Network error while requesting ${path}: ${detail}`);
  }

  if (!res.ok) {
    // Try to extract a message from a JSON error body, fall back to status.
    let message = `Request to ${path} failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body === "object" && "message" in body && body.message) {
        message = String((body as { message: unknown }).message);
      } else if (body && typeof body === "object" && "error" in body && body.error) {
        message = String((body as { error: unknown }).error);
      }
    } catch {
      // ignore body parse errors, keep default message
    }
    throw new Error(message);
  }

  return (await res.json()) as T;
}

function enc(segment: string): string {
  return encodeURIComponent(segment);
}

// ---------- Source (MySQL) endpoints ----------

export function getDatabases(): Promise<DatabasesResponse> {
  return request<DatabasesResponse>("/api/databases");
}

export function getTables(database: string): Promise<TablesResponse> {
  return request<TablesResponse>(`/api/databases/${enc(database)}/tables`);
}

export function getColumns(
  database: string,
  table: string
): Promise<ColumnsResponse> {
  return request<ColumnsResponse>(
    `/api/databases/${enc(database)}/tables/${enc(table)}/columns`
  );
}

export function getRows(
  database: string,
  table: string,
  page: number,
  pageSize: number
): Promise<RowsResponse> {
  return request<RowsResponse>(
    `/api/databases/${enc(database)}/tables/${enc(table)}/rows?page=${page}&page_size=${pageSize}`
  );
}

export function indexToMilvus(payload: IndexRequest): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------- Milvus endpoints ----------

export function getCollections(): Promise<CollectionsResponse> {
  return request<CollectionsResponse>("/api/milvus/collections");
}

export function getCollectionData(
  name: string,
  page: number,
  pageSize: number
): Promise<CollectionDataResponse> {
  return request<CollectionDataResponse>(
    `/api/milvus/collections/${enc(name)}?page=${page}&page_size=${pageSize}`
  );
}
