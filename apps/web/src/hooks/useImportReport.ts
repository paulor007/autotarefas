import { useEffect, useState } from "react";

import {
  getImportReport,
  IMPORT_REPORT_NAME,
  type ImportReport,
  type RunResult,
} from "../lib/api";

/**
 * Busca o importacao_report.json quando a execucao concluida o gerou.
 *
 * O Cadastro automatico via planilha expoe o relatorio como artefato;
 * este hook o localiza pelo nome canonico e faz o fetch do download_url.
 * Para as demais automacoes (sem esse artefato) retorna null e nada e
 * buscado. Espelha o useValidationReport da Auditoria (duplicacao
 * consciente: contratos JSON diferentes, componentes independentes).
 */
export function useImportReport(result: RunResult | null): ImportReport | null {
  const [report, setReport] = useState<ImportReport | null>(null);

  useEffect(() => {
    setReport(null);
    const artifact = result?.artifacts.find(
      (a) => a.name === IMPORT_REPORT_NAME,
    );
    if (!artifact) {
      return;
    }

    let cancelled = false;
    getImportReport(artifact.download_url)
      .then((data) => {
        if (!cancelled) {
          setReport(data);
        }
      })
      .catch(() => {
        // Sem resumo visual neste caso; os downloads continuam disponiveis.
      });
    return () => {
      cancelled = true;
    };
  }, [result]);

  return report;
}
