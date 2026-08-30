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

/**
 * Tamanho legível, escolhendo a unidade pelo valor.
 *
 * Existia duas vezes, e uma das cópias arredondava tudo para MB: um pacote de
 * 1,8 KB aparecia como "0.0 MB" ao lado da mesma informação escrita como "1.8
 * KB" três linhas acima. Duas respostas para a mesma pergunta, na mesma tela.
 */
export function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
