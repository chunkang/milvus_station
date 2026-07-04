import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App / Main landing", () => {
  it("renders the Main page with title and purpose by default", () => {
    render(<App />);
    // "milvus_station" appears in the nav brand and the hero title.
    expect(screen.getAllByText(/milvus_station/i).length).toBeGreaterThanOrEqual(
      1,
    );
    // Purpose / architecture copy replaces the old "hello world".
    expect(screen.getByText(/what it does/i)).toBeInTheDocument();
    expect(screen.getAllByText(/semantic/i).length).toBeGreaterThanOrEqual(1);
  });

  it("describes the architecture and data pipeline", () => {
    render(<App />);
    expect(screen.getByText(/^architecture$/i)).toBeInTheDocument();
    expect(screen.getAllByText(/nginx/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/ollama/i).length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(/milvus/i).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("shows the default MySQL credentials", () => {
    render(<App />);
    expect(screen.getByText(/default mysql credentials/i)).toBeInTheDocument();
    const milvus = screen.getAllByText(/^milvus$/i);
    expect(milvus.length).toBeGreaterThanOrEqual(2); // id + password
  });

  it("renders a mysqladmin link pointing to /mysql/ opening in a new tab", () => {
    render(<App />);
    const link = screen.getByRole("link", { name: /mysqladmin/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/mysql/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("exposes the navigation menus (Main, Source, Milvus, mysqladmin)", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /^main$/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^source$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^milvus$/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /mysqladmin/i })).toBeInTheDocument();
  });
});
