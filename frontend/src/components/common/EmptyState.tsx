interface Props {
  title: string;
  detail?: string;
  action?: React.ReactNode;
}

export default function EmptyState({ title, detail, action }: Props) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {detail ? <p>{detail}</p> : null}
      {action}
    </div>
  );
}
