export function StatusBadge({
  label,
  tone = "neutral"
}: {
  label: string;
  tone?: "neutral" | "good" | "warning" | "danger";
}) {
  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}

export function SignalBadge({ color }: { color: string }) {
  const tone = color === "green" ? "good" : color === "yellow" ? "warning" : "danger";
  return <StatusBadge label={color} tone={tone} />;
}
