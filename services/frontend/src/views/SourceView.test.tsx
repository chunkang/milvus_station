import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SourceView from "./SourceView";
import * as api from "../api";

vi.mock("../api");

const mockedApi = vi.mocked(api);

describe("SourceView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getDatabases.mockResolvedValue({ databases: ["app"] });
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
  });

  it("renders the database list from the API", async () => {
    render(<SourceView />);
    expect(
      await screen.findByRole("button", { name: /^app$/ })
    ).toBeInTheDocument();
  });

  it("shows tables with an 'Index to Milvus' button when a DB is clicked", async () => {
    render(<SourceView />);
    fireEvent.click(await screen.findByRole("button", { name: /^app$/ }));

    expect(
      await screen.findByRole("button", { name: /users/ })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /index to milvus/i })
    ).toBeInTheDocument();
    expect(mockedApi.getTables).toHaveBeenCalledWith("app");
  });

  it("renders rows and pagination when a table is clicked, and Next advances the page", async () => {
    render(<SourceView />);
    fireEvent.click(await screen.findByRole("button", { name: /^app$/ }));
    fireEvent.click(await screen.findByRole("button", { name: /users/ }));

    // First page rows + pagination indicator.
    expect(await screen.findByText("alice")).toBeInTheDocument();
    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
    expect(mockedApi.getRows).toHaveBeenCalledWith("app", "users", 1, 25);

    // Advance to page 2.
    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    await waitFor(() =>
      expect(mockedApi.getRows).toHaveBeenCalledWith("app", "users", 2, 25)
    );
    expect(await screen.findByText("zoe")).toBeInTheDocument();
  });
});
