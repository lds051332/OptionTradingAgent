import { useEffect, useState } from "react";
import { fetchMe, logout } from "./api";
import { Desk } from "./Desk";
import { Login } from "./Login";
import type { Defaults } from "./types";

export function App() {
  const [ready, setReady] = useState(false);
  const [defaults, setDefaults] = useState<Defaults | null>(null);

  async function refresh() {
    const me = await fetchMe();
    setDefaults(me);
    setReady(true);
  }

  useEffect(() => {
    void refresh();
  }, []);

  if (!ready) {
    return (
      <p className="px-6 py-16 text-center font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">
        正在核对会话…
      </p>
    );
  }

  if (!defaults) {
    return <Login onLoggedIn={() => void refresh()} />;
  }

  return (
    <Desk
      defaults={defaults}
      onLogout={() => {
        void logout().then(() => setDefaults(null));
      }}
    />
  );
}
