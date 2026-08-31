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

/**
 * Há quanto tempo, em palavras.
 *
 * "30/08/2026, 22:17" obriga quem lê a fazer a conta com o relógio para
 * responder a única pergunta que importa ali: *isto está vivo agora?*. "há 12
 * segundos" responde direto.
 *
 * Cai para a data absoluta quando o intervalo passa de um dia: "há 37 dias" é
 * pior do que a data, porque a pessoa perde a referência de quando foi.
 */
export function desdeQuando(bruto: string, agora: Date = new Date()): string {
  if (!bruto) return "sem contato";
  const data = new Date(bruto);
  if (Number.isNaN(data.getTime())) return bruto;

  const segundos = Math.floor((agora.getTime() - data.getTime()) / 1000);
  // Relógios diferentes produzem futuro por alguns segundos. "há -3 segundos"
  // seria pior do que arredondar para agora.
  if (segundos < 45) return "agora há pouco";
  if (segundos < 90) return "há 1 minuto";
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) return `há ${minutos} minutos`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `há ${horas} ${horas === 1 ? "hora" : "horas"}`;
  return quando(bruto);
}
