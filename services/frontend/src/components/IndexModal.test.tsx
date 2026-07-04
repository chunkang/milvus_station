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
      ],
    });
    mockedApi.indexToMilvus.mockResolvedValue({
      status: "ok",
      collection: "app_users_bio",
      indexed: 42,
      dim: 384,
    });
  });

  it("shows the column picker with non-embeddable columns disabled", async () => {
    render(<IndexModal database="app" table="users" onClose={() => {}} />);

    const idRadio = (await screen.findByRole("radio", {
      name: /id/,
    })) as HTMLInputElement;
    const bioRadio = screen.getByRole("radio", { name: /bio/ }) as HTMLInputElement;

    expect(idRadio).toBeDisabled();
    expect(bioRadio).toBeEnabled();
  });

  it("indexes with the chosen column and shows the result", async () => {
    render(<IndexModal database="app" table="users" onClose={() => {}} />);

    const bioRadio = await screen.findByRole("radio", { name: /bio/ });
    fireEvent.click(bioRadio);
    fireEvent.click(screen.getByRole("button", { name: /^index$/i }));

    await waitFor(() =>
      expect(mockedApi.indexToMilvus).toHaveBeenCalledWith({
        database: "app",
        table: "users",
        column: "bio",
      })
    );
    expect(await screen.findByText(/indexed 42 rows/i)).toBeInTheDocument();
  });
});
