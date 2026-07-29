import { useCallback, useEffect, useRef, useState } from "react";

import {
  analyzeSpreadsheet,
  confirmSuggestedSchema,
  JourneyError,
  selectReading,
  startValidation,
  uploadSchema,
  type AnalysisResponse,
  type SchemaResponse,
} from "../lib/spreadsheets";
import { useExecution, type UseExecution } from "./useExecution";

/**
 * Etapas da jornada, do ponto de vista da INTERFACE.
 *
 * Nao sao os mesmos nomes que o backend usa: ele descreve o estado do
 * servidor, e aqui descrevemos o que a pessoa esta vendo (por exemplo,
 * `choosing_schema` e `schema_uploading` sao momentos de tela que o backend
 * nem conhece). O backend continua sendo a FONTE DE VERDADE — quando ele
 * responde, o estado da tela e derivado da resposta, nunca de texto do
 * terminal.
 */
export type JourneyStep =
  | "idle"
  | "file_selected"
  | "analyzing"
  | "needs_selection"
  | "analysis_ready"
  | "choosing_schema"
  | "schema_uploading"
  | "schema_invalid"
  | "schema_ready"
  | "reviewing"
  | "validating"
  | "completed"
  | "completed_with_issues"
  | "invalid_configuration"
  | "rejected_file"
  | "technical_failure"
  | "timed_out"
  | "expired";

/** Estados em que a jornada terminou (com ou sem problemas). */
const FINISHED: ReadonlySet<JourneyStep> = new Set<JourneyStep>([
  "completed",
  "completed_with_issues",
  "invalid_configuration",
  "technical_failure",
  "timed_out",
]);

const EXIT_OK = 0;
const EXIT_DATA_PROBLEMS = 1;
const EXIT_USAGE = 2;

export interface UseSpreadsheetJourney {
  step: JourneyStep;
  file: File | null;
  analysis: AnalysisResponse | null;
  schema: SchemaResponse | null;
  error: string | null;
  /** Mensagem do backend quando o arquivo foi recusado. */
  rejection: string | null;
  token: string | null;
  execution: UseExecution;
  busy: boolean;

  chooseFile: (file: File | null) => void;
  analyzeFile: () => Promise<void>;
  analyzeSample: () => Promise<void>;
  choose: (choice: { sheet?: string; headerRow?: number }) => Promise<void>;
  useSuggested: () => Promise<void>;
  sendSchema: (file: File) => Promise<void>;
  goToSchemaChoice: () => void;
  goToReview: () => void;
  validate: () => Promise<void>;
  reset: () => void;
}

