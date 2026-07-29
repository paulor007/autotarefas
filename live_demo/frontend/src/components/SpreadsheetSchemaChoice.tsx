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
  onUseSuggested: () => void;
  onUpload: (file: File) => void;
}

const SCHEMA_ACCEPT = ".yaml,.yml";

/**
 * Escolha de como validar: schema sugerido ou YAML proprio.
 *
 * O texto sobre o schema sugerido e obrigatorio e literal: ele descreve o que
 * foi OBSERVADO no arquivo e nao conhece as regras do negocio de ninguem.
 * Prometer mais que isso seria o tipo de exagero que o produto evita.
 */
export default function SpreadsheetSchemaChoice({
  token,
  busy,
  error,
  summary,
  onUseSuggested,
  onUpload,
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
          Usar o schema sugerido
        </h4>
        <p className="mt-2 text-[0.85rem] leading-relaxed text-muted">
          O schema sugerido descreve a estrutura observada no arquivo. Ele não
          conhece automaticamente todas as regras específicas do seu negócio.
        </p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onUseSuggested}
            disabled={busy}
            className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Confirmando…" : "Confirmar schema sugerido"}
          </button>
          <a
            href={artifactUrl(token, SUGGESTED_SCHEMA_NAME)}
            download
            className="rounded-lg border border-white/12 px-5 py-2.5 text-center text-sm font-semibold text-fg hover:border-white/25"
          >
            Baixar schema sugerido
          </a>
        </div>
      </section>

      <section className="rounded-2xl border border-white/6 bg-ink p-5">
        <h4 className="text-sm font-semibold text-fg">
          Enviar meu schema YAML
        </h4>
        <p className="mt-2 text-[0.85rem] leading-relaxed text-muted">
          Se você já tem um schema com as regras do seu processo — validações,
          chaves de grupo, contas entre colunas — envie o arquivo{" "}
          <code className="text-fg">.yaml</code> ou{" "}
          <code className="text-fg">.yml</code>.
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

        <button
          type="button"
          onClick={enviar}
          disabled={!schemaFile || busy}
          className="mt-4 rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Enviando…" : "Enviar schema"}
        </button>
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
