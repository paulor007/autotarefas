import type { RunResult, ValidationReport } from "../lib/api";
import {
  ANALYSIS_REPORT_NAME,
  EVIDENCE_PACKAGE_NAME,
  ORGANIZED_SHEET_NAME,
  originalUrl,
} from "../lib/spreadsheets";
import type { JourneyStep } from "../hooks/useSpreadsheetJourney";
import ValidationSummary from "./ValidationSummary";

interface Props {
  step: JourneyStep;
  result: RunResult | null;
  /** Token da execucao — sem ele nao ha como oferecer o arquivo original. */
  token?: string | null;
  /**
   * Resumo lido do `validacao_report.json` desta execucao.
   *
   * E o que responde "o que aconteceu com a MINHA planilha": quantos
   * registros entraram, quantos seguem, quantos voltam para revisao e
   * quantos valores foram normalizados. Null enquanto o arquivo nao chegou.
   */
  report?: ValidationReport | null;
  /** True quando a pessoa confirmou as correções seguras nesta execução. */
  appliedCleaning?: boolean;
  /** True quando a pessoa confirmou a versão organizada nesta execução. */
  appliedOrganize?: boolean;
}

interface Aparencia {
  titulo: string;
  texto: string;
  classe: string;
}

/**
 * Os quatro desfechos possiveis, ditos na lingua de quem enviou a planilha.
 *
 * 1. Estava organizada e nada exigiu decisao.
 * 2. Foi organizada — a versao profissional saiu.
 * 3. Ha pontos que dependem de uma decisao humana.
 * 4. Nao foi possivel concluir com seguranca.
 *
 * A distincao que mais importa continua sendo a terceira: exit 1 significa "a
 * analise terminou e encontrou o que precisa da sua decisao" — um resultado
 * util, nao uma falha da aplicacao.
 */
function aparencia(
  step: JourneyStep,
  organizou: boolean,
  motivo: string,
): Aparencia | null {
  switch (step) {
    case "completed":
      return organizou
        ? {
            titulo: "Concluído — versão organizada gerada",
            texto:
              "A formatação profissional foi aplicada sobre uma cópia. Valores, fórmulas, identificadores e a ordem das linhas continuam como estavam; nada exigiu a sua decisão.",
            classe: "border-ok/40 bg-ok/5 text-ok",
          }
        : {
            titulo: "Concluído — nada exigiu a sua decisão",
            texto:
              "A análise geral foi feita, incluindo a verificação de linhas 100% repetidas, e não encontrou nada que dependesse de você.",
            classe: "border-ok/40 bg-ok/5 text-ok",
          };
    case "completed_with_issues":
      return {
        titulo: "Concluído — há pontos que dependem da sua decisão",
        texto:
          "A análise terminou e encontrou pontos que precisam de uma decisão humana. Nada foi removido ou alterado por conta própria: o relatório mostra cada linha e o motivo.",
        classe: "border-warn/40 bg-warn/5 text-warn",
      };
    case "invalid_configuration":
    case "timed_out":
    case "technical_failure":
      return {
        titulo: "Não foi possível concluir com segurança",
        texto: `${motivo} O arquivo original continua intacto e nenhuma alteração foi aplicada.`,
        classe: "border-danger/40 bg-danger/5 text-danger",
      };
    default:
      return null;
  }
}

/** O detalhe do que impediu a conclusão — sem jargão e sem culpar a pessoa. */
function motivoDaFalha(step: JourneyStep): string {
  if (step === "invalid_configuration") {
    return "A configuração escolhida não pôde ser utilizada — revise a aba, o cabeçalho ou o schema enviado.";
  }
  if (step === "timed_out") {
    return "A execução passou do tempo limite e foi interrompida.";
  }
  return "Houve uma falha técnica durante a execução.";
}

/** Rotulos legiveis para os artefatos — nada de nome tecnico cru. */
/**
 * Rotulos legiveis para os artefatos.
 *
 * "planilha_validada.xlsx" NAO e a planilha corrigida: e um relatorio em
 * quatro abas (Resumo, Registros validos, Registros invalidos, Auditoria).
 * O rotulo anterior, "Planilha validada", sugeria correcao automatica — que o
 * fluxo nao faz. O nome do ARQUIVO nao muda (e contrato publico da CLI); so a
 * forma como a tela o apresenta.
 */
