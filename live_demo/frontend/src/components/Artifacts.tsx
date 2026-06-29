import { FolderOpen } from "lucide-react";

import SectionHeader from "./SectionHeader";

export default function Artifacts() {
  return (
    <section id="artefatos" className="bg-elevated py-20">
      <div className="container-page">
        <SectionHeader
          title="Artefatos Gerados"
          subtitle="Resultados prontos para download após a execução"
        />

        <div className="mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl border border-dashed border-white/[0.08] bg-surface px-6 py-14 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white/[0.04] text-muted">
            <FolderOpen className="h-6 w-6" />
          </div>
          <p className="text-sm font-medium text-fg">Nenhum artefato ainda</p>
          <p className="max-w-sm text-sm text-muted">
            Os artefatos aparecerão aqui após uma execução real. O download dos
            resultados será conectado ao backend no Front-2.
          </p>
        </div>
      </div>
    </section>
  );
}
