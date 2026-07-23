export function StatCard({
  label,
  value,
  detail
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <section className="stat-card" aria-label={label}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </section>
  );
}
