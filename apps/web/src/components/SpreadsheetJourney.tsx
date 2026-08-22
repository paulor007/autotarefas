import { useEffect, useRef } from "react";

import { useSpreadsheetJourney } from "../hooks/useSpreadsheetJourney";
import { useValidationReport } from "../hooks/useValidationReport";
import FileDrop from "./FileDrop";
import SpreadsheetAnalysis from "./SpreadsheetAnalysis";
import SpreadsheetResult from "./SpreadsheetResult";
import SpreadsheetReview from "./SpreadsheetReview";
import SpreadsheetSchemaChoice from "./SpreadsheetSchemaChoice";
import SpreadsheetSelection from "./SpreadsheetSelection";
import TerminalView from "./TerminalView";

// .xls e .ods entram para LEITURA: a analise geral funciona, mas eles nao tem
// apresentacao que o openpyxl consiga regravar — nao ha versao organizada.
const SPREADSHEET_ACCEPT = ".csv,.xlsx,.xls,.ods";

/**
 * As etapas visiveis na trilha, na ordem em que acontecem.
 *
 * A etapa "Regras" saiu: schema deixou de ser exigencia da jornada. Quem
 * analisa uma planilha vai do diagnostico direto para revisar a analise e as
 * opcoes; o YAML virou um desvio avancado dentro dessa mesma etapa.
 */
const TRILHA = [
  { chave: "arquivo", titulo: "Arquivo" },
  { chave: "analise", titulo: "Análise" },
  { chave: "revisao", titulo: "Revisão e opções" },
  { chave: "resultado", titulo: "Resultado" },
] as const;

type EtapaTrilha = (typeof TRILHA)[number]["chave"];

function etapaAtual(step: string): EtapaTrilha {
  if (["idle", "file_selected"].includes(step)) return "arquivo";
  if (
    [
      "analyzing",
      "needs_selection",
      "analysis_ready",
      "rejected_file",
    ].includes(step)
  ) {
    return "analise";
  }
  if (
    [
      "reviewing",
      "choosing_schema",
      "schema_uploading",
      "schema_invalid",
      "schema_ready",
    ].includes(step)
  ) {
    return "revisao";
  }
  return "resultado";
}

/**
 * Jornada guiada de planilhas: analisar antes de validar.
 *
 * Este componente orquestra as etapas e nao contem regra nenhuma — cada
 * decisao (o que e ambiguo, se o schema vale, qual o desfecho) vem do
 * backend. O terminal continua disponivel, mas como INFORMACAO COMPLEMENTAR:
 * o que a tela afirma sai dos dados estruturados, nunca do texto da saida.
 */
