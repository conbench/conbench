export function compactAxisValue(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) {
    return `${trimFixed(value / 1_000_000_000, 1)}B`;
  }
  if (abs >= 1_000_000) {
    return `${trimFixed(value / 1_000_000, 0)}M`;
  }
  if (abs >= 1_000) {
    return `${trimFixed(value / 1_000, 0)}k`;
  }
  if (abs > 0 && abs < 0.1) {
    return trimFixed(value, 3);
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return trimFixed(value, 1);
}

function trimFixed(value: number, fractionDigits: number): string {
  return value
    .toFixed(fractionDigits)
    .replace(/\.0+$/, "")
    .replace(/(\.\d*?)0+$/, "$1");
}
