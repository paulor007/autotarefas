import { useEffect, useMemo, useState } from "react";

import Artifacts from "./components/Artifacts";
import Catalog from "./components/Catalog";
import ExecutionPanel from "./components/ExecutionPanel";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import Navbar from "./components/Navbar";
import StatusBar from "./components/StatusBar";
import TerminalView, { type TerminalLine } from "./components/TerminalView";
import { useExecution } from "./hooks/useExecution";
import { useImportReport } from "./hooks/useImportReport";
import { useValidationReport } from "./hooks/useValidationReport";
import {
  getCatalog,
  getHealth,
  type Automation,
  type Catalog as CatalogData,
  type Health,
} from "./lib/api";

// Saida de exemplo: linhas reais representativas do stdout do AutoTarefas
// (Cadastro automatico via planilha com o leads.csv de exemplo). Some na 1a
// execucao real, quando o terminal recebe o stdout ao vivo do SSE
// (/api/stream/{token}). Mostra o momento do retry (registro que se recupera
// sozinho) e os 4 artefatos gerados.
const SAMPLE_LINES: TerminalLine[] = [
  {
    kind: "command",
    text: "autotarefas send api registros_validos.csv --out-dir envio/",
  },
  {
    kind: "plain",
    text: "Enviando 8 registros para o sistema (com Idempotency-Key)",
  },
  { kind: "ok", text: "  [1/8] [OK] criado (id 1)" },
  { kind: "ok", text: "  [4/8] [OK] criado (id 4)" },
  { kind: "warn", text: "  [5/8] [OK] criado (id 5)  (2 tentativas)" },
  {
    kind: "error",
    text: "  [6/8] [FALHA] HTTP 422: CPF invalido: '111.111.111'",
  },
  { kind: "error", text: "  [7/8] [FALHA] HTTP 409: CPF ja cadastrado" },
  { kind: "ok", text: "[OK] Enviados:  envio/registros_enviados.csv" },
  {
    kind: "ok",
    text: "[OK] Falhos:    envio/registros_falhos.csv (reenviavel)",
  },
  { kind: "ok", text: "[OK] Relatorio: envio/importacao_report.json" },
  {
    kind: "done",
    text: "Total: 8 | Enviados: 6 | Falhas: 2 (validacao 1, duplicado 1)",
  },
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<CatalogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hasInteracted, setHasInteracted] = useState(false);

  const exec = useExecution();
  const validationReport = useValidationReport(exec.result);
  const importReport = useImportReport(exec.result);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getHealth(), getCatalog()])
      .then(([h, c]) => {
        if (!cancelled) {
          setHealth(h);
          setCatalog(c);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "falha ao conectar");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeIds = useMemo(
    () => new Set(health?.active_automations ?? []),
    [health],
  );
  const online = !!health && (health.demo_servers[0]?.alive ?? false);
  const selectedAutomation = useMemo(
    () => catalog?.automations.find((a) => a.id === selectedId) ?? null,
    [catalog, selectedId],
  );

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setTimeout(() => {
      document
        .getElementById("execucao")
        ?.scrollIntoView({ behavior: "smooth" });
    }, 150);
  };

  const handleRun = (
    automation: Automation,
    opts: { files?: File[]; useSample?: boolean },
  ) => {
    setHasInteracted(true);
    void exec.run(automation, opts);
    setTimeout(() => {
      document
        .getElementById("terminal")
        ?.scrollIntoView({ behavior: "smooth" });
    }, 150);
  };

  const terminalLines = hasInteracted ? exec.lines : SAMPLE_LINES;

  return (
    <div className="min-h-screen">
      <Navbar online={online} />
      <Hero health={health} />
      <StatusBar health={health} />
      <Catalog
        catalog={catalog}
        activeIds={activeIds}
        selectedId={selectedId}
        onSelect={handleSelect}
        loading={loading}
        error={error}
      />
      <ExecutionPanel
        selected={selectedAutomation}
        status={exec.status}
        error={exec.error}
        onRun={handleRun}
      />
      <TerminalView
        lines={terminalLines}
        status={exec.status}
        outcome={exec.result?.outcome}
        sample={!hasInteracted}
        onClear={hasInteracted ? exec.reset : undefined}
      />
      <Artifacts
        result={exec.result}
        report={validationReport}
        importReport={importReport}
        onNextStep={() => handleSelect("send_api")}
      />
      <Footer />
    </div>
  );
}
