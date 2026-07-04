// ┌──────────────────────────────────────────────────────────────────────────┐
// │ milvus_station                                                           │
// │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
// │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
// └──────────────────────────────────────────────────────────────────────────┘

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import IndexModal from "./IndexModal";
import * as api from "../api";

vi.mock("../api");

const mockedApi = vi.mocked(api);

describe("IndexModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.getColumns.mockResolvedValue({
      database: "app",
      table: "users",
      columns: [
        { name: "id", type: "int", embeddable: false },
        { name: "bio", type: "text", embeddable: true },
        { name: "title", type: "varchar", embeddable: true },
      ],
    });
    mockedApi.indexToMilvus.mockResolvedValue({
      status: "ok",
      collection: "app_users",
      indexed: 42,
      dim: 384,
      columns: ["bio", "title"],
    });
  });

  it("shows the columns as checkboxes with non-embeddable columns disabled", async () => {
    render(<IndexModal database="app" table="users" onClose={() => {}} />);

    const idBox = (await screen.findByRole("checkbox", {
      name: /id/,
    })) as HTMLInputElement;
    const bioBox = screen.getByRole("checkbox", {
      name: /bio/,
    }) as HTMLInputElement;

    expect(idBox).toBeDisabled();
    expect(bioBox).toBeEnabled();
  });

  it("indexes with the multiple selected columns and shows the result", async () => {
    render(<IndexModal database="app" table="users" onClose={() => {}} />);

    // "bio" is pre-selected (first embeddable); also select "title".
    const titleBox = await screen.findByRole("checkbox", { name: /title/ });
    fireEvent.click(titleBox);
    fireEvent.click(screen.getByRole("button", { name: /^index$/i }));

    await waitFor(() =>
      expect(mockedApi.indexToMilvus).toHaveBeenCalledWith({
        database: "app",
        table: "users",
        columns: ["bio", "title"],
      })
    );
    expect(await screen.findByText(/indexed 42 rows/i)).toBeInTheDocument();
  });

  it("disables Index when no column is selected", async () => {
    render(<IndexModal database="app" table="users" onClose={() => {}} />);

    // Deselect the pre-selected "bio" so nothing is chosen.
    const bioBox = await screen.findByRole("checkbox", { name: /bio/ });
    fireEvent.click(bioBox);

    expect(screen.getByRole("button", { name: /^index$/i })).toBeDisabled();
  });
});
