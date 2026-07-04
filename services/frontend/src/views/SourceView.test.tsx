import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
});
