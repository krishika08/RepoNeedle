// Formatting helpers.
// function fakeCommentFn() { notCalled(); }
export function formatPrice(amount: number): string {
  return "€" + round(amount).toFixed(2);
}

export function round(value: number): number {
  return Math.round(value * 100) / 100;
}

export const label = (name: string): string => `item: ${name}()`;
