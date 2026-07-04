import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the 'hello world' text", () => {
    render(<App />);
    expect(screen.getByText(/hello world/i)).toBeInTheDocument();
  });

  it("renders a link pointing to /mysql/ that opens in a new tab", () => {
    render(<App />);
    const link = screen.getByRole("link", { name: /mysql/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/mysql/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the default MySQL credentials", () => {
    render(<App />);
    expect(screen.getByText(/default mysql credentials/i)).toBeInTheDocument();
    const milvus = screen.getAllByText(/^milvus$/i);
    expect(milvus.length).toBeGreaterThanOrEqual(2); // id + password
  });
});
