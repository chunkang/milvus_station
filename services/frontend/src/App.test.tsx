import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App / Home landing", () => {
  it("renders the 'hello world' text by default", () => {
    render(<App />);
    expect(screen.getByText(/hello world/i)).toBeInTheDocument();
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

  it("exposes the three navigation menus", () => {
    render(<App />);
    expect(screen.getByRole("button", { name: /^source$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^milvus$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /mysqladmin/i })).toBeInTheDocument();
  });
});