export function useSpreadsheetJourney(): UseSpreadsheetJourney {
  const [step, setStep] = useState<JourneyStep>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejection, setRejection] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const execution = useExecution();

  // Nada de setState depois que o componente saiu de cena: uma resposta que
  // chega tarde nao pode "ressuscitar" a tela.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const reset = useCallback(() => {
    execution.reset();
    setStep("idle");
    setFile(null);
    setAnalysis(null);
    setSchema(null);
    setError(null);
    setRejection(null);
    setToken(null);
    setBusy(false);
  }, [execution]);

  /** Traduz uma falha de chamada em estado de tela. */
  const handleFailure = useCallback((e: unknown): void => {
    if (!mounted.current) return;
    if (e instanceof JourneyError) {
      if (e.expired) {
        // Sessao expirada: o token nao vale mais e insistir so gera erro.
        setStep("expired");
        setError(e.message);
        return;
      }
      setError(e.message);
      return;
    }
    setError("Não foi possível concluir a operação.");
  }, []);

  /** Aplica uma resposta de analise, derivando a etapa do que o backend disse. */
  const applyAnalysis = useCallback((data: AnalysisResponse) => {
    if (!mounted.current) return;
    setToken(data.token);
    setAnalysis(data);
    // A leitura mudou: o backend ja invalidou o schema confirmado, e a tela
    // nao pode continuar mostrando o resumo antigo como se valesse.
    setSchema(null);

    if (data.status === "rejected_file") {
      setRejection(data.detail ?? "Não foi possível ler este arquivo.");
      setStep("rejected_file");
      return;
    }
    setRejection(null);
    setStep(data.needs_choice ? "needs_selection" : "analysis_ready");
  }, []);

  const runAnalysis = useCallback(
    async (opts: { file?: File; useSample?: boolean }) => {
      setBusy(true);
      setError(null);
      setStep("analyzing");
      try {
        applyAnalysis(await analyzeSpreadsheet(opts));
      } catch (e: unknown) {
        handleFailure(e);
        if (mounted.current) setStep(file ? "file_selected" : "idle");
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [applyAnalysis, file, handleFailure],
  );

  const chooseFile = useCallback((next: File | null) => {
    setFile(next);
    setError(null);
    setStep(next ? "file_selected" : "idle");
  }, []);

  const analyzeFile = useCallback(async () => {
    if (file) await runAnalysis({ file });
  }, [file, runAnalysis]);

  const analyzeSample = useCallback(async () => {
    setFile(null);
    await runAnalysis({ useSample: true });
  }, [runAnalysis]);

  const choose = useCallback(
    async (choice: { sheet?: string; headerRow?: number }) => {
      if (!token) return;
      setBusy(true);
      setError(null);
      setStep("analyzing");
      try {
        applyAnalysis(await selectReading(token, choice));
      } catch (e: unknown) {
        handleFailure(e);
        if (mounted.current) setStep("needs_selection");
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [applyAnalysis, handleFailure, token],
  );

  const goToSchemaChoice = useCallback(() => {
    setError(null);
    setStep("choosing_schema");
  }, []);

  const goToReview = useCallback(() => {
    setError(null);
    setStep("reviewing");
  }, []);

  const applySchema = useCallback((data: SchemaResponse) => {
    if (!mounted.current) return;
    setSchema(data);
    setStep("schema_ready");
  }, []);

  const useSuggested = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      applySchema(await confirmSuggestedSchema(token));
    } catch (e: unknown) {
      handleFailure(e);
      if (mounted.current) setStep("choosing_schema");
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [applySchema, handleFailure, token]);

  const sendSchema = useCallback(
    async (schemaFile: File) => {
      if (!token) return;
      setBusy(true);
      setError(null);
      setStep("schema_uploading");
      try {
        applySchema(await uploadSchema(token, schemaFile));
      } catch (e: unknown) {
        handleFailure(e);
        // O backend preserva o ultimo schema valido: se havia um, a jornada
        // continua podendo seguir com ele; senao, volta para a escolha.
        if (mounted.current)
          setStep(schema ? "schema_invalid" : "choosing_schema");
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [applySchema, handleFailure, schema, token],
  );

  const validate = useCallback(async () => {
    if (!token || busy || step === "validating") return;
    setBusy(true);
    setError(null);
    setStep("validating");
    try {
      const started = await startValidation(token);
      execution.attach(started.token, started.stream_url);
    } catch (e: unknown) {
      handleFailure(e);
      if (mounted.current && !(e instanceof JourneyError && e.expired)) {
        setStep("reviewing");
      }
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [busy, execution, handleFailure, step, token]);

  // Enquanto valida, a etapa segue o resultado REAL da execucao — nunca o
  // texto do terminal. Exit 1 e "concluido com problemas nos dados", nao
  // falha da aplicacao; exit 2 e configuracao invalida.
  const { status: runStatus, result } = execution;
  useEffect(() => {
    if (step !== "validating" && !FINISHED.has(step)) return;
    if (runStatus === "timeout") {
      setStep("timed_out");
      return;
    }
    if (runStatus === "error") {
      setStep("technical_failure");
      return;
    }
    if (runStatus !== "done" || !result) return;
    if (result.exit_code === EXIT_OK) setStep("completed");
    else if (result.exit_code === EXIT_DATA_PROBLEMS) {
      setStep("completed_with_issues");
    } else if (result.exit_code === EXIT_USAGE) {
      setStep("invalid_configuration");
    } else setStep("technical_failure");
  }, [result, runStatus, step]);

  return {
    step,
    file,
    analysis,
    schema,
    error,
    rejection,
    token,
    execution,
    busy,
    chooseFile,
    analyzeFile,
    analyzeSample,
    choose,
    useSuggested,
    sendSchema,
    goToSchemaChoice,
    goToReview,
    validate,
    reset,
  };
}