export default function SpreadsheetJourney() {
  const jornada = useSpreadsheetJourney();
  const { step, analysis, schema, error, rejection, token, execution, busy } =
    jornada;

  const etapa = etapaAtual(step);
  const cabecalhoRef = useRef<HTMLHeadingElement>(null);
  // O resumo sai do relatorio REAL da execucao (validacao_report.json), nunca
  // do texto do terminal.
  const relatorio = useValidationReport(execution.result);

  // Ao mudar de etapa, o foco vai para o titulo: quem navega por teclado ou
  // leitor de tela precisa saber que a tela mudou.
  useEffect(() => {
    cabecalhoRef.current?.focus();
  }, [etapa]);

  const origem = jornada.file ? "upload" : "exemplo";

  return (
    <div className="space-y-6">
      {/* Trilha das etapas */}
      <ol className="flex gap-2 overflow-x-auto" aria-label="Etapas da jornada">
        {TRILHA.map((passo, i) => {
          const indiceAtual = TRILHA.findIndex((p) => p.chave === etapa);
          const estado =
            i < indiceAtual ? "feito" : i === indiceAtual ? "atual" : "futuro";
          return (
            <li
              key={passo.chave}
              aria-current={estado === "atual" ? "step" : undefined}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[0.75rem] font-semibold ${
                estado === "atual"
                  ? "bg-signal text-ink"
                  : estado === "feito"
                    ? "border border-white/12 text-fg"
                    : "border border-white/6 text-muted"
              }`}
            >
              {i + 1}. {passo.titulo}
            </li>
          );
        })}
      </ol>

      <h3
        ref={cabecalhoRef}
        tabIndex={-1}
        className="text-lg font-semibold text-fg outline-none"
      >
        {etapa === "arquivo" && "Escolha o arquivo"}
        {etapa === "analise" && "Diagnóstico do arquivo"}
        {etapa === "revisao" && "Revisar análise e opções"}
        {etapa === "resultado" && "Resultado"}
      </h3>

      {error && step !== "expired" ? (
        <div
          role="alert"
          className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {error}
        </div>
      ) : null}

      {/* ---------- Etapa: arquivo ---------- */}
      {etapa === "arquivo" ? (
        <div className="space-y-4">
          <p className="text-[0.9rem] leading-relaxed text-muted">
            Envie um CSV ou XLSX. O AutoTarefas analisa a estrutura, mostra o
            que encontrou e só valida depois que você confirmar as regras. O
            arquivo original nunca é alterado. Planilhas antigas (.xls) e do
            LibreOffice (.ods) também são lidas, mas para elas não há versão
            organizada — só a análise.
          </p>

          <FileDrop
            accept={SPREADSHEET_ACCEPT}
            multiple={false}
            files={jornada.file ? [jornada.file] : []}
            onChange={(arquivos) => jornada.chooseFile(arquivos[0] ?? null)}
            disabled={busy}
          />

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => void jornada.analyzeFile()}
              disabled={!jornada.file || busy}
              className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              Analisar meus dados
            </button>
            <button
              type="button"
              onClick={() => void jornada.analyzeSample()}
              disabled={busy}
              className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
            >
              Testar com exemplo
            </button>
          </div>

          <p className="text-[0.8rem] leading-relaxed text-muted">
            O arquivo é processado em um espaço temporário desta execução, não é
            enviado a serviços externos neste fluxo, e fórmulas e macros não são
            executadas. Os arquivos desta execução são temporários e removidos
            conforme a política do ambiente.
          </p>
        </div>
      ) : null}

      {/* ---------- Etapa: análise ---------- */}
      {step === "analyzing" ? (
        <p className="text-sm text-muted" aria-live="polite">
          Analisando a estrutura do arquivo…
        </p>
      ) : null}

      {step === "rejected_file" ? (
        <div className="space-y-4">
          <div
            role="alert"
            className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger"
          >
            {rejection}
          </div>
          <button
            type="button"
            onClick={jornada.reset}
            className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25"
          >
            Escolher outro arquivo
          </button>
        </div>
      ) : null}

      {step === "needs_selection" && analysis ? (
        <SpreadsheetSelection
          ambiguities={analysis.ambiguities}
          busy={busy}
          onChoose={(escolha) => void jornada.choose(escolha)}
        />
      ) : null}

      {step === "analysis_ready" && analysis?.analysis ? (
        <div className="space-y-5">
          <SpreadsheetAnalysis
            report={analysis.analysis}
            preview={analysis.preview}
          />

          {/* Abas classificadas: com mais de uma aba de dados, a escolha ja
              aconteceu na etapa de ambiguidade — aqui so mostramos o que foi
              encontrado, para ninguem descobrir depois que havia outra aba. */}
          {analysis.sheets.length > 1 ? (
            <div className="rounded-lg border border-white/6 bg-ink px-4 py-3 text-[0.85rem]">
              <p className="font-semibold text-fg">
                O arquivo tem {analysis.sheets.length} abas
              </p>
              <ul className="mt-2 space-y-1 text-muted">
                {analysis.sheets.map((aba) => (
                  <li key={aba.nome}>
                    <span className="text-fg">{aba.nome}</span> — {aba.natureza}
                    {aba.nome === analysis.analysis?.selected_sheet
                      ? " (em análise)"
                      : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={jornada.goToReview}
              className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink"
            >
              Revisar análise e opções
            </button>
            {/* Saida disponivel JA na analise: antes so havia como recomecar
                depois de validar, o que obrigava a executar algo so para
                trocar de arquivo. */}
            <button
              type="button"
              onClick={jornada.reset}
              className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25"
            >
              Analisar outro arquivo
            </button>
          </div>
        </div>
      ) : null}

      {/* ---------- Etapa: revisão e opções ---------- */}
      {step === "reviewing" && analysis?.analysis ? (
        <SpreadsheetReview
          report={analysis.analysis}
          origem={origem}
          busy={busy}
          presentation={analysis.presentation}
          columns={jornada.columns}
          notes={analysis.notes}
          columnTypes={Object.fromEntries(
            (analysis.analysis?.columns ?? []).map((c) => [
              c.name,
              c.inferred_type ?? "",
            ]),
          )}
          duplicateRows={analysis.duplicate_rows}
          applyCleaning={jornada.applyCleaning}
          onApplyCleaningChange={jornada.setApplyCleaning}
          organize={jornada.organize}
          onOrganizeChange={jornada.setOrganize}
          sortColumn={jornada.sortColumn}
          sortDesc={jornada.sortDesc}
          onSortChange={jornada.setSort}
          canSummarize={analysis.column_roles?.offerable ?? false}
          suggestion={
            analysis.column_roles?.suggestion ?? {
              valor: "",
              categoria: "",
              data: "",
            }
          }
          indicators={jornada.indicators}
          onIndicatorsChange={jornada.setIndicators}
          dashboard={jornada.dashboard}
          onDashboardChange={jornada.setDashboard}
          token={token}
          onValidate={() => void jornada.validate()}
          onAdvanced={jornada.goToSchemaChoice}
        />
      ) : null}

      {/* Desvio avançado: regras próprias em YAML. */}
      {["choosing_schema", "schema_uploading", "schema_invalid"].includes(
        step,
      ) && token ? (
        <SpreadsheetSchemaChoice
          token={token}
          busy={busy}
          error={error}
          summary={schema?.summary ?? null}
          onUpload={(arquivo) => void jornada.sendSchema(arquivo)}
          onBack={jornada.goToReview}
        />
      ) : null}

      {step === "schema_ready" && schema ? (
        <div className="space-y-5">
          <p className="rounded-lg border border-ok/40 bg-ok/5 px-4 py-3 text-sm text-ok">
            Schema aceito. As regras do seu processo serão aplicadas junto com a
            análise geral.
          </p>
          <button
            type="button"
            onClick={jornada.goToReview}
            className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink"
          >
            Voltar para a revisão
          </button>
        </div>
      ) : null}

      {/* ---------- Etapa: execução e resultado ---------- */}
      {step === "validating" ? (
        <p className="text-sm text-muted" aria-live="polite">
          Validando… acompanhe a saída abaixo.
        </p>
      ) : null}

      <SpreadsheetResult
        step={step}
        result={execution.result}
        token={token}
        report={relatorio}
        appliedCleaning={jornada.applyCleaning}
        appliedOrganize={jornada.organize}
      />

      {execution.lines.length > 0 ? (
        <details className="rounded-2xl border border-white/6 bg-ink">
          <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-fg">
            Saída detalhada da execução
          </summary>
          <div className="px-4 pb-4">
            <TerminalView
              lines={execution.lines}
              status={execution.status}
              outcome={execution.result?.outcome}
            />
          </div>
        </details>
      ) : null}

      {/* ---------- Sessão expirada ---------- */}
      {step === "expired" ? (
        <div className="space-y-4">
          <div
            role="alert"
            className="rounded-lg border border-warn/40 bg-warn/5 px-4 py-3 text-sm text-warn"
          >
            Os arquivos desta execução eram temporários e já foram removidos
            conforme a política do ambiente. Envie o arquivo de novo para
            recomeçar.
          </div>
          <button
            type="button"
            onClick={jornada.reset}
            className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink"
          >
            Recomeçar
          </button>
        </div>
      ) : null}

      {[
        "completed",
        "completed_with_issues",
        "invalid_configuration",
        "timed_out",
        "technical_failure",
      ].includes(step) ? (
        <button
          type="button"
          onClick={jornada.reset}
          className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25"
        >
          Analisar outro arquivo
        </button>
      ) : null}
    </div>
  );
}
