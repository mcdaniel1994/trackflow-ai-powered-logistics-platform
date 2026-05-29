export function CharacterCounter({
  value,
  remainingLabel,
  overLimitLabel,
}: {
  value: string;
  remainingLabel: string;
  overLimitLabel: string;
}) {
  const remaining = 500 - value.length;
  const isOverLimit = remaining < 0;

  return (
    <span
      className={`text-xs ${isOverLimit ? "text-red-700" : "text-neutral-500"}`}
      aria-live="polite"
    >
      {isOverLimit
        ? `${Math.abs(remaining)} ${overLimitLabel}`
        : `${remaining} ${remainingLabel}`}
    </span>
  );
}
