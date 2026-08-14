import { useCallback, useEffect, useRef, useState } from "react";

import {
  analyzeSpreadsheet,
  confirmProfileSchema,
  confirmSuggestedSchema,
  ContractError,
  getProfile,
  JourneyError,
  listProfiles,
  selectReading,
  startValidation,
  uploadSchema,
  type AnalysisResponse,
  type ProfileInfo,
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
  | "choosing_profile"
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
  /** Perfis do catalogo. Carregados sob demanda, ao abrir a opcao. */
  profiles: ProfileInfo[];
  /** Perfil em foco na tela de mapeamento. */
  profile: ProfileInfo | null;
  /** Campo conceitual -> coluna real, ainda NAO confirmado pelo backend. */
  mapping: Record<string, string>;
  /** Colunas da analise ATUAL — as unicas que o mapeamento pode usar. */
  columns: string[];
  error: string | null;
  /** Mensagem do backend quando o arquivo foi recusado. */
  rejection: string | null;
  token: string | null;
  execution: UseExecution;
  busy: boolean;
  /**
   * Correcoes seguras CONFIRMADAS pela pessoa (espacos, caixa, formato).
   *
   * Comeca desligado de proposito: sem confirmacao, o AutoTarefas so aponta
   * o que encontrou. Ligado, ele normaliza o que e seguro normalizar e
   * mostra o antes/depois de cada valor alterado.
   */
  applyCleaning: boolean;
  setApplyCleaning: (value: boolean) => void;
  /**
   * Sinalizar linhas 100% repetidas para revisao.
   *
   * Vem LIGADO quando a analise encontrou repetidas — nao para decidir por
   * ninguem, mas porque esconder o achado seria pior: as linhas continuam na
   * planilha, e nenhuma e removida em hipotese alguma.
   */
  flagDuplicateRows: boolean;
  setFlagDuplicateRows: (value: boolean) => void;

  chooseFile: (file: File | null) => void;
  analyzeFile: () => Promise<void>;
  analyzeSample: () => Promise<void>;
  choose: (choice: { sheet?: string; headerRow?: number }) => Promise<void>;
  useSuggested: () => Promise<void>;
  sendSchema: (file: File) => Promise<void>;
  goToSchemaChoice: () => void;
  goToProfileChoice: () => Promise<void>;
  pickProfile: (profileId: string) => Promise<void>;
  setMappingField: (field: string, column: string) => void;
  submitProfileMapping: () => Promise<void>;
  goToReview: () => void;
  validate: () => Promise<void>;
  reset: () => void;
}

