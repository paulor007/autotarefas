import type { AnalysisReport, PresentationAudit } from "../lib/spreadsheets";

interface Props {
  report: AnalysisReport;
  origem: "exemplo" | "upload";
  busy: boolean;
  /** Avaliação objetiva da apresentação (null em CSV). */
  presentation: PresentationAudit | null;
  /** Colunas disponíveis para ordenação e para os papéis do resumo. */
  columns: string[];
  duplicateRows: number;

  applyCleaning: boolean;
  onApplyCleaningChange: (value: boolean) => void;
  organize: boolean;
  onOrganizeChange: (value: boolean) => void;
  sortColumn: string;
  sortDesc: boolean;
  onSortChange: (column: string, desc: boolean) => void;
  /** Resumo só é oferecido quando o significado das colunas está claro. */
  canSummarize: boolean;
  suggestion: { valor: string; categoria: string; data: string };
  indicators: { valor: string; categoria: string; data: string };
  onIndicatorsChange: (value: {
    valor: string;
    categoria: string;
    data: string;
  }) => void;
  /** Aba de painel dentro da planilha organizada. */
  dashboard: boolean;
  onDashboardChange: (value: boolean) => void;

  onValidate: () => void;
  onAdvanced: () => void;
}

const VEREDITO = {
  organizada: {
    titulo: "Sua planilha já está estruturada e legível",
    texto:
      "Nada a melhorar com segurança na apresentação. Não vamos propor uma reformatação que mexeria na identidade visual dela.",
    classe: "border-ok/40 bg-ok/[0.06]",
  },
  melhoravel: {
    titulo: "A apresentação desta planilha pode ser melhorada",
    texto: "Deseja gerar uma versão organizada e profissional?",
    classe: "border-signal/40 bg-signal/[0.06]",
  },
  ambigua: {
    titulo: "Estrutura ambígua — precisa da sua decisão",
    texto:
      "A tabela não está clara o bastante (mesclagens ou cabeçalho irreconhecível). Organizar seria chutar, então a organização não é oferecida.",
    classe: "border-warn/40 bg-warn/[0.06]",
  },
} as const;

function Caixa({
  checked,
  disabled,
  onChange,
  titulo,
  children,
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (v: boolean) => void;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 accent-signal"
      />
      <span>
        <span className="block text-[0.9rem] font-semibold text-fg">
          {titulo}
        </span>
        <span className="mt-1 block text-[0.85rem] text-muted">{children}</span>
      </span>
    </label>
  );
}

/**
 * Revisar análise e opções — a única parada antes de executar.
 *
 * Substituiu as etapas de schema e perfil: quem analisa uma planilha não
 * precisa entender schema. Tudo aqui começa DESLIGADO, e cada opção diz o
 * que vai acontecer se for ligada.
 */
