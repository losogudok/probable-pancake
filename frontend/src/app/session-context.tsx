import { createContext, useContext, useMemo, useState, type PropsWithChildren } from "react";
import type { DemoRole } from "../domain/types";
import { persistence } from "../mocks/persistence";

interface SessionValue { role: DemoRole; setRole: (role: DemoRole) => void; history: string[]; refreshHistory: () => void; resetDemo: () => void }
const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: PropsWithChildren) {
  const [role, setRoleState] = useState<DemoRole>(() => persistence.getRole());
  const [history, setHistory] = useState(() => persistence.getHistory());
  const value = useMemo<SessionValue>(() => ({
    role, history,
    setRole(next) { persistence.setRole(next); setRoleState(next); },
    refreshHistory() { setHistory(persistence.getHistory()); },
    resetDemo() { persistence.reset(); setRoleState("researcher"); setHistory([]); window.location.reload(); },
  }), [role, history]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
export function useSession() { const value = useContext(SessionContext); if (!value) throw new Error("SessionProvider missing"); return value; }
