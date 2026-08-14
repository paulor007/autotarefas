// Cliente tipado da jornada de planilhas (backend: /api/spreadsheets/*).
//
// Os quatro endpoints da jornada conduzem: analisar -> escolher aba/cabecalho
// -> confirmar schema -> validar. O acompanhamento (SSE, resultado, download)
// continua nos endpoints gerais do Live, com o MESMO token.
//
// Nada aqui interpreta stdout nem recebe caminho fisico: o backend devolve
// dados estruturados e URLs de download prontas.

/** Estados que o backend atribui a jornada. */
export type JourneyStatus =
  | "analyzing"
  | "needs_selection"
  | "analysis_ready"
  | "rejected_file"
  | "schema_ready"
  | "validating"
  | "completed"
  | "completed_with_issues"
  | "invalid_configuration"
  | "technical_failure"
  | "timed_out";

export interface SheetOption {
  name: string;
  score: number;
  rows: number;
  cols: number;
}

export interface Ambiguity {
  kind: "sheet" | "header";
  confidence: number;
  sheet_options: SheetOption[];
  header_options: number[];
}

/** Coluna como o profiling a observou (sem regra inventada). */
export interface AnalysisColumn {
  name: string;
  inferred_type: string | null;
  empty_count: number;
  distinct_count: number | null;
}

/**
 * Achado da analise e aviso do leitor.
 *
 * ATENCAO — foi aqui que a tela preta nasceu: `reader_warnings` NAO e uma
 * lista de textos, e um objeto `{code, message, column, row}`. O tipo
 * anterior dizia `string[]`, o componente renderizava o item direto, e o
 * React lancou "Objects are not valid as a React child", derrubando a
 * aplicacao inteira. O contrato agora reflete o payload de verdade.
 */
export interface AnalysisNote {
  code: string | null;
  severity: string | null;
  message: string;
  column: string | null;
  row: number | null;
}

export interface AnalysisReport {
  source_file: string;
  extension: string | null;
  selected_sheet: string | null;
  header_row: number | null;
  confidence: number | null;
  header_confidence: number | null;
  available_sheets: SheetOption[];
  row_count: number | null;
  column_count: number | null;
  columns: AnalysisColumn[];
  findings: AnalysisNote[];
  reader_warnings: AnalysisNote[];
}

/**
 * Resposta de analise JA NORMALIZADA.
 *
 * Nada aqui vem cru da rede: `parseAnalysis` transforma o JSON nao confiavel
 * neste modelo, garantindo que todo array exista e que todo campo renderizado
 * seja primitivo. Os componentes podem confiar nele.
 */
export interface AnalysisResponse {
  token: string;
  status: JourneyStatus;
  needs_choice: boolean;
  analysis: AnalysisReport | null;
  preview: string;
  ambiguities: Ambiguity[];
  selected_sheet: string | null;
  header_row: number | null;
  schema_suggestion_available: boolean;
  /**
   * Linhas COMPLETAMENTE identicas encontradas na leitura (ocorrencias
   * excedentes: a primeira de cada grupo e o original).
   *
   * Nao confundir com chave repetida — numa planilha de vendas o mesmo
   * codigo aparece uma vez por item, e isso e esperado.
   */
  duplicate_rows: number;
  /** Preenchido quando o arquivo foi recusado. */
  rejection: string | null;
}

/** A resposta da API nao cabe no contrato — defeito de integracao, nao do dado. */
export class ContractError extends Error {
  constructor(detalhe: string) {
    super(`resposta fora do contrato: ${detalhe}`);
    this.name = "ContractError";
  }
}

export interface SchemaColumnSummary {
  name: string;
  type: string | null;
  required: boolean;
  format: string | null;
  validator_br: string | null;
  unique: boolean;
}

export interface SchemaSummary {
  columns: SchemaColumnSummary[];
  detect_duplicate_rows: boolean;
  group_keys: { name: string; columns: string[] }[];
  group_checks: {
    name: string;
    group_key: string;
    consistent: string[];
    severity: string;
  }[];
  derived_checks: {
    name: string;
    target: string;
    expression: string;
    tolerance: string;
    severity: string;
  }[];
  /** So existe quando o schema foi REALMENTE gerado por um perfil. */
  generated_from?: {
    profile?: string;
    profile_version?: number;
    tool_version?: string;
  };
}

