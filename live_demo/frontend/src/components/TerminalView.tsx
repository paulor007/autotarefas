import { useEffect, useRef, useState } from "react";
import { Check, Copy, Trash2 } from "lucide-react";

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

const LABEL: Partial<Record<LineKind, string>> = {
  info: "[INFO]",
  warn: "[WARN]",
  ok: "[OK]",
  error: "[ERROR]",
  done: "[DONE]",
};

const COLOR: Record<LineKind, string> = {
  command: "text-fg",
  info: "text-cyan",
  warn: "text-signal",
  ok: "text-ok",
  error: "text-danger",
  done: "text-cyan",
  plain: "text-muted",
};

interface Props {
  lines: TerminalLine[];
  sample?: boolean;
}

export default function TerminalView({ lines, sample = false }: Props) {
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

  return (
    <section id="terminal" className="py-20">
      <div className="container-page">
        <SectionHeader
          title="Terminal ao Vivo"
          subtitle="Saída em tempo real da execução no sandbox"
        />

        <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-terminal shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
          {/* Header estilo macOS */}
          <div className="flex items-center border-b border-white/[0.06] bg-white/[0.02] px-4 py-3">
            <div className="mr-4 flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-danger" />
              <span className="h-2.5 w-2.5 rounded-full bg-signal" />
              <span className="h-2.5 w-2.5 rounded-full bg-ok" />
            </div>
            <span className="flex-grow font-mono text-xs text-muted">
              autotarefas@sandbox:~
            </span>
            {sample && (
              <span className="mr-3 rounded bg-white/[0.05] px-2 py-0.5 font-mono text-[0.6rem] uppercase tracking-wider text-muted">
                saída de exemplo
              </span>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCopy}
                aria-label="Copiar saída do terminal"
                className="rounded p-1 text-muted transition-colors hover:bg-white/[0.05] hover:text-fg"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-ok" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </button>
              <button
                type="button"
                disabled
                aria-label="Limpar terminal (disponível no Front-2)"
                className="cursor-not-allowed rounded p-1 text-muted/40"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Corpo */}
          <div
            ref={bodyRef}
            className="max-h-[400px] min-h-[280px] overflow-y-auto p-5 font-mono text-[0.8rem] leading-[1.9]"
          >
            {lines.map((line, i) => (
              <div key={i} className="flex items-baseline gap-2">
                {line.kind === "command" ? (
                  <>
                    <span className="select-none font-semibold text-ok">$</span>
                    <span className="font-medium text-fg">{line.text}</span>
                  </>
                ) : line.kind === "plain" ? (
                  <span className="text-muted">{line.text}</span>
                ) : (
                  <>
                    <span className={`font-semibold ${COLOR[line.kind]}`}>
                      {LABEL[line.kind]}
                    </span>
                    <span className="text-muted">{line.text}</span>
                  </>
                )}
              </div>
            ))}
            <div className="flex items-baseline gap-2">
              <span className="select-none font-semibold text-ok">$</span>
              <span className="animate-blink text-ok">_</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
