import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { apiFetch } from './api';

export type AccountType = 'diner' | 'restaurant' | 'admin';

export interface UserData {
  username: string;
  accountType: AccountType;
}

interface AppContextValue {
  userData: UserData | null;
  setUserData: (u: UserData | null) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [userData, setUserData] = useState<UserData | null>(null);

  const value = useMemo(
    () => ({
      userData,
      setUserData,
    }),
    [userData],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext() {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return ctx;
}

export function useLogout(navigate: (to: string) => void) {
  const { setUserData } = useAppContext();
  return useCallback(async () => {
    try {
      await apiFetch('/api/auth/logout/', { method: 'POST' });
    } catch {
      /* ignore */
    }
    navigate('/home/');
    // Defer clearing user data so the navigation to /home/ commits
    // before RequireAuth can re-evaluate and redirect to /signin/.
    setTimeout(() => setUserData(null), 0);
  }, [navigate, setUserData]);
}
