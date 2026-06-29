import type { Automation } from "../lib/api";
import { iconFor } from "../lib/icons";

const UPLOAD_LABEL: Record<string, string> = {
  csv: "CSV",
  folder: "Arquivos",
  none: "Sem upload",
};
const OUTPUT_LABEL: Record<string, string> = {
  report: "Relatório JSON",
  zip: "ZIP",
  file: "Arquivo",
  html: "Painel HTML",
};

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[0.65rem] uppercase tracking-wider text-muted">
        {label}
      </span>
      <span className="text-xs font-medium text-fg">{value}</span>
    </div>
  );
}

interface Props {
  automation: Automation;
  active: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
}

export default function AutomationCard({
  automation,
  active,
  selected,
  onSelect,
}: Props) {
  const Icon = iconFor(automation.id);

  if (!active) {
    return (
      <div className="flex flex-col gap-3 rounded-2xl border border-white/[0.06] bg-surface p-6 opacity-40">
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-white/[0.05] text-muted">
            <Icon className="h-5 w-5" />
          </div>
          <span className="rounded bg-white/[0.05] px-2 py-0.5 text-[0.68rem] font-semibold uppercase tracking-wide text-muted">
            Em breve
          </span>
        </div>
        <h3 className="text-[1.02rem] font-semibold">{automation.title}</h3>
        <p className="text-sm leading-relaxed text-muted">
          {automation.description}
        </p>
      </div>
    );
  }

  return (
    <div
      className={`group flex flex-col gap-3 rounded-2xl border bg-surface p-6 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_32px_rgba(0,0,0,0.3)] ${
        selected
          ? "border-signal shadow-[0_0_20px_rgba(240,177,0,0.2)]"
          : "border-white/[0.06] hover:border-signal/30"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-signal/10 text-signal">
          <Icon className="h-5 w-5" />
        </div>
        <span className="rounded bg-ok/10 px-2 py-0.5 text-[0.68rem] font-semibold uppercase tracking-wide text-ok">
          Ativo
        </span>
      </div>
      <h3 className="text-[1.02rem] font-semibold">{automation.title}</h3>
      <p className="flex-grow text-sm leading-relaxed text-muted">
        {automation.description}
      </p>
      <div className="flex gap-4 border-t border-white/[0.06] pt-3">
        <Field
          label="Entrada"
          value={UPLOAD_LABEL[automation.upload] ?? automation.upload}
        />
        <Field
          label="Saída"
          value={OUTPUT_LABEL[automation.output] ?? automation.output}
        />
      </div>
      <button
        type="button"
        onClick={() => onSelect(automation.id)}
        aria-pressed={selected}
        className={`mt-1 w-full rounded-lg border px-4 py-2 text-sm font-semibold transition-all ${
          selected
            ? "border-signal bg-signal text-black hover:bg-amber-400"
            : "border-signal/30 text-signal hover:bg-signal/10"
        }`}
      >
        {selected ? "Selecionado" : "Selecionar"}
      </button>
    </div>
  );
}
