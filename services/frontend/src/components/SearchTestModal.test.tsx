// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import SearchTestModal from "./SearchTestModal";
import * as api from "../api";

vi.mock("../api");

const mockedApi = vi.mocked(api);

describe("SearchTestModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no numeric fields, so the base dialog behaves as before.
    mockedApi.getFilterFields.mockResolvedValue({
      collection: "docs",
      fields: [],
    });
  });

  it("runs a search and renders ranked results", async () => {
    mockedApi.searchCollection.mockResolvedValue({
      collection: "docs",
      query: "hello",
      top_k: 5,
      results: [
        { pk: 1, text: "best match", score: 0.9876 },
        { pk: 2, text: "second match", score: 0.4321 },
      ],
    });

    render(
      <SearchTestModal collection="docs" open onOpenChange={() => {}} />
    );

    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    await waitFor(() =>
      expect(mockedApi.searchCollection).toHaveBeenCalledWith(
        "docs",
        "hello",
        5,
        undefined
      )
    );

    expect(await screen.findByText("best match")).toBeInTheDocument();
    expect(screen.getByText("second match")).toBeInTheDocument();
    expect(screen.getByText("0.9876")).toBeInTheDocument();
  });

  it("shows the error message on an error response", async () => {
    mockedApi.searchCollection.mockResolvedValue({
      collection: "docs",
      query: "hello",
      top_k: 5,
      results: [],
      status: "error",
      message: "collection not indexed",
    });

    render(
      <SearchTestModal collection="docs" open onOpenChange={() => {}} />
    );

    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    expect(
      await screen.findByText(/collection not indexed/i)
    ).toBeInTheDocument();
  });

  it("renders 'No matches' when there are no results", async () => {
    mockedApi.searchCollection.mockResolvedValue({
      collection: "docs",
      query: "hello",
      top_k: 5,
      results: [],
    });

    render(
      <SearchTestModal collection="docs" open onOpenChange={() => {}} />
    );

    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    expect(await screen.findByText(/no matches/i)).toBeInTheDocument();
  });

  it("does not show the Filters section when there are no numeric fields", async () => {
    mockedApi.searchCollection.mockResolvedValue({
      collection: "docs",
      query: "hello",
      top_k: 5,
      results: [],
    });

    render(
      <SearchTestModal collection="docs" open onOpenChange={() => {}} />
    );

    // Wait for the filter-fields fetch to settle.
    await waitFor(() =>
      expect(mockedApi.getFilterFields).toHaveBeenCalledWith("docs")
    );

    expect(
      screen.queryByRole("button", { name: /add filter/i })
    ).not.toBeInTheDocument();

    // Search still works, called without filters (undefined).
    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    await waitFor(() =>
      expect(mockedApi.searchCollection).toHaveBeenCalledWith(
        "docs",
        "hello",
        5,
        undefined
      )
    );
  });

  it("adds a numeric filter row and passes it to the search", async () => {
    mockedApi.getFilterFields.mockResolvedValue({
      collection: "movies",
      fields: [
        { name: "year", type: "int" },
        { name: "rating", type: "float" },
      ],
    });
    mockedApi.searchCollection.mockResolvedValue({
      collection: "movies",
      query: "space epic",
      top_k: 5,
      results: [],
    });

    render(
      <SearchTestModal collection="movies" open onOpenChange={() => {}} />
    );

    // The Filters section appears once the numeric fields load.
    const addButton = await screen.findByRole("button", {
      name: /add filter/i,
    });
    fireEvent.click(addButton);

    // Field defaults to the first numeric field ("year"); keep it.
    // Operator defaults to ">=" (gte); keep it.
    // Set the value.
    fireEvent.change(screen.getByLabelText(/filter value/i), {
      target: { value: "2000" },
    });

    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "space epic" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    await waitFor(() =>
      expect(mockedApi.searchCollection).toHaveBeenCalledWith(
        "movies",
        "space epic",
        5,
        [{ field: "year", op: "gte", value: 2000 }]
      )
    );
  });

  it("lets the user change field and operator via the selects", async () => {
    mockedApi.getFilterFields.mockResolvedValue({
      collection: "movies",
      fields: [
        { name: "year", type: "int" },
        { name: "rating", type: "float" },
      ],
    });
    mockedApi.searchCollection.mockResolvedValue({
      collection: "movies",
      query: "great",
      top_k: 5,
      results: [],
    });

    render(
      <SearchTestModal collection="movies" open onOpenChange={() => {}} />
    );

    fireEvent.click(await screen.findByRole("button", { name: /add filter/i }));

    // Change field to "rating".
    fireEvent.click(screen.getByRole("combobox", { name: /filter field/i }));
    fireEvent.click(await screen.findByRole("option", { name: "rating" }));

    // Change operator to ">".
    fireEvent.click(screen.getByRole("combobox", { name: /filter operator/i }));
    fireEvent.click(await screen.findByRole("option", { name: ">" }));

    fireEvent.change(screen.getByLabelText(/filter value/i), {
      target: { value: "4" },
    });

    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "great" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    await waitFor(() =>
      expect(mockedApi.searchCollection).toHaveBeenCalledWith(
        "movies",
        "great",
        5,
        [{ field: "rating", op: "gt", value: 4 }]
      )
    );
  });

  it("ignores filter rows with an empty value", async () => {
    mockedApi.getFilterFields.mockResolvedValue({
      collection: "movies",
      fields: [{ name: "year", type: "int" }],
    });
    mockedApi.searchCollection.mockResolvedValue({
      collection: "movies",
      query: "hello",
      top_k: 5,
      results: [],
    });

    render(
      <SearchTestModal collection="movies" open onOpenChange={() => {}} />
    );

    // Add a row but leave its value empty.
    fireEvent.click(await screen.findByRole("button", { name: /add filter/i }));

    fireEvent.change(screen.getByLabelText(/query text/i), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run test/i }));

    await waitFor(() =>
      expect(mockedApi.searchCollection).toHaveBeenCalledWith(
        "movies",
        "hello",
        5,
        undefined
      )
    );
  });
});
