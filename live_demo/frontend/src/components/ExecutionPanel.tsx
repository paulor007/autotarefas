import { useEffect, useState } from "react";
import { FileUp, Info, Loader2, Play } from "lucide-react";

import type { RunStatus } from "../hooks/useExecution";
import type { Automation } from "../lib/api";
import FileDrop from "./FileDrop";
import SectionHeader from "./SectionHeader";

// Automacoes que realmente tem exemplo disponivel no backend.
const SAMPLE_IDS = new Set(["validate", "backup", "organize", "send_api"]);

// accept para upload do tipo "folder" (qualquer extensao permitida pelo backend).
const FOLDER_ACCEPT =
  ".csv,.tsv,.txt,.pdf,.docx,.xlsx,.jpg,.jpeg,.png,.json,.yaml,.yml";

// accept para upload do tipo "spreadsheet" (Auditoria de planilha).
const SPREADSHEET_ACCEPT = ".csv,.xlsx";

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

const STEPS = [
  { num: 1, title: "Escolher Automação", desc: "Selecione no catálogo" },
  { num: 2, title: "Enviar Arquivo", desc: "Upload ou usar exemplo" },
  { num: 3, title: "Executar", desc: "Rodar no sandbox" },
  { num: 4, title: "Terminal ao Vivo", desc: "Acompanhar stdout" },
  { num: 5, title: "Baixar Artefatos", desc: "Download dos resultados" },
];

function activeStep(
  status: RunStatus,
  hasSelection: boolean,
  hasInput: boolean,
): number {
  if (status === "starting" || status === "running") return 3;
  if (status === "done" || status === "timeout") return 5;
  if (!hasSelection) return 1;
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
  const step = activeStep(status, !!selected, files.length > 0);

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

  return (
    <section id="execucao" className="bg-elevated py-20">
      <div className="container-page">
        <SectionHeader
          title="Painel de Execução"
          subtitle="Configure e execute automações em tempo real"
        />

        <div className="overflow-hidden rounded-2xl border border-white/6 bg-surface">
          {/* Stepper */}
          <div className="flex gap-2 overflow-x-auto border-b border-white/6 p-5">
            {STEPS.map((s) => {
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
                  Arquivo de entrada {uploadLabel(upload)}
                </span>
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
              <div className="flex items-start gap-3 rounded-lg border border-cyan/20 bg-cyan/6 px-4 py-3">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
                <p className="text-sm text-muted">
                  Esta automação não precisa de upload — roda direto no sandbox
                  contra os serviços internos.
                </p>
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
                {busy
                  ? "Executando…"
                  : needsFile
                    ? "Executar com arquivo"
                    : "Executar agora"}
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
