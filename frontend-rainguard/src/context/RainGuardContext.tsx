import { createContext, useContext, useMemo, type ReactNode } from "react";
import { createRainGuardClient } from "../lib/client";
import { RainGuard } from "../lib/contract";
import { useWallet } from "../hooks/useWallet";

interface RainGuardContextValue {
  wallet: ReturnType<typeof useWallet>;
  contract: RainGuard;
}

const RainGuardContext = createContext<RainGuardContextValue | null>(null);

export function RainGuardProvider({ children }: { children: ReactNode }) {
  const wallet = useWallet();
  const contract = useMemo(() => {
    const client = createRainGuardClient(wallet.address);
    return new RainGuard(client);
  }, [wallet.address]);

  return (
    <RainGuardContext.Provider value={{ wallet, contract }}>
      {children}
    </RainGuardContext.Provider>
  );
}

export function useRainGuard(): RainGuardContextValue {
  const ctx = useContext(RainGuardContext);
  if (!ctx) {
    throw new Error("useRainGuard must be used within a RainGuardProvider");
  }
  return ctx;
}