export function useSpreadsheetJourney(): UseSpreadsheetJourney {
  const [step, setStep] = useState<JourneyStep>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
  const [profile, setProfile] = useState<ProfileInfo | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [rejection, setRejection] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [applyCleaning, setApplyCleaning] = useState(false);
  const [flagDuplicateRows, setFlagDuplicateRows] = useState(false);

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

  /**
   * Descarta o que foi escolhido sobre a leitura anterior.
   *
   * Um mapeamento aponta para COLUNAS de uma analise especifica. Se o arquivo,
   * a aba ou o cabecalho mudam, aquelas colunas podem nem existir mais — deixar
   * o mapeamento de pe faria a tela mostrar uma associacao que o backend
   * recusaria (ou pior, aceitaria contra outra tabela).
   */
  const limparEscolhas = useCallback(() => {
    setSchema(null);
    setProfile(null);
    setMapping({});
  }, []);

  const reset = useCallback(() => {
    execution.reset();
    setStep("idle");
    setFile(null);
    setAnalysis(null);
    setProfiles([]);
    limparEscolhas();
    setError(null);
    setRejection(null);
    setToken(null);
    setBusy(false);
    setApplyCleaning(false);
    setFlagDuplicateRows(false);
  }, [execution, limparEscolhas]);

  /**
   * Traduz uma falha de chamada em estado de tela.
   *
   * Devolve `true` quando JA definiu a etapa (o caso da sessao expirada, que
   * tem tela propria). Sem esse retorno, o chamador voltava a etapa anterior
   * na linha seguinte e apagava o estado `expired` — a pessoa nunca via a
   * opcao de recomecar.
   */
  const handleFailure = useCallback((e: unknown): boolean => {
    if (!mounted.current) return true;
    if (e instanceof ContractError) {
      // Divergencia entre o que a API devolveu e o contrato. O detalhe tecnico
      // vai para o console; a tela recebe algo acionavel.
      console.error("[AutoTarefas] resposta fora do contrato", e);
      setError(
        "A resposta do serviço não pôde ser interpretada. Reinicie a análise; se repetir, o serviço pode estar em uma versão diferente da interface.",
      );
      return false;
    }
    if (e instanceof JourneyError) {
      if (e.expired) {
        // Sessao expirada: o token nao vale mais e insistir so gera erro.
        setStep("expired");
        setError(e.message);
        return true;
      }
      setError(e.message);
      return false;
    }
    setError("Não foi possível concluir a operação.");
    return false;
  }, []);

  /** Aplica uma resposta de analise, derivando a etapa do que o backend disse. */
  const applyAnalysis = useCallback((data: AnalysisResponse) => {
    if (!mounted.current) return;
    setToken(data.token);
    setAnalysis(data);
    // A leitura mudou: o backend ja invalidou o schema confirmado, e a tela
    // nao pode continuar mostrando o resumo antigo — nem o mapeamento, que
    // aponta para colunas que talvez nao existam mais.
    limparEscolhas();
    // Achou linha repetida? A sinalizacao ja vem marcada — a pessoa pode
    // desmarcar, mas nao vai descobrir a repeticao por acaso depois.
    setFlagDuplicateRows(data.duplicate_rows > 0);

    if (data.status === "rejected_file") {
      setRejection(data.rejection ?? "Não foi possível ler este arquivo.");
      setStep("rejected_file");
      return;
    }
    setRejection(null);
    if (data.needs_choice) {
      setStep("needs_selection");
      return;
    }
    // Invariante: nao anunciamos "analise pronta" sem relatorio para mostrar.
    // HTTP 200 nao e sinonimo de sucesso operacional.
    if (data.analysis === null) {
      setError(
        "A análise respondeu, mas sem um diagnóstico utilizável deste arquivo.",
      );
      setStep("rejected_file");
      setRejection(
        "Não foi possível descrever a estrutura deste arquivo. Verifique se ele tem uma tabela com cabeçalho.",
      );
      return;
    }
    setStep("analysis_ready");
  }, []);

  const runAnalysis = useCallback(
    async (opts: { file?: File; useSample?: boolean }) => {
      setBusy(true);
      setError(null);
      setStep("analyzing");
      try {
        applyAnalysis(await analyzeSpreadsheet(opts));
      } catch (e: unknown) {
        const assumido = handleFailure(e);
        if (mounted.current && !assumido) {
          setStep(file ? "file_selected" : "idle");
        }
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
        const assumido = handleFailure(e);
        if (mounted.current && !assumido) setStep("needs_selection");
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
      const assumido = handleFailure(e);
      if (mounted.current && !assumido) setStep("choosing_schema");
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
        const assumido = handleFailure(e);
        // O backend preserva o ultimo schema valido: se havia um, a jornada
        // continua podendo seguir com ele; senao, volta para a escolha.
        if (mounted.current && !assumido) {
          setStep(schema ? "schema_invalid" : "choosing_schema");
        }
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [applySchema, handleFailure, schema, token],
  );

  /** Colunas da analise ATUAL — a unica origem valida do seletor. */
  const columns = analysis?.analysis?.columns.map((c) => c.name) ?? [];

  const goToProfileChoice = useCallback(async () => {
    setError(null);
    setStep("choosing_profile");
    if (profiles.length > 0) return; // catalogo ja carregado nesta jornada
    setBusy(true);
    try {
      const lista = await listProfiles();
      if (mounted.current) setProfiles(lista);
    } catch (e: unknown) {
      handleFailure(e);
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [handleFailure, profiles.length]);

  const pickProfile = useCallback(
    async (profileId: string) => {
      setError(null);
      setBusy(true);
      // Trocar de perfil zera o mapeamento: os campos conceituais sao outros.
      setMapping({});
      try {
        const dados = await getProfile(profileId);
        if (mounted.current) setProfile(dados);
      } catch (e: unknown) {
        handleFailure(e);
      } finally {
        if (mounted.current) setBusy(false);
      }
    },
    [handleFailure],
  );

  const setMappingField = useCallback((field: string, column: string) => {
    setMapping((atual) => {
      const proximo = { ...atual };
      // Coluna vazia = "Nao usar": o campo sai do mapa em vez de ir vazio.
      if (column) proximo[field] = column;
      else delete proximo[field];
      return proximo;
    });
  }, []);

  const submitProfileMapping = useCallback(async () => {
    if (!token || !profile || busy) return;
    setBusy(true);
    setError(null);
    try {
      const resposta = await confirmProfileSchema(token, profile.id, mapping);
      if (mounted.current) {
        setSchema(resposta);
        setStep("schema_ready");
      }
    } catch (e: unknown) {
      const assumido = handleFailure(e);
      // Permanece na tela de mapeamento para a pessoa corrigir sem recomecar.
      if (mounted.current && !assumido) setStep("choosing_profile");
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [busy, handleFailure, mapping, profile, token]);

  const validate = useCallback(async () => {
    if (!token || busy || step === "validating") return;
    setBusy(true);
    setError(null);
    setStep("validating");
    try {
      const started = await startValidation(token, {
        applyCleaning,
        flagDuplicateRows,
      });
      execution.attach(started.token, started.stream_url);
    } catch (e: unknown) {
      const assumido = handleFailure(e);
      if (mounted.current && !assumido) setStep("reviewing");
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, [
    applyCleaning,
    busy,
    execution,
    flagDuplicateRows,
    handleFailure,
    step,
    token,
  ]);

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
    profiles,
    profile,
    mapping,
    columns,
    error,
    applyCleaning,
    setApplyCleaning,
    flagDuplicateRows,
    setFlagDuplicateRows,
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
    goToProfileChoice,
    pickProfile,
    setMappingField,
    submitProfileMapping,
    goToReview,
    validate,
    reset,
  };
}
