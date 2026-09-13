export function roundMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

export function realizedOptionPnl(
  entryPremium: number,
  closePrice: number,
  contracts: number,
  fees = 0,
): number {
  return roundMoney((entryPremium - closePrice) * contracts * 100 - fees);
}

export function markOptionPnl(entryPremium: number, mark: number, contracts: number): number {
  return roundMoney((entryPremium - mark) * contracts * 100);
}

export function profitCapture(entryPremium: number, mark: number): number | null {
  if (entryPremium <= 0) return null;
  return (entryPremium - mark) / entryPremium;
}
