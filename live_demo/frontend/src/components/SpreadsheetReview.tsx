import type { AnalysisReport, SchemaSummary } from "../lib/spreadsheets";
import SpreadsheetSchemaSummary from "./SpreadsheetSchemaSummary";

interface Props {
  report: AnalysisReport;
  summary: SchemaSummary;
  origin: "suggested" | "uploaded";
  origem: "exemplo" | "upload";
  busy: boolean;
  onValidate: () => void;
  onBack: () => void;
}

/**
 * Ultima parada antes de executar.
 *
 * A validacao NAO comeca sozinha depois que o schema e confirmado: quem
 * decide executar e a pessoa, depois de ver o que sera aplicado.
 */
export default function SpreadsheetReview({
  report,
  summary,
  origin,
  origem,
  busy,
  onValidate,
  onBack,
}: Props) {
  const linhas = report.row_count !== null ? String(report.row_count) : "—";
  const colunas =
    report.column_count !== null ? String(report.column_count) : "—";

  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {[
          ["Arquivo", report.source_file],
          ["Origem", origem === "exemplo" ? "exemplo" : "arquivo enviado"],
          ["Aba", report.selected_sheet ?? "—"],
          [
            "Cabeçalho",
            report.header_row !== null ? `linha ${report.header_row}` : "—",
          ],
          ["Linhas", linhas],
          ["Colunas", colunas],
        ].map(([rotulo, valor]) => (
          <div
            key={rotulo}
            className="rounded-lg border border-white/6 bg-ink p-3"
          >
            <dt className="text-[0.68rem] uppercase tracking-wider text-muted">
              {rotulo}
            </dt>
            <dd className="mt-1 text-[0.9rem] font-semibold text-fg">
              {valor}
            </dd>
          </div>
        ))}
      </dl>

      <SpreadsheetSchemaSummary summary={summary} origin={origin} />

      <p className="rounded-lg border border-white/6 bg-ink px-4 py-3 text-[0.85rem] text-muted">
        O arquivo original não é alterado. A validação trabalha sobre uma cópia
        em um espaço temporário e produz arquivos novos.
      </p>

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onValidate}
          disabled={busy}
          className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Iniciando…" : "Executar validação"}
        </button>
        <button
          type="button"
          onClick={onBack}
          disabled={busy}
          className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
        >
          Trocar o schema
        </button>
      </div>
    </div>
  );
}
