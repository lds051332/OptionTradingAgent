import { login } from "./api";
import { useState, type FormEvent } from "react";
import { BrandSeal } from "./Brand";

type Props = {
  onLoggedIn: () => void;
};

export function Login({ onLoggedIn }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-5 py-10">
      <BrandSeal variant="mark" size="lg" className="mx-auto" alt="摩根大山" />
      <h1 className="mt-5 text-center font-[family-name:var(--font-display)] text-[2.35rem] leading-none tracking-[0.18em] text-[var(--chalk)]">
        摩根大山
      </h1>
      <p className="mt-3 text-center font-[family-name:var(--font-mono)] text-[11px] tracking-[0.32em] text-[var(--brass)] uppercase">
        Option Desk
      </p>
      <p className="mt-4 text-center text-[15px] leading-relaxed text-[var(--mute)]">
        短周期美股轮式决策台：持币卖 put，持股卖 call。输入口令进入，分析过程会逐步摊开，不下单。
      </p>
      <form onSubmit={onSubmit} className="ticket mt-8 px-6 py-6 pl-8">
        <label htmlFor="password" className="block text-sm text-[var(--mute)]">
          共享口令
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 text-[var(--chalk)]"
        />
        {error ? <p className="mt-3 text-sm text-[var(--skip)]">{error}</p> : null}
        <button
          type="submit"
          disabled={busy || !password}
          className="mt-5 min-h-11 w-full rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)] disabled:opacity-50"
        >
          {busy ? "核对中…" : "进入决策台"}
        </button>
      </form>
    </main>
  );
}
