import { useState } from "react";

import {
  previewSummary,
  type AnalysisReport,
  type PresentationAudit,
  type SummaryIndicator,
} from "../lib/spreadsheets";

interface Props {
  report: AnalysisReport;
  origem: "exemplo" | "upload";
  busy: boolean;
  /** Avaliação objetiva da apresentação (null em CSV). */
  presentation: PresentationAudit | null;
  /** Colunas disponíveis para ordenação e para os papéis do resumo. */
  columns: string[];
  /** O que chama atenção nos dados — observado, nunca alterado. */
  notes: string[];
  /** Tipo observado de cada coluna, para avisar antes de somar texto. */
  columnTypes: Record<string, string>;
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
  /** Token da sessão — necessário para calcular a prévia. */
  token: string | null;

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

/**
 * Tipos que se comportam como numero na hora de somar.
 *
 * Somar uma coluna de texto nao quebra nada — o resultado sai zero, com as
 * linhas contadas como ignoradas. Mas descobrir isso depois de executar e
 * tempo perdido: da para avisar no momento da escolha.
 */
const TIPOS_SOMAVEIS = new Set(["inteiro", "decimal", "moeda", "percentual"]);

/** Os tres papeis do resumo, e o que cada um faz com o numero. */
const PAPEIS = [
  {
    campo: "valor",
    rotulo: "Valor",
    dica: "o número que será somado",
  },
  {
    campo: "categoria",
    rotulo: "Categoria",
    dica: "por quem agrupar — vira as barras",
  },
  {
    campo: "data",
    rotulo: "Data",
    dica: "agrupa por mês — vira a linha do tempo",
  },
] as const;

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
  notes,
  columnTypes,
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
  token,
  onValidate,
  onAdvanced,
}: Props) {
  const [previa, setPrevia] = useState<SummaryIndicator[] | null>(null);
  const [calculando, setCalculando] = useState(false);
  const [erroPrevia, setErroPrevia] = useState<string | null>(null);

  const podeResumir = Boolean(
    indicators.valor && (indicators.categoria || indicators.data),
  );

  const verPrevia = async () => {
    if (!token || calculando) return;
    setCalculando(true);
    setErroPrevia(null);
    try {
      setPrevia(await previewSummary(token, indicators));
    } catch (e: unknown) {
      setPrevia(null);
      setErroPrevia(
        e instanceof Error ? e.message : "não foi possível calcular a prévia",
      );
    } finally {
      setCalculando(false);
    }
  };

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

      {notes.length > 0 ? (
        <div className="rounded-lg border border-white/10 bg-ink px-4 py-3">
          <p className="text-[0.85rem] font-semibold text-fg">
            Observações sobre os dados
          </p>
          <ul className="mt-1.5 space-y-1 text-[0.85rem] text-muted">
            {notes.map((nota) => (
              <li key={nota}>• {nota}</li>
            ))}
          </ul>
          <p className="mt-2 text-[0.8rem] text-muted">
            São observações, não correções: nada disso é alterado sem você pedir.
          </p>
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
              Diga o que cada coluna significa e o sistema soma o valor por
              categoria e por mês. Sem essa confirmação, nenhum número é somado
              — e nada disso altera a aba dos seus dados.
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              {PAPEIS.map(({ campo, rotulo, dica }) => (
                <label key={campo} className="block">
                  <span className="block text-[0.8rem] font-semibold text-fg">
                    {rotulo}
                  </span>
                  <span className="mt-0.5 block text-[0.78rem] text-muted">
                    {dica}
                  </span>
                  <select
                    value={indicators[campo]}
                    disabled={busy}
                    onChange={(e) =>
                      onIndicatorsChange({
                        ...indicators,
                        [campo]: e.target.value,
                      })
                    }
                    className="mt-1.5 w-full rounded-lg border border-white/12 bg-surface px-3 py-2 text-sm text-fg"
                    aria-label={`Coluna de ${rotulo.toLowerCase()}`}
                  >
                    <option value="">nenhuma</option>
                    {columns.map((coluna) => (
                      <option key={coluna} value={coluna}>
                        {coluna}
                        {suggestion[campo] === coluna ? " (sugerida)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>

            {/* Valor sozinho nao produz nada: sem uma dimensao nao ha como
                agrupar. Dizer isso aqui evita um painel vazio depois. */}
            {indicators.valor &&
            columnTypes[indicators.valor] &&
            !TIPOS_SOMAVEIS.has(columnTypes[indicators.valor]) ? (
              <p className="mt-2 text-[0.82rem] text-warn">
                A coluna <strong>{indicators.valor}</strong> foi observada como{" "}
                <strong>{columnTypes[indicators.valor]}</strong>, não como
                número. O resumo sairia zerado, com todas as linhas ignoradas —
                confira se é mesmo a coluna dos valores.
              </p>
            ) : null}

            {indicators.valor && !indicators.categoria && !indicators.data ? (
              <p className="mt-2 text-[0.82rem] text-warn">
                Escolha também uma categoria ou uma data — só com o valor não há
                como agrupar, e nenhum resumo seria gerado.
              </p>
            ) : null}

            {/* Conferir a escolha das colunas nao devia custar uma execucao
                inteira. A conta aqui e a MESMA que vai para o relatorio. */}
            {podeResumir ? (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => void verPrevia()}
                  disabled={busy || calculando}
                  className="rounded-lg border border-white/12 px-4 py-2 text-[0.85rem] font-semibold text-fg hover:border-white/25 disabled:opacity-50"
                >
                  {calculando ? "Calculando…" : "Ver prévia do resumo"}
                </button>

                {erroPrevia ? (
                  <p className="mt-2 text-[0.82rem] text-danger">{erroPrevia}</p>
                ) : null}

                {previa !== null && previa.length === 0 ? (
                  <p className="mt-2 text-[0.82rem] text-warn">
                    Com estas colunas, nenhum número seria somado.
                  </p>
                ) : null}

                {previa?.map((indicador) => (
                  <div
                    key={indicador.titulo}
                    className="mt-3 rounded-lg border border-white/6 bg-surface p-3"
                  >
                    <p className="text-[0.85rem] font-semibold text-fg">
                      {indicador.titulo}
                    </p>
                    <table className="mt-1.5 w-full text-[0.82rem] text-muted">
                      <tbody>
                        {indicador.linhas.map(([chave, valor]) => (
                          <tr key={chave}>
                            <td className="py-0.5 pr-3">{chave}</td>
                            <td className="py-0.5 text-right text-fg">
                              {valor.toLocaleString("pt-BR", {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </td>
                          </tr>
                        ))}
                        <tr className="border-t border-white/10">
                          <td className="py-0.5 pr-3 font-semibold text-fg">
                            Total
                          </td>
                          <td className="py-0.5 text-right font-semibold text-fg">
                            {indicador.total.toLocaleString("pt-BR", {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    {indicador.ignoradas > 0 ? (
                      <p className="mt-1.5 text-[0.8rem] text-warn">
                        {indicador.ignoradas} linha(s) ignorada(s): o valor não
                        pôde ser lido como número.
                      </p>
                    ) : null}
                  </div>
                ))}

                {previa && previa.length > 0 ? (
                  <p className="mt-2 text-[0.8rem] text-muted">
                    Mostrando as primeiras linhas de cada resumo. Nada foi
                    gravado — isto é só um cálculo para você conferir.
                  </p>
                ) : null}
              </div>
            ) : null}

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
