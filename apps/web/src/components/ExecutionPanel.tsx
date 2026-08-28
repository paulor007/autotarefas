import { useEffect, useState } from "react";
import { FileUp, Loader2, Play } from "lucide-react";

import type { RunStatus } from "../hooks/useExecution";
import ErrorBoundary from "./ErrorBoundary";
import SpreadsheetJourney from "./SpreadsheetJourney";
import type { Automation, UploadKind } from "../lib/api";
import DemoSource from "./DemoSource";
import FileDrop from "./FileDrop";
import SectionHeader from "./SectionHeader";
import { cliqueDeNavegacao, PRODUTO } from "../lib/rotas";

// Automacoes que realmente tem exemplo disponivel no backend.
const SAMPLE_IDS = new Set(["validate", "backup", "organize", "send_api"]);

// accept para upload do tipo "folder" (qualquer extensao permitida pelo backend).
const FOLDER_ACCEPT =
  ".csv,.tsv,.txt,.pdf,.docx,.xlsx,.jpg,.jpeg,.png,.json,.yaml,.yml";

// accept para upload do tipo "spreadsheet" (Auditoria de planilha).
const SPREADSHEET_ACCEPT = ".csv,.xlsx";

/** Card que abre a jornada guiada em vez do fluxo classico de execucao. */
const SPREADSHEET_JOURNEY_ID = "validate";

/**
 * Titulo da secao de entrada.
 *
 * O backup ganha nome proprio: enviar arquivos pelo navegador e a porta de
 * entrada do card, nao o produto. Chamar isso de "arquivo de entrada"
 * esconderia que existe um caminho maior — o das pastas da maquina, que
 * chega com o agente.
 */
function entradaTitulo(automation: Automation): string {
  // "Proteger" era a palavra do produto. Aqui nao se protege nada: se
  // empacota o que a pessoa acabou de entregar, uma vez.
  if (automation.id === "backup") return "Compactar com comprovante";
  return `Arquivo de entrada ${uploadLabel(automation.upload)}`;
}

function uploadLabel(upload: string): string {
  if (upload === "csv") return "(.csv)";
  if (upload === "spreadsheet") return "(.csv ou .xlsx)";
  return "(um ou mais arquivos)";
}

function uploadAccept(upload: string): string {
  if (upload === "csv") return ".csv";
  if (upload === "spreadsheet") return SPREADSHEET_ACCEPT;
  return FOLDER_ACCEPT;
}

// A etapa 2 depende do TIPO DE ENTRADA da automacao, nao do id dela:
// quem recebe arquivo envia um arquivo; quem nao recebe (upload "none")
// roda contra um servico de demonstracao interno — a "entrada" e a origem.
function inputStep(upload: UploadKind): { title: string; desc: string } {
  if (upload === "none") {
    return { title: "Selecionar origem", desc: "Usar serviço de demonstração" };
  }
  return { title: "Enviar arquivo", desc: "Upload ou usar exemplo" };
}

function buildSteps(
  upload: UploadKind,
): { num: number; title: string; desc: string }[] {
  const entrada = inputStep(upload);
  return [
    { num: 1, title: "Escolher Automação", desc: "Selecione no catálogo" },
    { num: 2, title: entrada.title, desc: entrada.desc },
    { num: 3, title: "Executar", desc: "Processar em espaço isolado" },
    { num: 4, title: "Execução", desc: "Acompanhar o andamento" },
    { num: 5, title: "Resultados", desc: "Baixar evidências" },
  ];
}

function activeStep(
  status: RunStatus,
  hasSelection: boolean,
  hasInput: boolean,
  needsFile: boolean,
): number {
  if (status === "starting" || status === "running") return 3;
  if (status === "done" || status === "timeout") return 5;
  if (!hasSelection) return 1;
  // Sem upload, a origem ja esta definida (servico de demonstracao):
  // o visitante ja pode executar.
  if (!needsFile) return 3;
  return hasInput ? 3 : 2;
}

interface Props {
  selected: Automation | null;
  status: RunStatus;
  error: string | null;
  onRun: (
    automation: Automation,
    opts: { files?: File[]; useSample?: boolean },
  ) => void;
}

