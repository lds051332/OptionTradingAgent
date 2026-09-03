import { useEffect, useState } from "react";
import { fetchMe, logout } from "./api";
import { BrandSeal } from "./Brand";
import { Desk } from "./Desk";
import { Home } from "./Home";
import { Login } from "./Login";
import type { Defaults } from "./types";

type View = "home" | "put" | "call";

export function App() {
  const [ready, setReady] = useState(false);
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [view, setView] = useState<View>("home");

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
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6">
        <BrandSeal variant="icon" size="md" alt="摩根大山" />
        <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">正在核对会话…</p>
      </div>
    );
  }

  if (!defaults) {
    return <Login onLoggedIn={() => void refresh()} />;
  }

  if (view === "home") {
    return (
      <Home
        onOpen={setView}
        onLogout={() => {
          setView("home");
          void logout().then(() => setDefaults(null));
        }}
      />
    );
  }

  return (
    <Desk
      defaults={defaults}
      mode={view}
      onBack={() => setView("home")}
      onLogout={() => {
        setView("home");
        void logout().then(() => setDefaults(null));
      }}
    />
  );
}
