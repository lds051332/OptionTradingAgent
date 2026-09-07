import { useEffect, useState } from "react";
import { fetchMe, logout } from "./api";
import { BrandSeal } from "./Brand";
import { Desk } from "./Desk";
import { Home } from "./Home";
import { Login } from "./Login";
import { PageFrame } from "./PageFrame";
import { useRouter } from "./router";
import type { Defaults } from "./types";

const PAGE_TITLE: Record<string, string> = {
  "/": "摩根大山 · Option Desk",
  "/put": "卖 Put 决策台 · 摩根大山",
  "/call": "卖 Call 决策台 · 摩根大山",
};

export function App() {
  const { path, navigate } = useRouter();
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

  useEffect(() => {
    document.title = PAGE_TITLE[path] ?? PAGE_TITLE["/"];
  }, [path]);

  useEffect(() => {
    if (path !== "/" && path !== "/put" && path !== "/call") {
      navigate("/", { replace: true });
    }
  }, [path, navigate]);

  function handleLogout() {
    navigate("/", { replace: true });
    void logout().then(() => setDefaults(null));
  }

  if (!ready) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6">
        <BrandSeal variant="icon" size="md" alt="摩根大山" />
        <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">正在核对会话…</p>
      </div>
    );
  }

  const page = !defaults ? (
    <Login onLoggedIn={() => void refresh()} />
  ) : path === "/put" || path === "/call" ? (
    <Desk defaults={defaults} mode={path.slice(1) as "put" | "call"} onLogout={handleLogout} />
  ) : (
    <Home onLogout={handleLogout} />
  );

  return <PageFrame>{page}</PageFrame>;
}
