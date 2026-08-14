import type {
  AnalysisReport,
  SchemaOrigin,
  SchemaSummary,
} from "../lib/spreadsheets";
import SpreadsheetSchemaSummary from "./SpreadsheetSchemaSummary";

interface Props {
  report: AnalysisReport;
  summary: SchemaSummary;
  origin: SchemaOrigin;
  origem: "exemplo" | "upload";
  busy: boolean;
  /** Correcoes seguras confirmadas pela pessoa (desligado por padrao). */
  applyCleaning: boolean;
  onApplyCleaningChange: (value: boolean) => void;
  /** Linhas 100% repetidas encontradas na analise (0 = nenhuma). */
  duplicateRows: number;
  flagDuplicateRows: boolean;
  onFlagDuplicateRowsChange: (value: boolean) => void;
  onValidate: () => void;
  onBack: () => void;
}

/** Extensoes em que a apresentacao original pode ser preservada. */
const PRESERVAVEIS = [".xlsx", ".xlsm"];

function preservaApresentacao(nomeArquivo: string): boolean {
  const nome = nomeArquivo.toLowerCase();
  return PRESERVAVEIS.some((ext) => nome.endsWith(ext));
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
  applyCleaning,
  onApplyCleaningChange,
  duplicateRows,
  flagDuplicateRows,
  onFlagDuplicateRowsChange,
  onValidate,
  onBack,
}: Props) {
  const linhas = report.row_count !== null ? String(report.row_count) : "—";
  const colunas =
    report.column_count !== null ? String(report.column_count) : "—";
  const preserva = preservaApresentacao(report.source_file);

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

      <div className="rounded-lg border border-white/6 bg-ink p-4">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={applyCleaning}
            disabled={busy}
            onChange={(e) => onApplyCleaningChange(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-signal"
          />
          <span>
            <span className="block text-[0.9rem] font-semibold text-fg">
              Aplicar as correções seguras
            </span>
            <span className="mt-1 block text-[0.85rem] text-muted">
              Espaços sobrando, caixa de e-mail e formatos reconhecidos são
              normalizados — cada valor alterado aparece no antes/depois. Nada
              ambíguo é decidido: o que depende de julgamento continua indo para
              a lista de revisão.
            </span>
          </span>
        </label>

        {applyCleaning && (
          <p className="mt-3 rounded-lg border border-white/6 bg-panel px-3 py-2 text-[0.82rem] text-muted">
            {preserva
              ? "Você vai receber também a planilha tratada, partindo do seu arquivo original: cores, larguras, filtros, painéis congelados e fórmulas não tocadas continuam como estão."
              : "Arquivos CSV não têm formatação para preservar — o resultado sai nos artefatos em CSV e na planilha de relatório."}
          </p>
        )}
      </div>

      {duplicateRows > 0 && (
        <div className="rounded-lg border border-warn/30 bg-warn/[0.05] p-4">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={flagDuplicateRows}
              disabled={busy}
              onChange={(e) => onFlagDuplicateRowsChange(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-signal"
            />
            <span>
              <span className="block text-[0.9rem] font-semibold text-fg">
                Sinalizar as {duplicateRows} linha(s) repetida(s) para revisão
              </span>
              <span className="mt-1 block text-[0.85rem] text-muted">
                A leitura encontrou {duplicateRows} linha(s) idêntica(s) a
                outra, envolvendo {duplicateRows * 2} linha(s) no total (a
                primeira de cada par é tratada como o registro original).
                Nenhuma é removida: elas entram no relatório com o número da
                linha, para alguém decidir.
              </span>
              <span className="mt-2 block text-[0.8rem] text-muted">
                Isso é diferente de <strong>chave repetida</strong>: numa
                planilha de vendas o mesmo código aparece uma vez por item da
                venda, e isso é esperado — só a linha inteira repetida é
                sinalizada.
              </span>
            </span>
          </label>
        </div>
      )}

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