const ROTULOS: Record<string, string> = {
  "validacao_report.json": "Relatório da validação (JSON)",
  "planilha_validada.xlsx": "Relatório em planilha (resumo e registros)",
  "planilha_tratada.xlsx": "Planilha tratada (a sua, com as correções seguras)",
  "preservacao_report.json": "O que foi preservado da planilha original",
  "registros_validos.csv": "Registros válidos",
  "registros_invalidos.csv": "Registros para revisão",
  "registros_para_revisao.csv": "Registros que precisam de decisão humana",
  "schema_sugerido.yaml": "Schema sugerido (estrutura observada)",
  "schema_efetivo.yaml": "Schema aplicado na validação",
  [EVIDENCE_PACKAGE_NAME]: "Pacote completo de evidências",
};

/**
 * Os arquivos que a area principal pode mostrar — no maximo tres.
 *
 * A lista antiga despejava sete arquivos com nome tecnico e deixava a pessoa
 * decidindo qual era "o resultado". Aqui ficam so os dois que respondem "e a
 * minha planilha?" e "o que voces acharam?"; o resto desce para os downloads
 * avancados, que continuam completos para quem audita.
 */
const PRINCIPAIS: ReadonlyArray<[string, string]> = [
  [ORGANIZED_SHEET_NAME, "Planilha organizada (a sua, formatada)"],
  [ANALYSIS_REPORT_NAME, "Relatório da análise"],
];

const PRINCIPAL = new Set<string>(PRINCIPAIS.map(([nome]) => nome));

