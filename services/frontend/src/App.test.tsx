import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the 'hello world' text", () => {
    render(<App />);
    expect(screen.getByText(/hello world/i)).toBeInTheDocument();
  });

  it("renders a link pointing to /mysql", () => {
    render(<App />);
    const link = screen.getByRole("link", { name: /mysql/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/mysql");
  });
});
