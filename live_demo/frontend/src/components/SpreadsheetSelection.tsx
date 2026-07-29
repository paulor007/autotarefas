import { useState } from "react";

import type { Ambiguity } from "../lib/spreadsheets";

interface Props {
  ambiguities: Ambiguity[];
  busy: boolean;
  onChoose: (choice: { sheet?: string; headerRow?: number }) => void;
}

/**
 * Escolha de aba / linha de cabecalho, quando o leitor nao teve certeza.
 *
 * As opcoes vem SEMPRE do backend: a interface nao inventa candidatas nem
 * adivinha. Sem escolha nao ha como seguir — e isso e proposital: seguir com
 * um palpite daria um resultado que parece legitimo sobre a tabela errada.
 */
export default function SpreadsheetSelection({
  ambiguities,
  busy,
  onChoose,
}: Props) {
  const aba = ambiguities.find((a) => a.kind === "sheet");
  const cabecalho = ambiguities.find((a) => a.kind === "header");

  const [abaEscolhida, setAbaEscolhida] = useState<string>("");
  const [linhaEscolhida, setLinhaEscolhida] = useState<number | "">("");

  const podeEnviar = aba ? abaEscolhida !== "" : linhaEscolhida !== "";

  const enviar = () => {
    if (!podeEnviar || busy) return;
    if (aba) onChoose({ sheet: abaEscolhida });
    else if (linhaEscolhida !== "") onChoose({ headerRow: linhaEscolhida });
  };

  return (
    <div className="space-y-4" aria-live="polite">
      <div className="rounded-lg border border-warn/40 bg-warn/5 px-4 py-3 text-sm text-warn">
        Não foi possível identificar com segurança onde começa a tabela.
        {aba
          ? " Escolha a aba que contém os dados."
          : " Escolha a linha que contém os nomes das colunas."}
      </div>

      {aba ? (
        <fieldset className="space-y-2">
          <legend className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Abas encontradas
          </legend>
          {aba.sheet_options.map((opcao) => (
            <label
              key={opcao.name}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-white/6 bg-ink px-4 py-3 text-sm hover:border-white/20 has-checked:border-signal"
            >
              <input
                type="radio"
                name="aba"
                value={opcao.name}
                checked={abaEscolhida === opcao.name}
                onChange={() => setAbaEscolhida(opcao.name)}
                disabled={busy}
                className="h-4 w-4"
              />
              <span className="min-w-0 flex-1">
                <span className="font-semibold text-fg">{opcao.name}</span>
                <span className="ml-2 text-muted">
                  {opcao.rows} linha(s) · {opcao.cols} coluna(s) ·{" "}
                  {Math.round(opcao.score * 100)}% de confiança
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      ) : null}

      {!aba && cabecalho ? (
        <fieldset className="space-y-2">
          <legend className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Linhas candidatas a cabeçalho
          </legend>
          {cabecalho.header_options.map((linha) => (
            <label
              key={linha}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-white/6 bg-ink px-4 py-3 text-sm hover:border-white/20 has-checked:border-signal"
            >
              <input
                type="radio"
                name="cabecalho"
                value={linha}
                checked={linhaEscolhida === linha}
                onChange={() => setLinhaEscolhida(linha)}
                disabled={busy}
                className="h-4 w-4"
              />
              {/* Numeracao FISICA, igual a do Excel: nada de indice zero. */}
              <span className="font-semibold text-fg">Linha {linha}</span>
            </label>
          ))}
        </fieldset>
      ) : null}

      <button
        type="button"
        onClick={enviar}
        disabled={!podeEnviar || busy}
        className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Analisando…" : "Confirmar e analisar de novo"}
      </button>
    </div>
  );
}
