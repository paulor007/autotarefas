import { useEffect, useState } from "react";

import {
  EXTRACT_REPORT_NAME,
  getExtractReport,
  type ExtractReport,
  type RunResult,
} from "../lib/api";

/**
 * Busca o extracao_report.json quando a execucao concluida o gerou.
 *
 * A Exportacao automatica de dados expoe o relatorio como artefato; este
 * hook o localiza pelo nome canonico e faz o fetch do download_url. Para
 * as demais automacoes (sem esse artefato) retorna null e nada e buscado.
 * Espelha o useImportReport/useValidationReport (duplicacao consciente:
 * contratos JSON diferentes, componentes independentes).
 */
export function useExtractReport(
  result: RunResult | null,
): ExtractReport | null {
  const [report, setReport] = useState<ExtractReport | null>(null);

  useEffect(() => {
    setReport(null);
    const artifact = result?.artifacts.find(
      (a) => a.name === EXTRACT_REPORT_NAME,
    );
    if (!artifact) {
      return;
    }

    let cancelled = false;
    getExtractReport(artifact.download_url)
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