/** De onde veio o schema confirmado. */
export type SchemaOrigin = "suggested" | "profile" | "uploaded";

/** Campo conceitual de um perfil (o "conceito", nao a coluna da planilha). */
export interface ProfileField {
  name: string;
  required: boolean;
  doc: string;
}

/** Perfil do catalogo, como o backend o descreve. */
export interface ProfileInfo {
  id: string;
  title: string;
  version: number;
  summary: string;
  fields: ProfileField[];
}

/**
 * Procedencia do schema gerado por perfil, CONFIRMADA pelo backend.
 *
 * `mapping` e `omitted` sao o que o nucleo efetivamente aplicou — nao o que a
 * tela enviou. Exibir o estado local levaria de volta ao bug antigo: mostrar
 * uma associacao enquanto o schema usa outra.
 */
export interface AppliedProfile {
  id: string;
  version: number | null;
  mapping: Record<string, string>;
  omitted: string[];
}

export interface SchemaResponse {
  token: string;
  status: JourneyStatus;
  schema_origin: SchemaOrigin;
  summary: SchemaSummary;
  /** So existe quando a origem foi um perfil. */
  profile: AppliedProfile | null;
}

export interface ValidateStartResponse {
  token: string;
  status: JourneyStatus;
  stream_url: string;
  result_url: string;
}

/**
 * Erro estruturado da jornada.
 *
 * O backend devolve `code` (para a interface decidir) e `detail` (para a
 * pessoa ler). Guardamos os dois: reagir pelo texto da mensagem seria
 * frágil e quebraria a cada ajuste de redacao.
 */
export class JourneyError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "JourneyError";
    this.code = code;
    this.status = status;
  }

  /** A sessao acabou (TTL) — o caminho e recomecar, nao insistir. */
  get expired(): boolean {
    return this.code === "expired";
  }
}

// ==========================================================================
// Fronteira de confianca
//
//   JSON da API (nao confiavel)  ->  normalizacao  ->  modelo interno
//
// O TypeScript nao valida JSON em tempo de execucao: ele descreve o que
// ESPERAMOS receber. Quando a expectativa e a realidade divergem — foi o que
// aconteceu com `reader_windows` sendo objeto e nao texto — o erro so aparece
// no render, e derruba a aplicacao. Estas funcoes existem para que a
// divergencia apareca AQUI, como erro controlado, e nunca dentro de um
// componente.
//
// Sao poucas funcoes pequenas de proposito: nao vale trazer uma biblioteca de
// schema para um punhado de campos, e verificacao espalhada por componente
// (optional chaining em tudo) esconderia o problema em vez de resolve-lo.
// ==========================================================================

