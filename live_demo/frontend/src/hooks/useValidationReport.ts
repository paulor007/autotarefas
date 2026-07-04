import { useEffect, useState } from "react";

import {
  getValidationReport,
  VALIDATION_REPORT_NAME,
  type RunResult,
  type ValidationReport,
} from "../lib/api";

/**
 * Busca o validacao_report.json quando a execucao concluida o gerou.
 *
 * A Auditoria de planilha expoe o relatorio como artefato; este hook o
 * localiza pelo nome canonico e faz o fetch do download_url. Para as
 * demais automacoes (sem esse artefato) retorna null e nada e buscado.
 */
export function useValidationReport(
  result: RunResult | null,
): ValidationReport | null {
  const [report, setReport] = useState<ValidationReport | null>(null);

  useEffect(() => {
    setReport(null);
    const artifact = result?.artifacts.find(
      (a) => a.name === VALIDATION_REPORT_NAME,
    );
    if (!artifact) {
      return;
    }

    let cancelled = false;
    getValidationReport(artifact.download_url)
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
