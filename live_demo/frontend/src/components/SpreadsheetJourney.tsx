import { useEffect, useRef } from "react";

import { useSpreadsheetJourney } from "../hooks/useSpreadsheetJourney";
import { useValidationReport } from "../hooks/useValidationReport";
import FileDrop from "./FileDrop";
import SpreadsheetAnalysis from "./SpreadsheetAnalysis";
import SpreadsheetResult from "./SpreadsheetResult";
import SpreadsheetReview from "./SpreadsheetReview";
import SpreadsheetSchemaChoice from "./SpreadsheetSchemaChoice";
import SpreadsheetProfileMapping from "./SpreadsheetProfileMapping";
import SpreadsheetSelection from "./SpreadsheetSelection";
import TerminalView from "./TerminalView";

const SPREADSHEET_ACCEPT = ".csv,.xlsx";

/** As etapas visiveis na trilha, na ordem em que acontecem. */
const TRILHA = [
  { chave: "arquivo", titulo: "Arquivo" },
  { chave: "analise", titulo: "Análise" },
  { chave: "schema", titulo: "Regras" },
  { chave: "revisao", titulo: "Revisão" },
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
      "choosing_schema",
      "schema_uploading",
      "schema_invalid",
      "schema_ready",
    ].includes(step)
  ) {
    return "schema";
  }
  if (step === "reviewing") return "revisao";
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
        {etapa === "schema" && "Como validar"}
        {etapa === "revisao" && "Revise antes de executar"}
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
            arquivo original nunca é alterado.
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
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={jornada.goToSchemaChoice}
              className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink"
            >
              Escolher como validar
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

      {/* ---------- Etapa: schema ---------- */}
      {["choosing_schema", "schema_uploading", "schema_invalid"].includes(
        step,
      ) && token ? (
        <SpreadsheetSchemaChoice
          token={token}
          busy={busy}
          error={error}
          summary={schema?.summary ?? null}
          onUseSuggested={() => void jornada.useSuggested()}
          onUseProfile={() => void jornada.goToProfileChoice()}
          onUpload={(arquivo) => void jornada.sendSchema(arquivo)}
        />
      ) : null}

      {step === "choosing_profile" ? (
        <SpreadsheetProfileMapping
          profiles={jornada.profiles}
          profile={jornada.profile}
          columns={jornada.columns}
          mapping={jornada.mapping}
          busy={busy}
          error={error}
          onPick={(id) => void jornada.pickProfile(id)}
          onChange={jornada.setMappingField}
          onSubmit={() => void jornada.submitProfileMapping()}
          onBack={jornada.goToSchemaChoice}
        />
      ) : null}

      {step === "schema_ready" && schema ? (
        <div className="space-y-5">
          <p className="rounded-lg border border-ok/40 bg-ok/5 px-4 py-3 text-sm text-ok">
            Schema confirmado. Revise a configuração antes de executar.
          </p>
          {schema.profile ? (
            <div className="rounded-lg border border-white/6 bg-ink px-4 py-3 text-[0.85rem]">
              <p className="font-semibold text-fg">
                Gerado a partir do perfil {schema.profile.id}
                {schema.profile.version !== null
                  ? ` (versão ${schema.profile.version})`
                  : ""}
              </p>
              {/* Exibimos o mapeamento CONFIRMADO pelo backend, não o estado
                  local: mostrar o que foi enviado poderia divergir do que o
                  núcleo realmente aplicou. */}
              <ul className="mt-2 space-y-1 text-muted">
                {Object.entries(schema.profile.mapping).map(
                  ([campo, coluna]) => (
                    <li key={campo}>
                      {campo} → <span className="text-fg">{coluna}</span>
                    </li>
                  ),
                )}
              </ul>
              {schema.profile.omitted.length > 0 ? (
                <p className="mt-2 text-muted">
                  Campos não usados: {schema.profile.omitted.join(", ")}.
                </p>
              ) : null}
            </div>
          ) : null}
          <button
            type="button"
            onClick={jornada.goToReview}
            className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink"
          >
            Revisar configuração
          </button>
        </div>
      ) : null}

      {/* ---------- Etapa: revisão ---------- */}
      {step === "reviewing" && analysis?.analysis && schema ? (
        <SpreadsheetReview
          report={analysis.analysis}
          summary={schema.summary}
          origin={schema.schema_origin}
          origem={origem}
          busy={busy}
          applyCleaning={jornada.applyCleaning}
          onApplyCleaningChange={jornada.setApplyCleaning}
          duplicateRows={analysis.duplicate_rows}
          flagDuplicateRows={jornada.flagDuplicateRows}
          onFlagDuplicateRowsChange={jornada.setFlagDuplicateRows}
          onValidate={() => void jornada.validate()}
          onBack={jornada.goToSchemaChoice}
        />
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
        report={relatorio}
        appliedCleaning={jornada.applyCleaning}
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
