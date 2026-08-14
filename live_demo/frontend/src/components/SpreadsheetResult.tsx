import type { RunResult, ValidationReport } from "../lib/api";
import { EVIDENCE_PACKAGE_NAME } from "../lib/spreadsheets";
import type { JourneyStep } from "../hooks/useSpreadsheetJourney";
import ValidationSummary from "./ValidationSummary";

interface Props {
  step: JourneyStep;
  result: RunResult | null;
  /**
   * Resumo lido do `validacao_report.json` desta execucao.
   *
   * E o que responde "o que aconteceu com a MINHA planilha": quantos
   * registros entraram, quantos seguem, quantos voltam para revisao e
   * quantos valores foram normalizados. Null enquanto o arquivo nao chegou.
   */
  report?: ValidationReport | null;
}

interface Aparencia {
  titulo: string;
  texto: string;
  classe: string;
}

/**
 * Como cada desfecho e apresentado.
 *
 * A distincao que mais importa: exit 1 significa "a validacao terminou e
 * encontrou registros para revisar" — um resultado util, nao uma falha da
 * aplicacao. Chamar isso de erro faria a pessoa achar que o sistema quebrou
 * quando, na verdade, ele fez o trabalho.
 */
function aparencia(step: JourneyStep): Aparencia | null {
  switch (step) {
    case "completed":
      return {
        titulo: "Concluído sem registros para revisão",
        // Sem esta segunda frase a tela parecia se contradizer: a analise
        // aponta observacoes estruturais (linhas repetidas, por exemplo) e o
        // resultado diz "sem problemas". Sao coisas distintas — as regras
        // confirmadas e que definem o que e problema, e o schema sugerido nao
        // inclui regra de duplicidade.
        texto:
          "A validação foi concluída e nenhum registro precisou de revisão. Observações estruturais vistas na análise não viram problema a menos que uma regra confirmada trate delas.",
        classe: "border-ok/40 bg-ok/5 text-ok",
      };
    case "completed_with_issues":
      return {
        titulo: "Concluído com registros para revisão",
        texto:
          "A validação foi concluída e encontrou registros que precisam de revisão. Os arquivos abaixo separam o que segue do que volta.",
        classe: "border-warn/40 bg-warn/5 text-warn",
      };
    case "invalid_configuration":
      return {
        titulo: "Configuração inválida",
        texto:
          "A configuração escolhida não pôde ser utilizada. Revise o schema ou a seleção de aba e cabeçalho e tente de novo.",
        classe: "border-danger/40 bg-danger/5 text-danger",
      };
    case "timed_out":
      return {
        titulo: "Execução interrompida",
        texto:
          "A execução passou do tempo limite e foi interrompida. O arquivo original continua intacto.",
        classe: "border-warn/40 bg-warn/5 text-warn",
      };
    case "technical_failure":
      return {
        titulo: "Não foi possível concluir",
        texto:
          "Houve uma falha ao executar a validação. Tente novamente; se persistir, use um arquivo menor para verificar.",
        classe: "border-danger/40 bg-danger/5 text-danger",
      };
    default:
      return null;
  }
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
  "schema_sugerido.yaml": "Schema sugerido (estrutura observada)",
  "schema_efetivo.yaml": "Schema aplicado na validação",
  [EVIDENCE_PACKAGE_NAME]: "Pacote completo de evidências",
};

/**
 * Ordem de exibicao: o que a pessoa mais quer baixar primeiro.
 *
 * A planilha tratada e o resultado do trabalho — ela abre a lista. O pacote
 * de evidencias e o schema interessam a quem vai auditar, e ficam no fim.
 */
const PRIORIDADE = [
  "planilha_tratada.xlsx",
  "registros_validos.csv",
  "registros_invalidos.csv",
  "planilha_validada.xlsx",
  "validacao_report.json",
  "preservacao_report.json",
  EVIDENCE_PACKAGE_NAME,
];

function ordemDoArtefato(nome: string): number {
  const posicao = PRIORIDADE.indexOf(nome);
  return posicao === -1 ? PRIORIDADE.length : posicao;
}

function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SpreadsheetResult({ step, result, report }: Props) {
  const visual = aparencia(step);
  if (!visual) return null;

  return (
    <div className="space-y-4" aria-live="polite">
      <div className={`rounded-lg border px-4 py-3 ${visual.classe}`}>
        <p className="text-sm font-semibold">{visual.titulo}</p>
        <p className="mt-1 text-[0.85rem] opacity-90">{visual.texto}</p>
      </div>

      {report ? <ValidationSummary report={report} /> : null}

      {result ? (
        <>
          <p className="text-[0.8rem] text-muted">
            Duração: {(result.duration_ms / 1000).toFixed(1)}s · o arquivo
            original não foi alterado.
          </p>

          {result.artifacts.length > 0 ? (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                Arquivos desta execução
              </h4>
              <ul className="space-y-2">
                {[...result.artifacts]
                  .sort(
                    (a, b) => ordemDoArtefato(a.name) - ordemDoArtefato(b.name),
                  )
                  .map((artefato) => (
                    <li key={artefato.name}>
                      <a
                        href={artefato.download_url}
                        download
                        className="flex items-center justify-between gap-3 rounded-lg border border-white/6 bg-ink px-4 py-3 text-sm hover:border-white/20"
                      >
                        <span className="min-w-0">
                          <span className="font-semibold text-fg">
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
          ) : null}
        </>
      ) : null}
    </div>
  );
}
