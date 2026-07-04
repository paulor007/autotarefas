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
import { useValidationReport } from "./hooks/useValidationReport";
import {
  getCatalog,
  getHealth,
  type Automation,
  type Catalog as CatalogData,
  type Health,
} from "./lib/api";

// Saida de exemplo: linhas reais representativas do stdout do AutoTarefas
// (Auditoria de planilha com o clientes.csv de exemplo). Some na 1a execucao
// real, quando o terminal recebe o stdout ao vivo do SSE (/api/stream/{token}).
const SAMPLE_LINES: TerminalLine[] = [
  {
    kind: "command",
    text: "autotarefas validate clientes.csv --mode limpeza --out-dir out/",
  },
  { kind: "plain", text: "Schema carregado: 5 coluna(s) declarada(s)." },
  { kind: "plain", text: "Modo: limpeza" },
  { kind: "plain", text: "Validando arquivo: clientes.csv" },
  { kind: "plain", text: "Encontrados 6 problema(s):" },
  {
    kind: "error",
    text: "[ERROR] Linha 7, coluna 'cpf': CPF invalido: '111.111.111-11'",
  },
  {
    kind: "error",
    text: "[ERROR] Linha 8, coluna 'cpf': Valor duplicado na coluna 'cpf' (linhas 3, 8)",
  },
  {
    kind: "warn",
    text: "[LIMPEZA] 6 valor(es) normalizado(s) com seguranca (nenhum dado foi inventado)",
  },
  { kind: "ok", text: "[OK] Registros validos:   out/registros_validos.csv" },
  { kind: "ok", text: "[OK] Registros invalidos: out/registros_invalidos.csv" },
  { kind: "ok", text: "[OK] Planilha validada:   out/planilha_validada.xlsx" },
  { kind: "ok", text: "[OK] Relatorio JSON:      out/validacao_report.json" },
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
      <Artifacts result={exec.result} report={validationReport} />
      <Footer />
    </div>
  );
}
