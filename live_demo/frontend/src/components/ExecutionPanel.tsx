import { FileUp, Info, Play, Upload } from "lucide-react";

import type { Automation } from "../lib/api";
import SectionHeader from "./SectionHeader";

const STEPS = [
  { num: 1, title: "Escolher Automação", desc: "Selecione no catálogo" },
  { num: 2, title: "Enviar Arquivo", desc: "Upload ou usar exemplo" },
  { num: 3, title: "Executar", desc: "Rodar no sandbox" },
  { num: 4, title: "Terminal ao Vivo", desc: "Acompanhar stdout" },
  { num: 5, title: "Baixar Artefatos", desc: "Download dos resultados" },
];

export default function ExecutionPanel({
  selected,
}: {
  selected: Automation | null;
}) {
  return (
    <section id="execucao" className="bg-elevated py-20">
      <div className="container-page">
        <SectionHeader
          title="Painel de Execução"
          subtitle="Configure e execute automações em tempo real"
        />

        <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-surface">
          {/* Stepper */}
          <div className="flex gap-2 overflow-x-auto border-b border-white/[0.06] p-5">
            {STEPS.map((step) => (
              <div
                key={step.num}
                className={`flex min-w-fit flex-1 items-center gap-3 rounded-lg px-4 py-3 ${
                  step.num === 1 ? "bg-signal/10" : ""
                }`}
              >
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    step.num === 1
                      ? "bg-signal text-black"
                      : "border border-white/[0.06] bg-ink text-muted"
                  }`}
                >
                  {step.num}
                </div>
                <div className="min-w-0">
                  <div className="whitespace-nowrap text-[0.8rem] font-semibold text-fg">
                    {step.title}
                  </div>
                  <div className="whitespace-nowrap text-[0.68rem] text-muted">
                    {step.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Workspace */}
          <div className="space-y-6 p-6 sm:p-8">
            <div>
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted">
                Automação selecionada
              </span>
              <div className="rounded-lg border border-white/[0.06] bg-ink p-3 text-sm">
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

            <div>
              <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-muted">
                Arquivo de entrada
              </span>
              <div className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed border-white/[0.06] p-8 text-center text-muted opacity-70">
                <Upload className="h-6 w-6" />
                <span className="text-sm">
                  Upload e execução serão conectados ao backend no Front-2
                </span>
                <span className="text-xs opacity-60">
                  Esta área já reflete a automação selecionada acima
                </span>
              </div>
            </div>

            {/* Aviso honesto: ainda sem execucao real */}
            <div className="flex items-start gap-3 rounded-lg border border-cyan/20 bg-cyan/[0.06] px-4 py-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-cyan" />
              <p className="text-sm text-muted">
                <span className="font-medium text-fg">Pré-visualização.</span> A
                execução real — upload, disparo no sandbox e stdout ao vivo via
                SSE — será conectada ao backend na próxima etapa (Front-2). Nada
                é simulado aqui.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                disabled
                aria-disabled
                className="inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-signal/40 px-5 py-2.5 text-sm font-semibold text-black/70"
              >
                <Play className="h-4 w-4 fill-current" />
                Executar agora (em breve)
              </button>
              <button
                type="button"
                disabled
                aria-disabled
                className="inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-lg border border-white/10 px-5 py-2.5 text-sm font-medium text-muted"
              >
                <FileUp className="h-4 w-4" />
                Usar exemplo (em breve)
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
