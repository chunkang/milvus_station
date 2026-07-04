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
      expect(mockedApi.searchCollection).toHaveBeenCalledWith("docs", "hello", 5)
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
});
