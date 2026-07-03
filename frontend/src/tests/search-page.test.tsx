import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import { SessionProvider } from "../app/session-context";
import { SearchPage } from "../features/search/SearchPage";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><SessionProvider><MemoryRouter><SearchPage/></MemoryRouter></SessionProvider></QueryClientProvider>);
}

describe("SearchPage", () => {
  it("renders an accessible search-first landing", async () => {
    const view = renderPage();
    expect(screen.getByRole("heading", { name: "Знания R&D — в одном ответе" })).toBeInTheDocument();
    const results = await axe(view.container);
    expect(results.violations).toHaveLength(0);
  });

  it("runs the catholyte scenario and shows evidence", async () => {
    const user = userEvent.setup(); renderPage();
    await user.click(screen.getByRole("button", { name: /Циркуляция католита/ }));
    expect(await screen.findByText(/20–30 л\/ч — документированный/)).toBeInTheDocument();
    expect(screen.getByText(/Скорость циркуляции обычно составляет 20–30 л\/ч/)).toBeInTheDocument();
  });
});
