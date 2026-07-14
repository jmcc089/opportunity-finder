interface FieldRowProps {
  label: string;
  value: string | number;
  fieldKey: string;
  estimatedFields: string[];
}

export function FieldRow({ label, value, fieldKey, estimatedFields }: FieldRowProps) {
  const isEstimate = estimatedFields.includes(fieldKey);
  // No real/estimate marker when there's no value to qualify.
  const hasValue = value !== '—' && value !== '' && value != null;

  return (
    <div className="flex items-center justify-between py-1.5 border-b border-sage-line last:border-0">
      <span className="text-ink-soft text-sm">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className="text-ink text-sm font-medium">{value}</span>
        {!hasValue ? null : isEstimate ? (
          <span className="flex items-center gap-0.5 text-xs text-muted">
            <span>✦</span>
            <span>estimate</span>
          </span>
        ) : (
          <span className="flex items-center gap-0.5 text-xs text-sage-mid">
            <span>✓</span>
            <span>real</span>
          </span>
        )}
      </div>
    </div>
  );
}
