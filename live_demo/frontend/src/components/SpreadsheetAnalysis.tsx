import type { AnalysisResponse } from "../lib/spreadsheets";

/** Quantas colunas listar antes de resumir — a tela nao e a planilha. */
const MAX_COLUNAS = 24;
/** Linhas da previa exibidas. O backend ja limita; aqui e o teto visual. */
const MAX_LINHAS_PREVIA = 12;

interface Props {
  analysis: AnalysisResponse;
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

/**
 * Diagnostico estrutural do arquivo, antes de qualquer validacao.
 *
 * Tudo aqui vem do payload estruturado do backend — nada e extraido do
 * terminal, e nenhum caminho de arquivo do servidor e exibido (o backend
 * envia apenas o NOME).
 */
export default function SpreadsheetAnalysis({ analysis }: Props) {
  const leitura = analysis.analysis.leitura ?? {};
  const estrutura = analysis.analysis.estrutura ?? {};
  const colunas = analysis.analysis.columns ?? [];
  const avisos = analysis.analysis.reader_warnings ?? [];
  const achados = analysis.analysis.findings ?? [];
  const nome = analysis.analysis.metadata?.source_file ?? "arquivo";

  const linhasPrevia = analysis.preview
    ? analysis.preview.split("\n").slice(0, MAX_LINHAS_PREVIA)
    : [];

  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Dado rotulo="Arquivo" valor={nome} />
        <Dado rotulo="Aba" valor={analysis.selected_sheet ?? "—"} />
        <Dado
          rotulo="Cabeçalho"
          valor={
            analysis.header_row !== null ? `linha ${analysis.header_row}` : "—"
          }
        />
        <Dado
          rotulo="Confiança"
          valor={
            typeof leitura.confidence === "number"
              ? `${Math.round(leitura.confidence * 100)}%`
              : "—"
          }
        />
        <Dado rotulo="Linhas" valor={String(estrutura.row_count ?? "—")} />
        <Dado rotulo="Colunas" valor={String(estrutura.column_count ?? "—")} />
      </dl>

      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
          Colunas e tipos observados
        </h4>
        <ul className="flex flex-wrap gap-2">
          {colunas.slice(0, MAX_COLUNAS).map((coluna) => (
            <li
              key={coluna.name}
              className="rounded-lg border border-white/6 bg-ink px-3 py-1.5 text-[0.8rem]"
            >
              <span className="font-semibold text-fg">{coluna.name}</span>
              {coluna.inferred_type ? (
                <span className="ml-2 text-muted">{coluna.inferred_type}</span>
              ) : null}
              {coluna.empty_count ? (
                <span className="ml-2 text-warn">
                  {coluna.empty_count} vazio(s)
                </span>
              ) : null}
            </li>
          ))}
          {colunas.length > MAX_COLUNAS ? (
            <li className="px-2 py-1.5 text-[0.8rem] text-muted">
              e mais {colunas.length - MAX_COLUNAS} coluna(s)
            </li>
          ) : null}
        </ul>
      </div>

      {achados.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Observações da análise
          </h4>
          <ul className="space-y-1.5 text-[0.85rem]">
            {achados.slice(0, 8).map((achado, i) => (
              <li
                key={`${achado.message ?? ""}-${i}`}
                className="rounded-lg border border-white/6 bg-ink px-3 py-2"
              >
                {achado.column ? (
                  <span className="font-semibold text-fg">
                    {achado.column}:{" "}
                  </span>
                ) : null}
                <span className="text-muted">{achado.message}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {avisos.length > 0 ? (
        <ul className="space-y-1.5">
          {avisos.slice(0, 5).map((aviso) => (
            <li
              key={aviso}
              className="rounded-lg border border-warn/40 bg-warn/5 px-3 py-2 text-[0.85rem] text-warn"
            >
              {aviso}
            </li>
          ))}
        </ul>
      ) : null}

      {linhasPrevia.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Prévia (primeiras linhas)
          </h4>
          <div className="max-h-64 overflow-auto rounded-lg border border-white/6 bg-ink">
            <pre className="min-w-full p-3 text-[0.75rem] leading-relaxed text-muted">
              {linhasPrevia.join("\n")}
            </pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}
