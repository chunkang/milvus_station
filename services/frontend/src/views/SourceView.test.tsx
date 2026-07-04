import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SourceView from "./SourceView";
import * as api from "../api";

vi.mock("../api");

const mockedApi = vi.mocked(api);

describe("SourceView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getDatabases.mockResolvedValue({
      databases: ["milvus_station", "otherdb"],
    });
    mockedApi.getTables.mockResolvedValue({
      database: "app",
      tables: [{ name: "users", rows: 42 }],
    });
    mockedApi.getRows.mockImplementation((_db, _table, page) =>
      Promise.resolve({
        database: "app",
        table: "users",
        page,
        page_size: 25,
        total: 50,
        columns: ["id", "name"],
        rows: [[page === 1 ? 1 : 26, page === 1 ? "alice" : "zoe"]],
      })
    );
    mockedApi.importSamples.mockResolvedValue({
      status: "ok",
      database: "milvus_station",
      tables: [
        { name: "products", created: true, rows: 10 },
        { name: "articles", created: true, rows: 8 },
        { name: "movies", created: true, rows: 6 },
        { name: "faqs", created: true, rows: 4 },
      ],
    });
    // By default no Milvus collections exist, so no "Test" buttons render.
    mockedApi.getCollections.mockResolvedValue({ collections: [] });
    mockedApi.searchCollection.mockResolvedValue({
      collection: "milvus_station_users",
      query: "hi",
      top_k: 5,
      results: [],
    });
  });

  it("renders the database list from the API", async () => {
    render(<SourceView />);
    expect(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    ).toBeInTheDocument();
  });

  it("shows tables with an 'Index to Milvus' button when a DB is clicked", async () => {
    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );

    expect(
      await screen.findByRole("button", { name: /users/ })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /index to milvus/i })
    ).toBeInTheDocument();
    expect(mockedApi.getTables).toHaveBeenCalledWith("milvus_station");
  });

  it("shows 'Import sample tables' for the app database, imports, and refreshes the tables list", async () => {
    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );

    // Tables loaded once for the selected DB.
    await screen.findByRole("button", { name: /users/ });
    expect(mockedApi.getTables).toHaveBeenCalledTimes(1);

    const importButton = screen.getByRole("button", {
      name: /import sample tables/i,
    });
    fireEvent.click(importButton);

    // importSamples called with the app database.
    await waitFor(() =>
      expect(mockedApi.importSamples).toHaveBeenCalledWith("milvus_station")
    );

    // Tables list refreshed (getTables called again after import).
    await waitFor(() => expect(mockedApi.getTables).toHaveBeenCalledTimes(2));
    expect(mockedApi.getTables).toHaveBeenLastCalledWith("milvus_station");
  });

  it("does NOT show 'Import sample tables' for a non-app database", async () => {
    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^otherdb$/ })
    );

    // Tables for otherdb load, but no import button is rendered.
    await screen.findByRole("button", { name: /users/ });
    expect(
      screen.queryByRole("button", { name: /import sample tables/i })
    ).not.toBeInTheDocument();
  });

  it("renders rows and pagination when a table is clicked, and Next advances the page", async () => {
    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );
    fireEvent.click(await screen.findByRole("button", { name: /users/ }));

    // First page rows + pagination indicator.
    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
    expect(mockedApi.getRows).toHaveBeenCalledWith(
      "milvus_station",
      "users",
      1,
      25
    );

    // Advance to page 2.
    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(mockedApi.getRows).toHaveBeenCalledWith(
        "milvus_station",
        "users",
        2,
        25
      )
    );
    expect(await screen.findByText("zoe")).toBeInTheDocument();
  });

  it("renders a 'Test' button only for tables that have a matching Milvus collection", async () => {
    // Two tables: "users" has a collection, "orders" does not.
    mockedApi.getTables.mockResolvedValue({
      database: "milvus_station",
      tables: [
        { name: "users", rows: 42 },
        { name: "orders", rows: 7 },
      ],
    });
    mockedApi.getCollections.mockResolvedValue({
      collections: [{ name: "milvus_station_users", count: 42 }],
    });

    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );

    // Both table buttons render.
    await screen.findByRole("button", { name: /users/ });
    await screen.findByRole("button", { name: /orders/ });

    // Exactly one "Test" button, and it belongs to the row that has a collection.
    const testButtons = await screen.findAllByRole("button", {
      name: /^test$/i,
    });
    expect(testButtons).toHaveLength(1);

    const usersRow = screen
      .getByRole("button", { name: /users/ })
      .closest("li");
    const ordersRow = screen
      .getByRole("button", { name: /orders/ })
      .closest("li");
    expect(usersRow).not.toBeNull();
    expect(ordersRow).not.toBeNull();
    expect(usersRow).toContainElement(testButtons[0]);
    expect(ordersRow?.textContent).not.toMatch(/test/i);
  });

  it("opens the search dialog for the correct collection when 'Test' is clicked", async () => {
    mockedApi.getTables.mockResolvedValue({
      database: "milvus_station",
      tables: [{ name: "users", rows: 42 }],
    });
    mockedApi.getCollections.mockResolvedValue({
      collections: [{ name: "milvus_station_users", count: 42 }],
    });

    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );

    const testButton = await screen.findByRole("button", { name: /^test$/i });
    fireEvent.click(testButton);

    // The SearchTestModal dialog opens targeting the collection name.
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/search test on/i);
    expect(dialog).toHaveTextContent("milvus_station_users");
  });

  it("shows a 'Test' button in the selected table's record-list header and opens the search dialog for its collection", async () => {
    mockedApi.getTables.mockResolvedValue({
      database: "milvus_station",
      tables: [{ name: "users", rows: 42 }],
    });
    mockedApi.getCollections.mockResolvedValue({
      collections: [{ name: "milvus_station_users", count: 42 }],
    });

    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );

    // Select the table so its records (DataTable) are displayed.
    fireEvent.click(await screen.findByRole("button", { name: /users/ }));
    await screen.findByText("alice");

    // The record-list header shows the table name and a Test button beside it.
    const recordHeaderTitle = screen.getByText(/milvus_station · users/i);
    const recordHeaderRow = recordHeaderTitle.parentElement as HTMLElement;
    expect(recordHeaderRow).not.toBeNull();

    // A Test button lives in the record-list header (in addition to the per-row one).
    const headerTestButton = within(recordHeaderRow).getByRole("button", {
      name: /^test$/i,
    });
    expect(headerTestButton).toBeInTheDocument();

    fireEvent.click(headerTestButton);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/search test on/i);
    expect(dialog).toHaveTextContent("milvus_station_users");
  });

  it("does not crash and shows no 'Test' buttons when Milvus is unreachable", async () => {
    mockedApi.getTables.mockResolvedValue({
      database: "milvus_station",
      tables: [{ name: "users", rows: 42 }],
    });
    mockedApi.getCollections.mockResolvedValue({
      collections: [],
      status: "unreachable",
    });

    render(<SourceView />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^milvus_station$/ })
    );

    await screen.findByRole("button", { name: /users/ });
    expect(
      screen.queryByRole("button", { name: /^test$/i })
    ).not.toBeInTheDocument();
  });
});
