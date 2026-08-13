// Cliente da API real do Live System. Sem mocks: catalogo, saude e execucao
// vem do backend. Em dev, o proxy do Vite encaminha /api ao backend (sem CORS).
// Em producao, o FastAPI serve este front na mesma origem.

export type UploadKind = "csv" | "spreadsheet" | "folder" | "none";
export type OutputKind = "report" | "zip" | "file" | "html";

export interface Category {
  key: string;
  title: string;
  summary: string;
}

export interface Automation {
  id: string;
  category: string;
  title: string;
  subtitle: string;
  description: string;
  requires_browser: boolean;
  upload: UploadKind;
  upload_hint: string;
  output: OutputKind;
  // Automacoes sem upload rodam contra um servico de demonstracao interno.
  // Quando preenchidos, o front mostra o bloco "Origem da demonstracao".
  source_label: string;
  source_detail: string;
}

export interface Catalog {
  categories: Category[];
  automations: Automation[];
}

export interface DemoServer {
  name: string;
  port: number;
  alive: boolean;
}

export interface HealthLimits {
  max_concurrent_runs: number;
  max_stream_lines: number;
  max_stream_bytes: number;
  rate_limit_per_min: number;
  run_timeout_s: number;
  egress_lockdown: boolean;
}

export interface Health {
  status: string;
  app: string;
  version: string;
  browser_available: boolean;
  active_automations: string[];
  active_runs: number;
  limits: HealthLimits;
  demo_servers: DemoServer[];
}

// ---- Execucao real ----

export interface Artifact {
  name: string;
  bytes: number;
  sha256: string;
  download_url: string; // ja vem pronto do backend: /api/download/{token}/{name}
}

export interface RunStarted {
  token: string;
  stream_url: string;
  status: string;
}

export interface RunResult {
  token: string;
  outcome: string;
  exit_code: number;
  duration_ms: number;
  stdout: string;
  artifacts: Artifact[];
}

// ---- Auditoria de planilha ----

// Nome canonico do relatorio JSON gerado pela Auditoria (backend, --out-dir).
export const VALIDATION_REPORT_NAME = "validacao_report.json";

// Campos do validacao_report.json que o resumo visual consome.
// (O arquivo tem mais campos — issues, cleaning_changes — que ficam no download.)
export interface ValidationReport {
  mode: string;
  rows: number;
  total_valid: number;
  total_invalid: number;
  total_errors: number;
  total_warnings: number;
  total_cleaned: number;
  issues_by_category: Record<string, number>;
}

export function getValidationReport(url: string): Promise<ValidationReport> {
  return getJSON<ValidationReport>(url);
}

// ---- Cadastro automatico via planilha ----

// Nome canonico do relatorio JSON gerado pelo Cadastro (backend, --out-dir).
export const IMPORT_REPORT_NAME = "importacao_report.json";

// Campos do importacao_report.json que o resumo visual consome.
// (O arquivo traz tambem items[] e contexto, que ficam no download.)
export interface ImportReport {
  total: number;
  enviados: number;
  falhas: number;
  reenviaveis: number;
  falhas_por_categoria: Record<string, number>;
}

export function getImportReport(url: string): Promise<ImportReport> {
  return getJSON<ImportReport>(url);
}

// ---- Exportacao automatica de dados ----

// Nome canonico do relatorio JSON gerado pela Exportacao (backend, --out-dir).
export const EXTRACT_REPORT_NAME = "extracao_report.json";

// Campos do extracao_report.json que o resumo visual consome.
export interface ExtractReport {
  total_registros: number;
  paginas: number | null;
  colunas: string[];
  origem: string;
  duracao_ms: number;
}

export function getExtractReport(url: string): Promise<ExtractReport> {
  return getJSON<ExtractReport>(url);
}

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`${path} respondeu ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return getJSON<Health>("/api/health");
}

export function getCatalog(): Promise<Catalog> {
  return getJSON<Catalog>("/api/catalog");
}

// Traduz o status HTTP do POST /api/run em mensagem amigavel (pt-BR).
function runErrorMessage(status: number, detail: string | null): string {
  switch (status) {
    case 429:
      return "Servidor ocupado ou muitas requisições. Aguarde alguns segundos e tente de novo.";
    case 503:
      return "Limite de execuções simultâneas atingido. Tente novamente em instantes.";
    case 415:
      return detail ?? "Arquivo não suportado.";
    case 400:
      return detail ?? "Não foi possível iniciar a execução.";
    case 404:
    case 501:
      return "Automação indisponível.";
    default:
      return detail ?? `Falha ao iniciar a execução (HTTP ${status}).`;
  }
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
  } catch {
    /* corpo nao-json */
  }
  return null;
}

export async function runAutomation(
  id: string,
  opts: { files?: File[]; useSample?: boolean },
): Promise<RunStarted> {
  const useSample = opts.useSample ?? false;
  const files = opts.files ?? [];

  let url = `/api/run/${encodeURIComponent(id)}`;
  let body: FormData | undefined;

  if (useSample) {
    url += "?use_sample=true";
  } else if (files.length > 0) {
    const form = new FormData();
    for (const file of files) {
      form.append("files", file);
    }
    body = form;
  }

  const response = await fetch(url, { method: "POST", body });
  if (!response.ok) {
    throw new Error(
      runErrorMessage(response.status, await readDetail(response)),
    );
  }
  return (await response.json()) as RunStarted;
}

export function getResult(token: string): Promise<RunResult> {
  return getJSON<RunResult>(`/api/result/${encodeURIComponent(token)}`);
}