function isRecord(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function texto(valor: unknown, padrao = ""): string {
  return typeof valor === "string" ? valor : padrao;
}

function textoOuNulo(valor: unknown): string | null {
  return typeof valor === "string" && valor !== "" ? valor : null;
}

function numeroOuNulo(valor: unknown): number | null {
  return typeof valor === "number" && Number.isFinite(valor) ? valor : null;
}

function numero(valor: unknown, padrao = 0): number {
  return numeroOuNulo(valor) ?? padrao;
}

function lista(valor: unknown): unknown[] {
  return Array.isArray(valor) ? valor : [];
}

/**
 * Normaliza um aviso ou achado.
 *
 * Aceita as duas formas que o backend produz — objeto com `message` e, por
 * seguranca, texto puro — e devolve SEMPRE a mesma estrutura. Um item que nao
 * tenha mensagem alguma e descartado: melhor omitir do que mostrar vazio.
 */
function nota(valor: unknown): AnalysisNote | null {
  if (typeof valor === "string") {
    return {
      code: null,
      severity: null,
      message: valor,
      column: null,
      row: null,
    };
  }
  if (!isRecord(valor)) return null;
  const mensagem = texto(valor.message);
  if (!mensagem) return null;
  return {
    code: textoOuNulo(valor.code),
    severity: textoOuNulo(valor.severity),
    message: mensagem,
    column: textoOuNulo(valor.column),
    row: numeroOuNulo(valor.row),
  };
}

function notas(valor: unknown): AnalysisNote[] {
  return lista(valor)
    .map(nota)
    .filter((n): n is AnalysisNote => n !== null);
}

/** Identidade estrutural de uma nota — nao o texto solto. */
function chaveDaNota(n: AnalysisNote): string {
  return [n.code ?? "", n.message, n.column ?? "", n.row ?? ""].join("|");
}

/**
 * Junta os achados do profiling com os avisos do leitor, sem repetir.
 *
 * O backend descreve a MESMA ocorrencia nas duas colecoes: `findings` (com
 * severidade, do profiling) e `reader_warnings` (do leitor). Isso e correto
 * do lado dele — sao camadas diferentes —, mas exibir as duas mostrava o
 * mesmo aviso duas vezes na tela.
 *
 * A juncao e por IDENTIDADE ESTRUTURAL (codigo + mensagem + coluna + linha),
 * nunca por texto solto: duas ocorrencias reais em colunas diferentes tem a
 * mesma mensagem e PRECISAM aparecer as duas. Quando ha empate, fica a versao
 * do profiling, que e a unica que traz `severity` — nenhum metadado se perde.
 */
export function notasUnificadas(report: AnalysisReport): AnalysisNote[] {
  const porChave = new Map<string, AnalysisNote>();
  for (const n of [...report.findings, ...report.reader_warnings]) {
    const chave = chaveDaNota(n);
    const existente = porChave.get(chave);
    if (!existente) {
      porChave.set(chave, n);
      continue;
    }
    // Preserva a versao mais informativa (a que tem severidade).
    if (existente.severity === null && n.severity !== null) {
      porChave.set(chave, n);
    }
  }
  return [...porChave.values()];
}

function coluna(valor: unknown): AnalysisColumn | null {
  if (!isRecord(valor)) return null;
  const nome = texto(valor.name);
  if (!nome) return null;
  return {
    name: nome,
    inferred_type: textoOuNulo(valor.inferred_type),
    empty_count: numero(valor.empty_count),
    distinct_count: numeroOuNulo(valor.distinct_count),
  };
}

function abaOpcao(valor: unknown): SheetOption | null {
  if (!isRecord(valor)) return null;
  const nome = texto(valor.name);
  if (!nome) return null;
  return {
    name: nome,
    score: numero(valor.score),
    rows: numero(valor.rows),
    cols: numero(valor.cols),
  };
}

function relatorio(valor: unknown): AnalysisReport | null {
  if (!isRecord(valor)) return null;
  const metadata = isRecord(valor.metadata) ? valor.metadata : {};
  const leitura = isRecord(valor.leitura) ? valor.leitura : {};
  const estrutura = isRecord(valor.estrutura) ? valor.estrutura : {};

  const colunas = lista(valor.columns)
    .map(coluna)
    .filter((c): c is AnalysisColumn => c !== null);

  // Um relatorio sem coluna nenhuma nao descreve tabela alguma: tratamos como
  // ausente para que a maquina de estados nao anuncie "analise pronta".
  if (colunas.length === 0) return null;

  return {
    source_file: texto(metadata.source_file, "arquivo"),
    extension: textoOuNulo(metadata.extension),
    selected_sheet: textoOuNulo(leitura.selected_sheet),
    header_row: numeroOuNulo(leitura.header_row),
    confidence: numeroOuNulo(leitura.confidence),
    header_confidence: numeroOuNulo(leitura.header_confidence),
    available_sheets: lista(leitura.available_sheets)
      .map(abaOpcao)
      .filter((a): a is SheetOption => a !== null),
    row_count: numeroOuNulo(estrutura.row_count),
    column_count: numeroOuNulo(estrutura.column_count),
    columns: colunas,
    findings: notas(valor.findings),
    reader_warnings: notas(valor.reader_warnings),
  };
}

function ambiguidade(valor: unknown): Ambiguity | null {
  if (!isRecord(valor)) return null;
  const tipo = texto(valor.kind);
  if (tipo !== "sheet" && tipo !== "header") return null;

  const abas = lista(valor.sheet_options)
    .map(abaOpcao)
    .filter((a): a is SheetOption => a !== null);
  const linhas = lista(valor.header_options)
    .map((n) => numeroOuNulo(n))
    .filter((n): n is number => n !== null && n >= 1);

  // Uma ambiguidade sem opcao nao e uma pergunta que alguem consiga responder.
  if (tipo === "sheet" && abas.length === 0) return null;
  if (tipo === "header" && linhas.length === 0) return null;

  return {
    kind: tipo,
    confidence: numero(valor.confidence),
    sheet_options: abas,
    header_options: linhas,
  };
}

/**
 * Converte a resposta de analise no modelo interno, com invariantes.
 *
 * As invariantes sao o que impede a tela de anunciar algo que os dados nao
 * sustentam:
 *
 *   analysis_ready   -> exige relatorio valido
 *   needs_selection  -> exige ao menos uma ambiguidade respondivel
 *   rejected_file    -> exige mensagem de recusa
 *
 * HTTP 200 nao significa sucesso operacional: o desfecho vem do `status`.
 */
export function parseAnalysis(bruto: unknown): AnalysisResponse {
  if (!isRecord(bruto)) throw new ContractError("corpo nao e um objeto");

  const token = texto(bruto.token);
  if (!token) throw new ContractError("token ausente");

  const status = texto(bruto.status) as JourneyStatus;
  const ambiguidades = lista(bruto.ambiguities)
    .map(ambiguidade)
    .filter((a): a is Ambiguity => a !== null);
  const analise = relatorio(bruto.analysis);
  const recusa = textoOuNulo(bruto.detail);

  if (status === "rejected_file" && !recusa) {
    throw new ContractError("arquivo recusado sem explicacao");
  }
  if (status === "needs_selection" && ambiguidades.length === 0) {
    throw new ContractError("selecao pedida sem opcoes");
  }
  if (status === "analysis_ready" && analise === null) {
    throw new ContractError("analise concluida sem relatorio utilizavel");
  }

  return {
    token,
    status,
    // `needs_choice` do backend e confirmado pelo que sobrou da normalizacao:
    // se as opcoes nao vieram utilizaveis, nao ha escolha a oferecer.
    needs_choice: ambiguidades.length > 0,
    analysis: analise,
    preview: texto(bruto.preview),
    ambiguities: ambiguidades,
    selected_sheet: textoOuNulo(bruto.selected_sheet),
    header_row: numeroOuNulo(bruto.header_row),
    schema_suggestion_available: bruto.schema_suggestion_available === true,
    duplicate_rows: Math.max(0, numeroOuNulo(bruto.duplicate_rows) ?? 0),
    rejection: recusa,
  };
}

async function getJourney<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path);
  } catch {
    throw new JourneyError(
      "Não foi possível falar com o servidor. Verifique a conexão.",
      "network",
      0,
    );
  }
  if (!response.ok) {
    let detail = `Falha na requisição (HTTP ${response.status}).`;
    let code = "http_error";
    try {
      const data = (await response.json()) as {
        detail?: unknown;
        code?: unknown;
      };
      if (typeof data.detail === "string") detail = data.detail;
      if (typeof data.code === "string") code = data.code;
    } catch {
      /* corpo nao-json */
    }
    throw new JourneyError(detail, code, response.status);
  }
  return (await response.json()) as T;
}

