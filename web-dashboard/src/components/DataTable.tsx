export interface Column<T> {
  header: string;
  render(item: T): React.ReactNode;
}

export function DataTable<T>({
  items,
  columns,
  emptyLabel
}: {
  items: T[];
  columns: Column<T>[];
  emptyLabel: string;
}) {
  if (items.length === 0) {
    return <div className="state-panel">{emptyLabel}</div>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.header}>{column.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={index}>{columns.map((column) => <td key={column.header}>{column.render(item)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
