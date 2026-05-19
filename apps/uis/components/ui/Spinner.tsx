// Inline spinner used wherever the UI needs to say "this specific thing is loading":
// the table header during refetch, the status/stage selects while saving, the
// submit button on the form. We pair the spinning ring with a visible text
// label so screen readers (and users on slow connections) know what's happening.
// `aria-hidden` on the ring stops it being announced — the label carries that.

type SpinnerProps = {
  label?: string;
  className?: string;
};

export function Spinner({ label = "Loading", className = "" }: SpinnerProps) {
  return (
    <span className={`inline-flex items-center gap-2 text-sm text-neutral-700 ${className}`.trim()}>
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-coral"
        aria-hidden="true"
      />
      <span>{label}</span>
    </span>
  );
}