async function postJourney<T>(path: string, body?: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { method: "POST", body });
  } catch {
    throw new JourneyError(
      "Não foi possível falar com o servidor. Verifique a conexão.",
      "network",
      0,
    );
  }
  if (!response.ok) {
    let detail = `Falha na requisição (HTTP ${response.status}).`;
    let code = "http_error";
    try {
      const data = (await response.json()) as {
        detail?: unknown;
        code?: unknown;
      };
      if (typeof data.detail === "string") detail = data.detail;
      if (typeof data.code === "string") code = data.code;
    } catch {
      /* corpo nao-json */
    }
    throw new JourneyError(detail, code, response.status);
  }
  return (await response.json()) as T;
}

/** Envia o arquivo (ou usa o exemplo do servidor) e devolve o diagnostico. */
export async function analyzeSpreadsheet(opts: {
  file?: File;
  useSample?: boolean;
}): Promise<AnalysisResponse> {
  if (opts.useSample) {
    return parseAnalysis(
      await postJourney<unknown>("/api/spreadsheets/analyze?use_sample=true"),
    );
  }
  const form = new FormData();
  if (opts.file) form.append("files", opts.file);
  return parseAnalysis(
    await postJourney<unknown>("/api/spreadsheets/analyze", form),
  );
}

/** Confirma aba e/ou linha de cabecalho; o backend reanalisa com a escolha. */
export async function selectReading(
  token: string,
  choice: { sheet?: string; headerRow?: number },
): Promise<AnalysisResponse> {
  const form = new FormData();
  if (choice.sheet !== undefined) form.append("sheet", choice.sheet);
  if (choice.headerRow !== undefined) {
    form.append("header_row", String(choice.headerRow));
  }
  return parseAnalysis(
    await postJourney<unknown>(
      `/api/spreadsheets/${encodeURIComponent(token)}/selection`,
      form,
    ),
  );
}

