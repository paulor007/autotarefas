import type { LineKind, TerminalLine } from "../components/TerminalView";

// Infere a cor a partir do proprio stdout do AutoTarefas (prefixos reais).
// Nao inventa nada: apenas classifica a linha que veio do backend via SSE.
export function classifyLine(text: string): TerminalLine {
  const t = text.trimStart();
  let kind: LineKind = "plain";
  if (/^\[(ERROR|ERRO|FALHA)\]/i.test(t) || /\|\s*ERROR\s*\|/i.test(t)) {
    kind = "error";
  } else if (/^\[(OK|SUCESSO)\]/i.test(t)) {
    kind = "ok";
  } else if (
    /^\[(WARN|AVISO)\]/i.test(t) ||
    /\|\s*WARN(?:ING)?\s*\|/i.test(t)
  ) {
    kind = "warn";
  } else if (/^\[INFO\]/i.test(t) || /\|\s*INFO\s*\|/i.test(t)) {
    kind = "info";
  } else if (/^\[DONE\]/i.test(t)) {
    kind = "done";
  }
  return { kind, text };
}
