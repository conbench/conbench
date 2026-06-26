const INTEGER_FORMAT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
  useGrouping: true,
});

const DECIMAL_FORMAT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 20,
  useGrouping: true,
});

/** formatNumber keeps integer benchmark values exact while rendering decimal
 * values compactly enough for dense benchmark tables. */
export function formatNumber(value: number, significantDigits = 4): string {
  if (!Number.isFinite(value)) {
    return String(value);
  }
  if (Number.isInteger(value)) {
    return INTEGER_FORMAT.format(value);
  }
  const rounded = Number(value.toPrecision(significantDigits));
  return Number.isInteger(rounded) ? INTEGER_FORMAT.format(rounded) : DECIMAL_FORMAT.format(rounded);
}

export function formatMeasurement(value: number | null, unit: string | null, missing = "—"): string {
  if (value === null) {
    return missing;
  }
  const text = formatNumber(value);
  return unit === null ? text : `${text} ${unit}`;
}