export default function ExecutionPanel({
  selected,
  status,
  error,
  onRun,
}: Props) {
  const [files, setFiles] = useState<File[]>([]);

  // Trocar de automacao limpa os arquivos escolhidos.
  useEffect(() => {
    setFiles([]);
  }, [selected?.id]);

  const busy = status === "starting" || status === "running";
  const upload = selected?.upload ?? "none";
  const needsFile = upload !== "none";
  const hasSample = selected ? SAMPLE_IDS.has(selected.id) : false;
  const canRunFile = !!selected && (!needsFile || files.length > 0) && !busy;
  const steps = buildSteps(upload);
  const step = activeStep(status, !!selected, files.length > 0, needsFile);

  const runFile = () => {
    if (selected && canRunFile) {
      onRun(selected, { files: needsFile ? files : [] });
    }
  };
  const runSample = () => {
    if (selected && !busy) {
      onRun(selected, { useSample: true });
    }
  };

  // A Analise e validacao de planilhas tem jornada propria (analisar antes de
  // validar), com endpoints proprios. Os demais cards seguem no fluxo classico
  // de /api/run — nada foi removido deles.
  if (selected?.id === SPREADSHEET_JOURNEY_ID) {
    return (
      <section id="execucao" className="bg-elevated py-20">
        <div className="container-page">
          <SectionHeader
            title="Análise e organização de planilhas"
            subtitle="Analise CSV e XLSX, revise a estrutura, confirme as regras e as correções seguras, e separe registros válidos dos que precisam de revisão"
          />
          <div className="overflow-hidden rounded-2xl border border-white/6 bg-surface">
            <div className="space-y-6 p-6 sm:p-8">
              {/* A barreira mantem a pagina de pe se um render falhar. */}
              <ErrorBoundary area="jornada de planilhas">
                <SpreadsheetJourney />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section id="execucao" className="bg-elevated py-20">
      <div className="container-page">
        <SectionHeader
          title="Painel de Execução"
          subtitle="Configure a execução e acompanhe cada etapa"
        />

        <div className="overflow-hidden rounded-2xl border border-white/6 bg-surface">
          {/* Stepper */}
          <div className="flex gap-2 overflow-x-auto border-b border-white/6 p-5">
            {steps.map((s) => {
              const isActive = s.num === step;
              return (
                <div
                  key={s.num}
                  className={`flex min-w-fit flex-1 items-center gap-3 rounded-lg px-4 py-3 ${
                    isActive ? "bg-signal/10" : ""
                  }`}
                >
                  <div
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      isActive
                        ? "bg-signal text-black"
                        : "border border-white/6 bg-ink text-muted"
                    }`}
                  >
                    {s.num}
                  </div>
                  <div className="min-w-0">
                    <div className="whitespace-nowrap text-[0.8rem] font-semibold text-fg">
                      {s.title}
                    </div>
                    <div className="whitespace-nowrap text-[0.68rem] text-muted">
                      {s.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Workspace */}
          <div className="space-y-6 p-6 sm:p-8">
            <div>
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted">
                Automação selecionada
              </span>
              <div className="rounded-lg border border-white/6 bg-ink p-3 text-sm">
                {selected ? (
                  <span className="font-semibold text-signal">
                    {selected.title}
                  </span>
                ) : (
                  <span className="text-muted">
                    Nenhuma selecionada — escolha uma no catálogo acima
                  </span>
                )}
              </div>
            </div>

            {selected && needsFile && (
              <div>
                <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted">
                  {entradaTitulo(selected)}
                </span>
                {selected.upload_hint && (
                  <p className="mb-2 text-[0.85rem] text-muted">
                    {selected.upload_hint}
                  </p>
                )}
                <FileDrop
                  accept={uploadAccept(upload)}
                  multiple={upload === "folder"}
                  files={files}
                  onChange={setFiles}
                  disabled={busy}
                />
              </div>
            )}

            {selected && !needsFile && (
              <div>
                <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted">
                  Origem dos dados
                </span>
                <DemoSource automation={selected} />
              </div>
            )}

            {/* Sao coisas diferentes, e a tela nao pode deixar confundir uma
                com a outra: aqui o servidor empacota o que voce ENTREGA; no
                produto o Agente protege o que voce TEM. Este aviso existe para
                quem chegou pelo catalogo achando que o envio avulso ja e
                backup — e para levar quem quer o backup de verdade. */}
            {selected?.has_product_version && (
              <div className="rounded-lg border border-white/8 bg-ink px-4 py-3">
                <p className="text-[0.85rem] font-semibold text-fg">
                  Isto compacta o que você enviar. O Backup automático protege o
                  que você já tem.
                </p>
                <p className="mt-1 text-[0.85rem] text-muted">
                  Aqui você entrega arquivos, uma vez, com limite de 10 MB por
                  arquivo — que é limite do navegador. Você faz, você baixa,
                  você guarda. Serve para ver o comprovante funcionando sem
                  instalar nada.
                </p>
                <p className="mt-2 text-[0.85rem] text-muted">
                  O <strong>Backup automático</strong> protege pastas inteiras
                  do computador, no horário, sozinho, com o navegador fechado,
                  para disco externo ou nuvem, com retenção e restauração. Ele
                  exige conta e o Agente instalado — porque nenhum navegador
                  alcança o disco de ninguém.
                </p>
                <a
                  href={PRODUTO}
                  onClick={cliqueDeNavegacao(PRODUTO)}
                  className="mt-3 inline-block rounded-lg border border-signal/40 bg-signal/10 px-3 py-1.5 text-[0.8rem] font-semibold text-signal hover:border-signal/70"
                >
                  Abrir o backup automático
                </a>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger">
                {error}
              </div>
            )}

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={runFile}
                disabled={!canRunFile}
                className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold transition-all ${
                  canRunFile
                    ? "bg-signal text-black shadow-[0_0_20px_rgba(240,177,0,0.2)] hover:bg-amber-400 hover:shadow-[0_0_30px_rgba(240,177,0,0.3)]"
                    : "cursor-not-allowed bg-signal/40 text-black/70"
                }`}
              >
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 fill-current" />
                )}
                {busy ? "Executando…" : "Executar agora"}
              </button>

              {hasSample && (
                <button
                  type="button"
                  onClick={runSample}
                  disabled={busy}
                  className={`inline-flex items-center justify-center gap-2 rounded-lg border px-5 py-2.5 text-sm font-medium transition-colors ${
                    busy
                      ? "cursor-not-allowed border-white/10 text-muted"
                      : "border-signal/30 text-signal hover:bg-signal/10"
                  }`}
                >
                  <FileUp className="h-4 w-4" />
                  Usar exemplo
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