export default function SpreadsheetReview({
  report,
  origem,
  busy,
  presentation,
  columns,
  duplicateRows,
  applyCleaning,
  onApplyCleaningChange,
  organize,
  onOrganizeChange,
  sortColumn,
  sortDesc,
  onSortChange,
  canSummarize,
  suggestion,
  indicators,
  onIndicatorsChange,
  dashboard,
  onDashboardChange,
  onValidate,
  onAdvanced,
}: Props) {
  const veredito = presentation ? VEREDITO[presentation.veredito] : null;
  const podeOrganizar = presentation?.veredito === "melhoravel";

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
          ["Linhas", report.row_count !== null ? String(report.row_count) : "—"],
          [
            "Colunas",
            report.column_count !== null ? String(report.column_count) : "—",
          ],
        ].map(([rotulo, valor]) => (
          <div
            key={rotulo}
            className="rounded-lg border border-white/6 bg-ink p-3"
          >
            <dt className="text-[0.68rem] uppercase tracking-wider text-muted">
              {rotulo}
            </dt>
            <dd className="mt-1 text-[0.9rem] font-semibold text-fg">{valor}</dd>
          </div>
        ))}
      </dl>

      {veredito ? (
        <div className={`rounded-lg border p-4 ${veredito.classe}`}>
          <p className="text-sm font-semibold text-fg">{veredito.titulo}</p>
          <p className="mt-1 text-[0.85rem] text-muted">{veredito.texto}</p>
          {presentation && presentation.pendencias.length > 0 ? (
            <ul className="mt-2 space-y-0.5 text-[0.82rem] text-muted">
              {presentation.pendencias.map((pendencia) => (
                <li key={pendencia}>• {pendencia}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {duplicateRows > 0 ? (
        <p className="rounded-lg border border-warn/30 bg-warn/[0.05] px-4 py-3 text-[0.85rem] text-muted">
          <strong className="text-fg">
            {duplicateRows} linha(s) 100% repetida(s)
          </strong>{" "}
          — {duplicateRows * 2} linha(s) envolvida(s). A verificação é sempre
          feita e nenhuma linha é removida: elas vão para a lista de revisão.
          Isso é diferente de chave repetida, como a mesma venda com vários
          itens.
        </p>
      ) : null}

      <div className="space-y-4 rounded-lg border border-white/6 bg-ink p-4">
        <p className="text-[0.7rem] uppercase tracking-wider text-muted">
          O que deseja aplicar
        </p>

        <Caixa
          checked={applyCleaning}
          disabled={busy}
          onChange={onApplyCleaningChange}
          titulo="Aplicar as correções seguras"
        >
          Espaços sobrando, caixa e formatos reconhecidos são normalizados, com
          o antes/depois registrado. Nada ambíguo é decidido.
        </Caixa>

        {podeOrganizar ? (
          <Caixa
            checked={organize}
            disabled={busy}
            onChange={onOrganizeChange}
            titulo="Gerar uma versão organizada e profissional"
          >
            Cabeçalho legível, filtro, painel congelado, larguras e formatos
            consistentes. Valores, fórmulas e nomes de coluna não mudam.
          </Caixa>
        ) : null}

        {columns.length > 0 ? (
          <div>
            <p className="text-[0.9rem] font-semibold text-fg">
              Ordenar as linhas (opcional)
            </p>
            <p className="mt-1 text-[0.85rem] text-muted">
              Ordenar altera a posição das linhas. Escolha a coluna e a direção
              antes de aplicar — sem escolha, a ordem original é preservada.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <select
                value={sortColumn}
                disabled={busy}
                onChange={(e) => onSortChange(e.target.value, sortDesc)}
                className="rounded-lg border border-white/12 bg-surface px-3 py-2 text-sm text-fg"
                aria-label="Coluna para ordenar"
              >
                <option value="">Não ordenar</option>
                {columns.map((coluna) => (
                  <option key={coluna} value={coluna}>
                    {coluna}
                  </option>
                ))}
              </select>
              <select
                value={sortDesc ? "desc" : "asc"}
                disabled={busy || !sortColumn}
                onChange={(e) =>
                  onSortChange(sortColumn, e.target.value === "desc")
                }
                className="rounded-lg border border-white/12 bg-surface px-3 py-2 text-sm text-fg"
                aria-label="Direção da ordenação"
              >
                <option value="asc">Crescente</option>
                <option value="desc">Decrescente</option>
              </select>
            </div>
          </div>
        ) : null}

        {canSummarize ? (
          <div>
            <p className="text-[0.9rem] font-semibold text-fg">
              Resumo visual (opcional)
            </p>
            <p className="mt-1 text-[0.85rem] text-muted">
              Identificamos uma possível coluna de valor
              {suggestion.categoria ? ", uma categoria" : ""}
              {suggestion.data ? " e uma data" : ""}. Confirme quais colunas
              usar — sem confirmação, nenhum número é somado.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(
                [
                  ["valor", "Valor"],
                  ["categoria", "Categoria"],
                  ["data", "Data"],
                ] as const
              ).map(([campo, rotulo]) => (
                <select
                  key={campo}
                  value={indicators[campo]}
                  disabled={busy}
                  onChange={(e) =>
                    onIndicatorsChange({
                      ...indicators,
                      [campo]: e.target.value,
                    })
                  }
                  className="rounded-lg border border-white/12 bg-surface px-3 py-2 text-sm text-fg"
                  aria-label={`Coluna de ${rotulo.toLowerCase()}`}
                >
                  <option value="">{rotulo}: nenhuma</option>
                  {columns.map((coluna) => (
                    <option key={coluna} value={coluna}>
                      {rotulo}: {coluna}
                    </option>
                  ))}
                </select>
              ))}
            </div>

            {/* O painel so existe se houver o que somar E uma planilha para
                receber a aba: sem coluna de valor confirmada, nao ha numero. */}
            {indicators.valor ? (
              <div className="mt-3">
                <Caixa
                  checked={dashboard}
                  disabled={busy || !organize}
                  onChange={onDashboardChange}
                  titulo="Adicionar uma aba de Dashboard na planilha organizada"
                >
                  Uma aba nova, com as tabelas e os gráficos desses números, na
                  frente das outras. A aba dos seus dados não recebe gráfico,
                  total nem coluna nova.
                  {!organize
                    ? " Requer a versão organizada — marque a opção acima."
                    : ""}
                </Caixa>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-[0.85rem] text-muted">
            Não foi possível identificar com segurança o papel das colunas, então
            nenhum indicador será criado. A análise geral segue normalmente.
          </p>
        )}
      </div>

      <p className="rounded-lg border border-white/6 bg-ink px-4 py-3 text-[0.85rem] text-muted">
        O arquivo original não é alterado. Tudo é feito sobre uma cópia, em um
        espaço temporário, e o resultado sai em arquivos novos.
      </p>

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onValidate}
          disabled={busy}
          className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Executando…" : "Analisar e organizar"}
        </button>
        <button
          type="button"
          onClick={onAdvanced}
          disabled={busy}
          className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
        >
          Adicionar regras do meu processo (YAML)
        </button>
      </div>
    </div>
  );
}
