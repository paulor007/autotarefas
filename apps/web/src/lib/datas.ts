/** Data legível, ou o texto cru quando não dá para interpretar. */
export function quando(bruto: string): string {
  if (!bruto) return "sem data";
  const data = new Date(bruto);
  if (Number.isNaN(data.getTime())) return bruto;
  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
