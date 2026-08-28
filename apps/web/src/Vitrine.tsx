/**
 * A vitrine: `/`.
 *
 * O que alguem ve antes de ter conta. Catalogo, demonstracao que roda de
 * verdade em espaco isolado, e a saida dela.
 *
 * O produto nao mora aqui. Ele morava — a plataforma inteira (organizacao,
 * dispositivos, politicas, historico, auditoria) ficava numa secao `#empresa`
 * no fim desta pagina, depois de cinco telas de demonstracao. Quem ja era
 * cliente rolava a vitrine toda para chegar ao proprio produto, e quem
 * procurava "Parear nova maquina" nao achava. Agora o produto e `/app`.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import Artifacts from "./components/Artifacts";
import Catalog from "./components/Catalog";
import ExecutionPanel from "./components/ExecutionPanel";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import Navbar from "./components/Navbar";
import StatusBar from "./components/StatusBar";
import TerminalView, { type TerminalLine } from "./components/TerminalView";
import { useExecution } from "./hooks/useExecution";
import { useExtractReport } from "./hooks/useExtractReport";
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
// (Exportacao automatica de dados com o catalogo de demonstracao). Some na
// 1a execucao real, quando o terminal recebe o stdout ao vivo do SSE
// (/api/stream/{token}). A Exportacao e a origem do pipeline: puxa a base
// de um sistema, paginando, e gera os artefatos.
const SAMPLE_LINES: TerminalLine[] = [
  {
    kind: "command",
    text: "autotarefas extract api -u .../api/catalogo --out-dir saida/",
  },
  { kind: "plain", text: "Extraindo de http://.../api/catalogo" },
  { kind: "plain", text: "  Pagina 1/5 ... 10 registros (total: 10)" },
  { kind: "plain", text: "  Pagina 3/5 ... 10 registros (total: 30)" },
  { kind: "plain", text: "  Pagina 5/5 ... 7 registros (total: 47)" },
  { kind: "ok", text: "Extraidos 47 registros" },
  { kind: "ok", text: "[OK] Dados (CSV):    saida/dados_extraidos.csv" },
  { kind: "ok", text: "[OK] Dados (Excel):  saida/dados_extraidos.xlsx" },
  { kind: "ok", text: "[OK] Relatorio JSON: saida/extracao_report.json" },
  {
    kind: "done",
    text: "47 registros em 5 paginas -> prontos para a Auditoria de planilha",
  },
];

export default function Vitrine() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<CatalogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hasInteracted, setHasInteracted] = useState(false);

  const exec = useExecution();
  const validationReport = useValidationReport(exec.result);
  const importReport = useImportReport(exec.result);
  const extractReport = useExtractReport(exec.result);

  // A carga fica em `useCallback` para o botao "Tentar novamente" refazer
  // exatamente a mesma consulta — sem recarregar a pagina inteira.
  const [tentativa, setTentativa] = useState(0);
  const recarregar = useCallback(() => {
    setTentativa((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getHealth(), getCatalog()])
      .then(([h, c]) => {
        if (!cancelled) {
          setHealth(h);
          setCatalog(c);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          // O detalhe tecnico vai para o console de dev; a tela recebe uma
          // mensagem util. Um ECONNREFUSED do proxy nao e "erro 500 do
          // servidor" — e o servico nao estar acessivel.
          console.error("[AutoTarefas] falha ao consultar a API", e);
          setError(
            e instanceof Error && e.message.includes("respondeu")
              ? "serviço indisponível no momento"
              : "não foi possível falar com o serviço",
          );
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
  }, [tentativa]);

  const activeIds = useMemo(
    () => new Set(health?.active_automations ?? []),
    [health],
  );
  // "Sistema operacional" e sobre O SISTEMA responder, nao sobre os servidores
  // de demonstracao. Antes isto olhava `demo_servers[0].alive`: com os mocks
  // desligados (eles so servem aos cards de integracao) a barra ficava em
  // "Conectando..." para sempre, com o Live inteiro no ar.
  const online = health?.status === "ok";
  // O card de planilhas abre a jornada guiada, que nao usa o fluxo classico.
  const emJornada = selectedId === "validate";

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
        onRetry={recarregar}
      />
      <ExecutionPanel
        selected={selectedAutomation}
        status={exec.status}
        error={exec.error}
        onRun={handleRun}
      />
      {/* O terminal e os artefatos abaixo pertencem ao FLUXO CLASSICO
          (/api/run). A jornada de planilhas tem execucao propria e mostra o
          registro e os resultados dentro dela — deixar estas secoes visiveis
          exibia o resultado de uma automacao ANTERIOR como se fizesse parte da
          analise em curso. */}
      {!emJornada ? (
        <>
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
            extractReport={extractReport}
            onNextStep={() => handleSelect("send_api")}
            onNextStepAudit={() => handleSelect("validate")}
          />
        </>
      ) : null}
      <Footer />
    </div>
  );
}