/**
 * Normaliza um perfil do catalogo.
 *
 * Mesma fronteira das demais respostas: o JSON e nao confiavel ate passar por
 * aqui. Um perfil sem `id` ou sem campos nao descreve nada e e descartado.
 */
function perfil(valor: unknown): ProfileInfo | null {
  if (!isRecord(valor)) return null;
  const id = texto(valor.id);
  if (!id) return null;
  const campos = lista(valor.fields)
    .map((f): ProfileField | null => {
      if (!isRecord(f)) return null;
      const nome = texto(f.name);
      if (!nome) return null;
      return { name: nome, required: f.required === true, doc: texto(f.doc) };
    })
    .filter((f): f is ProfileField => f !== null);
  if (campos.length === 0) return null;
  return {
    id,
    title: texto(valor.title, id),
    version: numero(valor.version, 1),
    summary: texto(valor.summary),
    fields: campos,
  };
}

/** Normaliza o bloco de procedencia devolvido apos gerar o schema. */
function perfilAplicado(valor: unknown): AppliedProfile | null {
  if (!isRecord(valor)) return null;
  const id = texto(valor.id);
  if (!id) return null;
  const mapa: Record<string, string> = {};
  if (isRecord(valor.mapping)) {
    for (const [campo, coluna] of Object.entries(valor.mapping)) {
      if (typeof coluna === "string" && coluna) mapa[campo] = coluna;
    }
  }
  return {
    id,
    version: numeroOuNulo(valor.version),
    mapping: mapa,
    omitted: lista(valor.omitted)
      .map((o) => texto(o))
      .filter((o) => o !== ""),
  };
}

/** Converte a resposta de schema no modelo interno. */
export function parseSchemaResponse(bruto: unknown): SchemaResponse {
  if (!isRecord(bruto)) throw new ContractError("corpo nao e um objeto");
  const origem = texto(bruto.schema_origin);
  if (origem !== "suggested" && origem !== "profile" && origem !== "uploaded") {
    throw new ContractError(
      `origem de schema desconhecida: ${origem || "(vazia)"}`,
    );
  }
  if (!isRecord(bruto.summary))
    throw new ContractError("resumo do schema ausente");
  const aplicado = perfilAplicado(bruto.profile);
  // Invariante: schema vindo de perfil precisa dizer QUAL perfil o gerou.
  if (origem === "profile" && aplicado === null) {
    throw new ContractError("schema de perfil sem procedencia");
  }
  return {
    token: texto(bruto.token),
    status: texto(bruto.status) as JourneyStatus,
    schema_origin: origem,
    summary: bruto.summary as unknown as SchemaSummary,
    profile: aplicado,
  };
}

