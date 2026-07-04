import {
  Download,
  File,
  FileArchive,
  FileJson,
  FileSpreadsheet,
  type LucideIcon,
} from "lucide-react";

import type { Artifact, RunResult, ValidationReport } from "../lib/api";
import SectionHeader from "./SectionHeader";
import ValidationSummary from "./ValidationSummary";

function iconForFile(name: string): LucideIcon {
  const n = name.toLowerCase();
  if (n.endsWith(".json")) return FileJson;
  if (n.endsWith(".zip")) return FileArchive;
  if (n.endsWith(".csv") || n.endsWith(".tsv") || n.endsWith(".xlsx"))
    return FileSpreadsheet;
  return File;
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Artifacts({
  result,
  report,
}: {
  result: RunResult | null;
  report?: ValidationReport | null;
}) {
  const artifacts: Artifact[] = result?.artifacts ?? [];

  return (
    <section id="artefatos" className="bg-elevated py-20">
      <div className="container-page">
        <SectionHeader
          title="Artefatos Gerados"
          subtitle="Resultados prontos para download após a execução"
        />

        {!result ? (
          <div className="mx-auto flex max-w-lg flex-col items-center gap-3 rounded-2xl border border-dashed border-white/8 bg-surface px-6 py-14 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white/4 text-muted">
              <File className="h-6 w-6" />
            </div>
            <p className="text-sm font-medium text-fg">Nenhum artefato ainda</p>
            <p className="max-w-sm text-sm text-muted">
              Os artefatos aparecerão aqui após uma execução. Use o painel acima
              para executar uma automação.
            </p>
          </div>
        ) : (
          <>
            <div className="mx-auto mb-6 flex max-w-3xl flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs text-muted">
              <span>
                resultado:{" "}
                <span
                  className={`font-mono ${
                    result.outcome === "ok"
                      ? "text-ok"
                      : result.outcome === "caught_issue"
                        ? "text-signal"
                        : "text-danger"
                  }`}
                >
                  {result.outcome}
                </span>
              </span>
              <span className="opacity-30">·</span>
              <span>
                exit{" "}
                <span className="font-mono text-fg">{result.exit_code}</span>
              </span>
              <span className="opacity-30">·</span>
              <span className="font-mono text-fg">
                {(result.duration_ms / 1000).toFixed(1)}s
              </span>
            </div>

            {report && <ValidationSummary report={report} />}

            {artifacts.length === 0 ? (
              <p className="text-center text-sm text-muted">
                Execução concluída sem artefatos para download.
              </p>
            ) : (
              <div className="mx-auto grid max-w-3xl grid-cols-1 gap-3 sm:grid-cols-2">
                {artifacts.map((art) => {
                  const Icon = iconForFile(art.name);
                  return (
                    <div
                      key={art.name}
                      className="flex items-center gap-3 rounded-xl border border-white/6 bg-surface p-4 transition-colors hover:border-white/12"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cyan/10 text-cyan">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="flex min-w-0 grow flex-col">
                        <span className="truncate font-mono text-sm text-fg">
                          {art.name}
                        </span>
                        <span className="text-[0.68rem] text-muted">
                          {humanSize(art.bytes)}
                        </span>
                      </div>
                      <a
                        href={art.download_url}
                        download
                        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-cyan/30 px-3 py-1.5 text-xs font-semibold text-cyan transition-colors hover:bg-cyan/10"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Baixar
                      </a>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
