import type { Automation } from "../lib/api";

const OUTPUT_LABEL: Record<string, string> = {
  report: "relatório",
  zip: "arquivo .zip",
  file: "arquivo",
  html: "painel html",
};

const UPLOAD_LABEL: Record<string, string> = {
  csv: "envia .csv",
  folder: "envia arquivos",
  none: "sem upload",
};

export default function AutomationCard({
  automation,
  active,
}: {
  automation: Automation;
  active: boolean;
}) {
  return (
    <article
      className={[
        "group relative flex flex-col rounded-lg border bg-surface p-5 transition-colors",
        active
          ? "border-line hover:border-signal/50 hover:bg-surface-2"
          : "border-line/60 opacity-60",
      ].join(" ")}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <h3 className="font-display text-base font-semibold text-text">
          {automation.title}
        </h3>
        {active ? (
          <span className="shrink-0 rounded-full border border-signal/40 bg-signal/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-signal">
            ativo
          </span>
        ) : (
          <span className="shrink-0 rounded-full border border-line-strong px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-text-dim">
            em breve
          </span>
        )}
      </div>

      <p className="mb-1 font-mono text-xs text-cyan/80">
        {automation.subtitle}
      </p>
      <p className="mb-4 text-sm leading-relaxed text-text-muted">
        {automation.description}
      </p>

      <div className="mt-auto border-t border-line/70 pt-3">
        <code className="font-mono text-xs text-text-dim">
          $ autotarefas {automation.id.replace("_", " ")}
        </code>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 font-mono text-[10px] text-text-dim">
        <span className="rounded border border-line px-1.5 py-0.5">
          {UPLOAD_LABEL[automation.upload]}
        </span>
        <span className="rounded border border-line px-1.5 py-0.5">
          {OUTPUT_LABEL[automation.output]}
        </span>
        {automation.requires_browser && (
          <span className="rounded border border-line px-1.5 py-0.5">
            usa navegador
          </span>
        )}
      </div>
    </article>
  );
}
