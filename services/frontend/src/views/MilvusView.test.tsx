import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MilvusView from "./MilvusView";
import * as api from "../api";

vi.mock("../api");

const mockedApi = vi.mocked(api);

describe("MilvusView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists collections with their entity counts", async () => {
    mockedApi.getCollections.mockResolvedValue({
      collections: [
        { name: "docs", count: 10 },
        { name: "faqs", count: 3 },
      ],
    });

    render(<MilvusView />);

    expect(
      await screen.findByRole("button", { name: /docs/ })
    ).toBeInTheDocument();
    expect(screen.getByText(/10 entities/i)).toBeInTheDocument();
  });

  it("shows a friendly message when Milvus is unreachable", async () => {
    mockedApi.getCollections.mockResolvedValue({
      collections: [],
      status: "unreachable",
    });

    render(<MilvusView />);

    expect(
      await screen.findByText(/milvus not reachable/i)
    ).toBeInTheDocument();
  });

  it("loads a collection's rows with pagination when clicked", async () => {
    mockedApi.getCollections.mockResolvedValue({
      collections: [{ name: "docs", count: 30 }],
    });
    mockedApi.getCollectionData.mockResolvedValue({
      collection: "docs",
      page: 1,
      page_size: 25,
      total: 30,
      fields: ["id", "text"],
      rows: [{ id: 1, text: "hello" }],
    });

    render(<MilvusView />);
    fireEvent.click(await screen.findByRole("button", { name: /docs/ }));

    expect(await screen.findByText("hello")).toBeInTheDocument();
    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(mockedApi.getCollectionData).toHaveBeenCalledWith("docs", 1, 25)
    );
  });
});