function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SpreadsheetResult({
  step,
  result,
  token = null,
  report,
  appliedCleaning = false,
  appliedOrganize = false,
}: Props) {
  const artefatos = result?.artifacts ?? [];
  const organizou =
    appliedOrganize && artefatos.some((a) => a.name === ORGANIZED_SHEET_NAME);
  const visual = aparencia(step, organizou, motivoDaFalha(step));
  if (!visual) return null;

  // Zero correções pode significar duas coisas MUITO diferentes: "não pedi
  // correção" ou "pedi e nada precisou ser corrigido". Um contador em zero,
  // sozinho, não distingue as duas — e a segunda é uma boa notícia.
  const nenhumaCorrecaoNecessaria =
    appliedCleaning && report !== null && report?.total_cleaned === 0;

  // "16" sozinho é ambíguo: são 16 pares? 16 linhas? A categoria conta as
  // ocorrências EXCEDENTES, então 16 repetidas = 32 linhas envolvidas.
  const duplicadas = report?.issues_by_category?.duplicado ?? 0;

  return (
    <div className="space-y-4" aria-live="polite">
      <div className={`rounded-lg border px-4 py-3 ${visual.classe}`}>
        <p className="text-sm font-semibold">{visual.titulo}</p>
        <p className="mt-1 text-[0.85rem] opacity-90">{visual.texto}</p>
      </div>

      {duplicadas > 0 ? (
        <div className="rounded-lg border border-warn/30 bg-warn/[0.05] px-4 py-3">
          <p className="text-sm font-semibold text-warn">
            {duplicadas} linha(s) repetida(s) — {duplicadas * 2} linha(s)
            envolvida(s)
          </p>
          <p className="mt-1 text-[0.85rem] text-muted">
            São ocorrências <strong>excedentes</strong>: a primeira de cada par
            é tratada como o registro original. Nenhuma foi removida — cada uma
            aparece no relatório com o número da linha e o par correspondente,
            para você decidir. Chave repetida (a mesma venda com vários itens)
            não entra nessa conta.
          </p>
        </div>
      ) : null}

      {/* Com pendencias, o aviso amarelo dominava a tela e a confirmacao da
          versao organizada sumia — quem pediu a formatacao ficava sem saber se
          ela saiu. Agora as duas noticias convivem. */}
      {organizou && step === "completed_with_issues" ? (
        <div className="rounded-lg border border-ok/30 bg-ok/[0.05] px-4 py-3">
          <p className="text-sm font-semibold text-ok">
            A versão organizada foi gerada
          </p>
          <p className="mt-1 text-[0.85rem] text-muted">
            Os pontos acima dependem da sua decisão, mas a formatação
            profissional que você confirmou está pronta para baixar abaixo.
          </p>
        </div>
      ) : null}

      {nenhumaCorrecaoNecessaria ? (
        <div className="rounded-lg border border-ok/30 bg-ok/[0.05] px-4 py-3">
          <p className="text-sm font-semibold text-ok">
            Nenhuma correção segura foi necessária
          </p>
          <p className="mt-1 text-[0.85rem] text-muted">
            Você pediu as correções seguras e o AutoTarefas não encontrou nada
            para normalizar: a planilha tratada preserva os dados originais,
            célula por célula.
          </p>
        </div>
      ) : null}

      {report ? <ValidationSummary report={report} /> : null}

      {result ? (
        <>
          <p className="text-[0.8rem] text-muted">
            Duração: {(result.duration_ms / 1000).toFixed(1)}s · o arquivo
            original não foi alterado.
          </p>

          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
              Downloads
            </h4>
            <ul className="space-y-2">
              {token ? (
                <li>
                  <a
                    href={originalUrl(token)}
                    download
                    className="flex items-center justify-between gap-3 rounded-lg border border-white/6 bg-ink px-4 py-3 text-sm hover:border-white/20"
                  >
                    <span className="min-w-0">
                      <span className="font-semibold text-fg">
                        Arquivo original
                      </span>
                      <span className="ml-2 text-[0.8rem] text-muted">
                        como você enviou
                      </span>
                    </span>
                    <span className="whitespace-nowrap text-[0.8rem] text-signal">
                      Baixar
                    </span>
                  </a>
                </li>
              ) : null}
              {PRINCIPAIS.map(([nome, rotulo]) => {
                const artefato = artefatos.find((a) => a.name === nome);
                if (!artefato) return null;
                return (
                  <li key={nome}>
                    <a
                      href={artefato.download_url}
                      download
                      className="flex items-center justify-between gap-3 rounded-lg border border-white/6 bg-ink px-4 py-3 text-sm hover:border-white/20"
                    >
                      <span className="min-w-0">
                        <span className="font-semibold text-fg">{rotulo}</span>
                        <span className="ml-2 text-[0.8rem] text-muted">
                          {tamanho(artefato.bytes)}
                        </span>
                      </span>
                      <span className="whitespace-nowrap text-[0.8rem] text-signal">
                        Baixar
                      </span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>

          {artefatos.some((a) => !PRINCIPAL.has(a.name)) ? (
            <details className="rounded-lg border border-white/6 bg-ink">
              <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-fg">
                Downloads avançados
              </summary>
              <div className="px-4 pb-4">
                <p className="mb-3 text-[0.8rem] text-muted">
                  Arquivos técnicos desta execução: registros separados, schema
                  aplicado, relatórios em JSON e o pacote completo com as somas
                  de verificação.
                </p>
                <ul className="space-y-2">
                  {artefatos
                    .filter((a) => !PRINCIPAL.has(a.name))
                    .map((artefato) => (
                      <li key={artefato.name}>
                        <a
                          href={artefato.download_url}
                          download
                          className="flex items-center justify-between gap-3 rounded-lg border border-white/6 px-4 py-2.5 text-sm hover:border-white/20"
                        >
                          <span className="min-w-0">
                            <span className="text-fg">
                              {ROTULOS[artefato.name] ?? artefato.name}
                            </span>
                            <span className="ml-2 text-[0.8rem] text-muted">
                              {tamanho(artefato.bytes)}
                            </span>
                          </span>
                          <span className="whitespace-nowrap text-[0.8rem] text-signal">
                            Baixar
                          </span>
                        </a>
                      </li>
                    ))}
                </ul>
              </div>
            </details>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
