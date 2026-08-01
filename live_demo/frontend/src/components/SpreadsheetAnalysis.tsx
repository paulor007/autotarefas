import type { AnalysisReport } from "../lib/spreadsheets";

/** Quantas colunas listar antes de resumir — a tela nao e a planilha. */
const MAX_COLUNAS = 24;
/** Linhas da previa exibidas. O backend ja limita; aqui e o teto visual. */
const MAX_LINHAS_PREVIA = 12;
/** Achados e avisos mostrados; o resto fica nos artefatos. */
const MAX_NOTAS = 8;

interface Props {
  /** Relatorio JA NORMALIZADO (ver `parseAnalysis`). */
  report: AnalysisReport;
  /** Previa textual da planilha, como o backend a produziu. */
  preview: string;
}

function Dado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-lg border border-white/6 bg-ink p-3">
      <dt className="text-[0.68rem] uppercase tracking-wider text-muted">
        {rotulo}
      </dt>
      <dd className="mt-1 text-[0.9rem] font-semibold text-fg">{valor}</dd>
    </div>
  );
}

function porcentagem(valor: number | null): string {
  return valor === null ? "—" : `${Math.round(valor * 100)}%`;
}

/**
 * Diagnostico estrutural do arquivo, antes de qualquer validacao.
 *
 * Recebe o relatorio JA NORMALIZADO: todo array existe e todo campo exibido e
 * primitivo. Antes desta correcao o componente recebia o JSON cru e renderizava
 * `reader_warnings` — que sao OBJETOS — como filho React, o que lancava
 * "Objects are not valid as a React child" e apagava a aplicacao inteira.
 */
export default function SpreadsheetAnalysis({ report, preview }: Props) {
  const linhasPrevia = preview
    ? preview.split("\n").slice(0, MAX_LINHAS_PREVIA)
    : [];

  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Dado rotulo="Arquivo" valor={report.source_file} />
        <Dado rotulo="Aba" valor={report.selected_sheet ?? "—"} />
        <Dado
          rotulo="Cabeçalho"
          valor={
            report.header_row !== null ? `linha ${report.header_row}` : "—"
          }
        />
        <Dado rotulo="Confiança" valor={porcentagem(report.confidence)} />
        <Dado
          rotulo="Linhas"
          valor={report.row_count !== null ? String(report.row_count) : "—"}
        />
        <Dado
          rotulo="Colunas"
          valor={
            report.column_count !== null ? String(report.column_count) : "—"
          }
        />
      </dl>

      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
          Colunas e tipos observados
        </h4>
        <ul className="flex flex-wrap gap-2">
          {report.columns.slice(0, MAX_COLUNAS).map((coluna) => (
            <li
              key={coluna.name}
              className="rounded-lg border border-white/6 bg-ink px-3 py-1.5 text-[0.8rem]"
            >
              <span className="font-semibold text-fg">{coluna.name}</span>
              {coluna.inferred_type ? (
                <span className="ml-2 text-muted">{coluna.inferred_type}</span>
              ) : null}
              {coluna.empty_count > 0 ? (
                <span className="ml-2 text-warn">
                  {coluna.empty_count} vazio(s)
                </span>
              ) : null}
            </li>
          ))}
          {report.columns.length > MAX_COLUNAS ? (
            <li className="px-2 py-1.5 text-[0.8rem] text-muted">
              e mais {report.columns.length - MAX_COLUNAS} coluna(s)
            </li>
          ) : null}
        </ul>
      </div>

      {report.findings.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Observações da análise
          </h4>
          <ul className="space-y-1.5 text-[0.85rem]">
            {report.findings.slice(0, MAX_NOTAS).map((achado, i) => (
              <li
                key={`${achado.code ?? "achado"}-${i}`}
                className="rounded-lg border border-white/6 bg-ink px-3 py-2"
              >
                {achado.column ? (
                  <span className="font-semibold text-fg">
                    {achado.column}:{" "}
                  </span>
                ) : null}
                {/* `message` e sempre texto apos a normalizacao */}
                <span className="text-muted">{achado.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.reader_warnings.length > 0 ? (
        <ul className="space-y-1.5">
          {report.reader_warnings.slice(0, MAX_NOTAS).map((aviso, i) => (
            <li
              key={`${aviso.code ?? "aviso"}-${i}`}
              className="rounded-lg border border-warn/40 bg-warn/5 px-3 py-2 text-[0.85rem] text-warn"
            >
              {aviso.message}
            </li>
          ))}
        </ul>
      ) : null}

      {linhasPrevia.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Prévia (primeiras linhas)
          </h4>
          <div className="max-h-64 overflow-auto rounded-lg border border-white/6">
            <pre className="min-w-full p-3 text-[0.75rem] leading-relaxed text-muted">
              {linhasPrevia.join("\n")}
            </pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}
