export default function RadarBadge({ status }) {
  if (!status) return null;
  const isTrigger = status.status === "TRIGGER";
  return (
    <span className={
      isTrigger
        ? "rounded-full px-2 py-0.5 text-[10px] font-bold bg-red-500/20 text-red-400"
        : "rounded-full px-2 py-0.5 text-[10px] font-medium bg-card text-muted border border-lineStrong"
    }>
      {isTrigger ? "🚨 PUMP" : "idle"}
    </span>
  );
}
