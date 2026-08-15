import { useRef, useState } from "react";

import {
  artifactUrl,
  SUGGESTED_SCHEMA_NAME,
  type SchemaSummary,
} from "../lib/spreadsheets";

interface Props {
  token: string;
  busy: boolean;
  error: string | null;
  /** Resumo do ultimo schema VALIDO, quando ja houver um. */
  summary: SchemaSummary | null;
  onUpload: (file: File) => void;
  onBack: () => void;
}

const SCHEMA_ACCEPT = ".yaml,.yml";

/**
 * Opção avançada: enviar as regras do próprio processo em YAML.
 *
 * Deixou de ser etapa obrigatória da jornada. A análise geral acontece sempre,
 * sem schema; quem tem regras próprias (validações, chaves de grupo, contas
 * entre colunas) chega aqui por escolha, não por exigência.
 */
export default function SpreadsheetSchemaChoice({
  token,
  busy,
  error,
  summary,
  onUpload,
  onBack,
}: Props) {
  const [schemaFile, setSchemaFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const enviar = () => {
    if (schemaFile && !busy) onUpload(schemaFile);
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-white/6 bg-ink p-5">
        <h4 className="text-sm font-semibold text-fg">
          Enviar meu schema YAML
        </h4>
        <p className="mt-2 text-[0.85rem] leading-relaxed text-muted">
          Etapa opcional. Se você já tem um schema com as regras do seu processo
          — validações, chaves de grupo, contas entre colunas — envie o arquivo{" "}
          <code className="text-fg">.yaml</code> ou{" "}
          <code className="text-fg">.yml</code>. Sem ele, a análise geral e a
          verificação de linhas repetidas acontecem do mesmo jeito.
        </p>

        <label
          htmlFor="schema-upload"
          className="mt-4 block text-xs font-semibold uppercase tracking-wider text-muted"
        >
          Arquivo do schema
        </label>
        <input
          id="schema-upload"
          ref={inputRef}
          type="file"
          accept={SCHEMA_ACCEPT}
          disabled={busy}
          onChange={(e) => setSchemaFile(e.target.files?.[0] ?? null)}
          className="mt-2 block w-full text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-white/8 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-fg"
        />

        {schemaFile ? (
          <p className="mt-2 text-[0.8rem] text-muted">
            {schemaFile.name} ·{" "}
            {Math.max(1, Math.round(schemaFile.size / 1024))} KB
          </p>
        ) : null}

        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={enviar}
            disabled={!schemaFile || busy}
            className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Enviando…" : "Enviar schema"}
          </button>
          <button
            type="button"
            onClick={onBack}
            disabled={busy}
            className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
          >
            Voltar sem enviar
          </button>
        </div>

        <p className="mt-4 text-[0.8rem] leading-relaxed text-muted">
          Para começar do que foi observado no arquivo, você pode{" "}
          <a
            href={artifactUrl(token, SUGGESTED_SCHEMA_NAME)}
            download
            className="font-semibold text-signal underline-offset-2 hover:underline"
          >
            baixar o schema sugerido
          </a>{" "}
          e editar. Ele descreve a estrutura observada e não conhece as regras
          específicas do seu negócio.
        </p>
      </section>

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {error}
          {summary ? (
            <p className="mt-1.5 text-[0.85rem] text-muted">
              O último schema válido continua disponível — corrija o arquivo e
              envie de novo, ou siga com o que já estava confirmado.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
