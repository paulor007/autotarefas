import { useEffect, useRef, useState } from "react";
import { Check, Copy, Loader2, Trash2 } from "lucide-react";

import type { RunStatus } from "../hooks/useExecution";
import SectionHeader from "./SectionHeader";

export type LineKind =
  | "command"
  | "info"
  | "warn"
  | "ok"
  | "error"
  | "done"
  | "plain";

export interface TerminalLine {
  kind: LineKind;
  text: string;
}

const COLOR: Record<LineKind, string> = {
  command: "text-fg",
  info: "text-cyan",
  warn: "text-signal",
  ok: "text-ok",
  error: "text-danger",
  done: "text-cyan",
  plain: "text-muted",
};

// O badge reflete o resultado real: o backend emite "done" para qualquer
// termino, e o outcome (ok | caught_issue | error) diz se foi sucesso, aviso
// ou erro. Assim nao mostramos "concluido" em verde quando houve problema.
function badgeFor(
  status: RunStatus,
  outcome?: string,
): { text: string; cls: string } | null {
  switch (status) {
    case "starting":
      return { text: "iniciando", cls: "text-signal" };
    case "running":
      return { text: "executando", cls: "text-signal" };
    case "timeout":
      return { text: "timeout", cls: "text-danger" };
    case "error":
      return { text: "erro", cls: "text-danger" };
    case "done":
      if (outcome === "caught_issue")
        return { text: "concluído · com avisos", cls: "text-signal" };
      if (outcome === "error")
        return { text: "concluído · com erros", cls: "text-danger" };
      return { text: "concluído", cls: "text-ok" };
    default:
      return null;
  }
}

interface Props {
  lines: TerminalLine[];
  status: RunStatus;
  outcome?: string;
  sample?: boolean;
  onClear?: () => void;
}

export default function TerminalView({
  lines,
  status,
  outcome,
  sample = false,
  onClear,
}: Props) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [lines]);

  const handleCopy = async () => {
    const text = lines
      .map((l) => (l.kind === "command" ? `$ ${l.text}` : l.text))
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* area de transferencia indisponivel */
    }
  };

  const busy = status === "starting" || status === "running";
  const canClear = !!onClear && !busy && lines.length > 0;
  const badge = badgeFor(status, outcome);
  const showCursor = status === "idle" || busy;

  return (
    <section id="terminal" className="py-20">
      <div className="container-page">
        <SectionHeader
          title="Terminal ao Vivo"
          subtitle="Saída em tempo real da execução no sandbox"
        />

        <div className="overflow-hidden rounded-2xl border border-white/6 bg-terminal shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
          {/* Header estilo macOS */}
          <div className="flex items-center border-b border-white/6 bg-white/2 px-4 py-3">
            <div className="mr-4 flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-danger" />
              <span className="h-2.5 w-2.5 rounded-full bg-signal" />
              <span className="h-2.5 w-2.5 rounded-full bg-ok" />
            </div>
            <span className="grow font-mono text-xs text-muted">
              autotarefas@sandbox:~
            </span>

            {busy ? (
              <span className="mr-3 inline-flex items-center gap-1.5 font-mono text-[0.65rem] text-signal">
                <Loader2 className="h-3 w-3 animate-spin" />
                {badge?.text}
              </span>
            ) : (
              badge && (
                <span
                  className={`mr-3 font-mono text-[0.65rem] uppercase tracking-wider ${badge.cls}`}
                >
                  {badge.text}
                </span>
              )
            )}

            {sample && status === "idle" && (
              <span className="mr-3 rounded bg-white/5 px-2 py-0.5 font-mono text-[0.6rem] uppercase tracking-wider text-muted">
                saída de exemplo
              </span>
            )}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copiar saída do terminal"
                className="rounded p-1 text-muted transition-colors hover:bg-white/5 hover:text-fg"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-ok" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>
              <button
                type="button"
                onClick={() => onClear?.()}
                disabled={!canClear}
                aria-label="Limpar terminal"
                className={`rounded p-1 transition-colors ${
                  canClear
                    ? "text-muted hover:bg-white/5 hover:text-fg"
                    : "cursor-not-allowed text-muted/40"
                }`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Corpo */}
          <div
            ref={bodyRef}
            className="max-h-100 min-h-70 overflow-y-auto p-5 font-mono text-[0.8rem] leading-[1.9]"
          >
            {lines.length === 0 && !busy && (
              <div className="text-muted">
                Selecione uma automação e execute para ver o stdout real aqui.
              </div>
            )}
            {lines.map((line, i) => (
              <div key={i} className="flex items-baseline gap-2">
                {line.kind === "command" ? (
                  <>
                    <span className="select-none font-semibold text-ok">$</span>
                    <span className="font-medium text-fg">{line.text}</span>
                  </>
                ) : (
                  <span
                    className={`whitespace-pre-wrap wrap-break-word ${COLOR[line.kind]}`}
                  >
                    {line.text}
                  </span>
                )}
              </div>
            ))}
            {showCursor && (
              <div className="flex items-baseline gap-2">
                <span className="select-none font-semibold text-ok">$</span>
                <span className="animate-blink text-ok">_</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
