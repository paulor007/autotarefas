import type { SchemaSummary } from "../lib/spreadsheets";

interface Props {
  summary: SchemaSummary;
  origin: "suggested" | "uploaded";
}

function Regra({ children }: { children: React.ReactNode }) {
  return (
    <li className="rounded-lg border border-white/6 bg-ink px-3 py-2 text-[0.85rem]">
      {children}
    </li>
  );
}

/**
 * Resumo das regras que serao aplicadas — a revisao antes de executar.
 *
 * `generated_from` so aparece quando EXISTE de verdade: um schema escrito a
 * mao nao ganha bloco de procedencia vazio nem inventado.
 */
export default function SpreadsheetSchemaSummary({ summary, origin }: Props) {
  const temRegras =
    summary.group_keys.length > 0 ||
    summary.group_checks.length > 0 ||
    summary.derived_checks.length > 0 ||
    summary.detect_duplicate_rows;

  return (
    <div className="space-y-4">
      <p className="text-[0.85rem] text-muted">
        Origem do schema:{" "}
        <span className="font-semibold text-fg">
          {origin === "suggested"
            ? "sugerido pela análise"
            : "enviado por você"}
        </span>
      </p>

      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
          Colunas verificadas ({summary.columns.length})
        </h4>
        <div className="max-h-64 overflow-auto rounded-lg border border-white/6">
          <table className="w-full text-left text-[0.8rem]">
            <thead className="bg-ink text-[0.68rem] uppercase tracking-wider text-muted">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Coluna
                </th>
                <th scope="col" className="px-3 py-2">
                  Tipo
                </th>
                <th scope="col" className="px-3 py-2">
                  Regras
                </th>
              </tr>
            </thead>
            <tbody>
              {summary.columns.map((coluna) => (
                <tr key={coluna.name} className="border-t border-white/6">
                  <td className="px-3 py-2 font-semibold text-fg">
                    {coluna.name}
                  </td>
                  <td className="px-3 py-2 text-muted">{coluna.type ?? "—"}</td>
                  <td className="px-3 py-2 text-muted">
                    {[
                      coluna.required ? "obrigatória" : null,
                      coluna.unique ? "sem repetição" : null,
                      coluna.format,
                      coluna.validator_br,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {temRegras ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            Regras entre linhas e colunas
          </h4>
          <ul className="space-y-1.5">
            {summary.detect_duplicate_rows ? (
              <Regra>Linhas totalmente repetidas são sinalizadas.</Regra>
            ) : null}
            {summary.group_keys.map((chave) => (
              <Regra key={chave.name}>
                <span className="font-semibold text-fg">{chave.name}</span>: um
                grupo é formado por {chave.columns.join(" + ")}.
              </Regra>
            ))}
            {summary.group_checks.map((check) => (
              <Regra key={check.name}>
                <span className="font-semibold text-fg">{check.name}</span>:{" "}
                {check.consistent.join(", ")} devem concordar dentro do grupo{" "}
                <span className="text-muted">({check.severity})</span>.
              </Regra>
            ))}
            {summary.derived_checks.map((check) => (
              <Regra key={check.name}>
                <span className="font-semibold text-fg">{check.name}</span>:{" "}
                {check.target} deve corresponder a{" "}
                <code className="text-fg">{check.expression}</code>{" "}
                <span className="text-muted">({check.severity})</span>.
              </Regra>
            ))}
          </ul>
        </div>
      ) : null}

      {summary.generated_from ? (
        <p className="text-[0.8rem] text-muted">
          Gerado a partir do perfil{" "}
          <span className="font-semibold text-fg">
            {summary.generated_from.profile}
          </span>
          {summary.generated_from.profile_version
            ? ` (versão ${summary.generated_from.profile_version})`
            : ""}
          .
        </p>
      ) : null}
    </div>
  );
}
