import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "./session-context";

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } });
export function AppProviders({ children }: PropsWithChildren) { return <QueryClientProvider client={client}><SessionProvider>{children}</SessionProvider></QueryClientProvider>; }