/** Perfis disponiveis no pacote instalado (catalogo publico, so leitura). */
export async function listProfiles(): Promise<ProfileInfo[]> {
  const corpo = await getJourney<unknown>("/api/spreadsheets/profiles");
  if (!isRecord(corpo)) throw new ContractError("catalogo invalido");
  return lista(corpo.profiles)
    .map(perfil)
    .filter((p): p is ProfileInfo => p !== null);
}

/** Metadados de um perfil especifico. */
export async function getProfile(profileId: string): Promise<ProfileInfo> {
  const corpo = await getJourney<unknown>(
    `/api/spreadsheets/profiles/${encodeURIComponent(profileId)}`,
  );
  const dados = perfil(corpo);
  if (dados === null) throw new ContractError("perfil invalido");
  return dados;
}

/**
 * Gera o schema a partir de um perfil e do mapeamento escolhido.
 *
 * O mapeamento vai como JSON num campo de formulario, no formato que o
 * endpoint ja existente espera. Quem valida campo, coluna e obrigatoriedade e
 * o nucleo — a tela nao repete essas regras.
 */
export async function confirmProfileSchema(
  token: string,
  profileId: string,
  mapping: Record<string, string>,
): Promise<SchemaResponse> {
  const form = new FormData();
  form.append("source", "profile");
  form.append("profile_id", profileId);
  form.append("mapping", JSON.stringify(mapping));
  return parseSchemaResponse(
    await postJourney<unknown>(
      `/api/spreadsheets/${encodeURIComponent(token)}/schema`,
      form,
    ),
  );
}

/** Confirma o schema sugerido pela analise. */
export async function confirmSuggestedSchema(
  token: string,
): Promise<SchemaResponse> {
  const form = new FormData();
  form.append("source", "suggested");
  return parseSchemaResponse(
    await postJourney<unknown>(
      `/api/spreadsheets/${encodeURIComponent(token)}/schema`,
      form,
    ),
  );
}

/** Envia um YAML proprio como schema da validacao. */
export async function uploadSchema(
  token: string,
  file: File,
): Promise<SchemaResponse> {
  const form = new FormData();
  form.append("source", "uploaded");
  form.append("files", file);
  return parseSchemaResponse(
    await postJourney<unknown>(
      `/api/spreadsheets/${encodeURIComponent(token)}/schema`,
      form,
    ),
  );
}

/**
 * Dispara a validacao com as escolhas confirmadas.
 *
 * `applyCleaning` e a confirmacao das correcoes seguras: sem ela o AutoTarefas
 * apenas aponta os problemas; com ela, normaliza o que e seguro normalizar e
 * (em XLSX) devolve a planilha tratada preservando a apresentacao original.
 */
export function startValidation(
  token: string,
  opts: {
    strictWarnings?: boolean;
    maxIssues?: number;
    applyCleaning?: boolean;
    flagDuplicateRows?: boolean;
  } = {},
): Promise<ValidateStartResponse> {
  const form = new FormData();
  if (opts.strictWarnings) form.append("strict_warnings", "true");
  if (opts.maxIssues !== undefined) {
    form.append("max_issues", String(opts.maxIssues));
  }
  if (opts.applyCleaning) form.append("apply_cleaning", "true");
  if (opts.flagDuplicateRows) form.append("flag_duplicate_rows", "true");
  return postJourney<ValidateStartResponse>(
    `/api/spreadsheets/${encodeURIComponent(token)}/validate`,
    form,
  );
}

/** URL de download de um artefato desta execucao (servida pelo backend). */
export function artifactUrl(token: string, name: string): string {
  return `/api/download/${encodeURIComponent(token)}/${encodeURIComponent(name)}`;
}

/** Nome do schema sugerido dentro do workspace (baixavel). */
export const SUGGESTED_SCHEMA_NAME = "schema_sugerido.yaml";

/** Nome do pacote de evidencias (baixavel). */
export const EVIDENCE_PACKAGE_NAME = "pacote_execucao.zip";
