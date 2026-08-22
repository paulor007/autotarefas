import {
  ArrowRight,
  Columns3,
  Database,
  FileStack,
  Table2,
} from "lucide-react";

import type { ExtractReport } from "../lib/api";

interface CardProps {
  label: string;
  value: number | string;
  icon: typeof Table2;
}

function SummaryCard({ label, value, icon: Icon }: CardProps) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-white/6 bg-surface p-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cyan/10 text-cyan">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-none text-fg">{value}</div>
        <div className="mt-1 text-[0.7rem] uppercase tracking-wider text-muted">
          {label}
        </div>
      </div>
    </div>
  );
}

export default function ExtractSummary({
  report,
  onNextStep,
}: {
  report: ExtractReport;
  onNextStep?: () => void;
}) {
  const paginas = report.paginas ?? "-";

  return (
    <div className="mx-auto mb-8 max-w-3xl space-y-4">
      {/* Banner: origem dos dados (a Exportacao e a origem do pipeline) */}
      <div className="flex items-start gap-3 rounded-xl border border-cyan/20 bg-cyan/6 px-4 py-3">
        <Database className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
        <p className="min-w-0 text-sm text-muted">
          <span className="font-semibold text-fg">Origem:</span> dados extraídos
          direto de{" "}
          <span className="break-all font-mono text-fg">{report.origem}</span> e
          montados numa planilha organizada, pronta para o próximo passo.
        </p>
      </div>

      {/* Cards do resumo */}
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard
          label="Registros"
          value={report.total_registros}
          icon={Table2}
        />
        <SummaryCard label="Páginas" value={paginas} icon={FileStack} />
        <SummaryCard
          label="Colunas"
          value={report.colunas.length}
          icon={Columns3}
        />
      </div>

      {/* Colunas extraidas */}
      {report.colunas.length > 0 && (
        <div className="rounded-xl border border-white/6 bg-surface p-4">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">
            Colunas extraídas
          </div>
          <div className="flex flex-wrap gap-2">
            {report.colunas.map((coluna) => (
              <span
                key={coluna}
                className="inline-flex items-center rounded-full border border-white/8 bg-ink px-3 py-1 font-mono text-xs text-fg"
              >
                {coluna}
              </span>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">
            A base completa está em{" "}
            <span className="font-mono text-fg">dados_extraidos.csv</span> e{" "}
            <span className="font-mono text-fg">dados_extraidos.xlsx</span>.
          </p>
        </div>
      )}

      {/* CTA: proximo passo do pipeline (Exportacao -> Auditoria) */}
      {onNextStep && report.total_registros > 0 && (
        <button
          type="button"
          onClick={onNextStep}
          className="group flex w-full items-center justify-between gap-3 rounded-xl border border-cyan/30 bg-cyan/6 px-4 py-3 text-left transition-colors hover:bg-cyan/10"
        >
          <span className="text-sm text-fg">
            <span className="font-semibold">Próximo passo:</span> Auditoria de
            planilha — validar e limpar essa base antes de usar
          </span>
          <ArrowRight className="h-4 w-4 shrink-0 text-cyan transition-transform group-hover:translate-x-0.5" />
        </button>
      )}
    </div>
  );
}
