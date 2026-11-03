// Small coloured label: Reorder Now = red, Low = orange, OK = green, Stock not entered = grey
export default function StatusBadge({ status }) {
  let badgeClass = "badge grey";
  if (status === "Reorder Now") {
    badgeClass = "badge red";
  } else if (status === "Low") {
    badgeClass = "badge orange";
  } else if (status === "OK") {
    badgeClass = "badge green";
  }
  return <span className={badgeClass}>{status}</span>;
}
