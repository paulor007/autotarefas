import type { ProfileInfo } from "../lib/spreadsheets";

interface Props {
  profiles: ProfileInfo[];
  profile: ProfileInfo | null;
  /** Colunas da análise ATUAL — as únicas que podem ser escolhidas. */
  columns: string[];
  mapping: Record<string, string>;
  busy: boolean;
  error: string | null;
  onPick: (profileId: string) => void;
  onChange: (field: string, column: string) => void;
  onSubmit: () => void;
  onBack: () => void;
}

/**
 * Escolha de perfil e mapeamento dos campos conceituais.
 *
 * O que a pessoa está fazendo aqui, em uma frase: dizendo ao AutoTarefas qual
 * coluna da planilha dela representa cada conceito que o perfil conhece.
 *
 * Nada é adivinhado — sem correspondência por posição, por nome parecido ou
 * por qualquer heurística. Se um campo não for mapeado, ele simplesmente não
 * entra no schema (quando opcional) ou impede o envio (quando obrigatório).
 *
 * A validação final é SEMPRE do backend: aqui só evitamos o envio quando já
 * dá para ver que falta algo, para a pessoa não gastar uma ida ao servidor.
 */
export default function SpreadsheetProfileMapping({
  profiles,
  profile,
  columns,
  mapping,
  busy,
  error,
  onPick,
  onChange,
  onSubmit,
  onBack,
}: Props) {
  const obrigatoriosPendentes = profile
    ? profile.fields.filter((f) => f.required && !mapping[f.name])
    : [];

  // Duas regras na mesma coluna: o backend recusa, e avisamos antes.
  const usadas = Object.values(mapping);
  const repetidas = usadas.filter((c, i) => usadas.indexOf(c) !== i);

  const podeEnviar =
    profile !== null &&
    obrigatoriosPendentes.length === 0 &&
    repetidas.length === 0 &&
    !busy;

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-white/6 bg-ink p-5">
        <h4 className="text-sm font-semibold text-fg">Escolha o perfil</h4>
        <p className="mt-2 text-[0.85rem] leading-relaxed text-muted">
          Um perfil é um conjunto de regras já conhecidas para um tipo de dado.
          O AutoTarefas <strong>não descobre sozinho</strong> qual perfil serve
          para a sua planilha — escolha um que corresponda ao conteúdo dela.
        </p>

        {profiles.length === 0 && !busy ? (
          <p className="mt-4 text-[0.85rem] text-muted">
            Nenhum perfil disponível nesta instalação.
          </p>
        ) : null}

        <ul className="mt-4 space-y-2">
          {profiles.map((item) => (
            <li key={item.id}>
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-white/6 bg-surface px-4 py-3 text-sm hover:border-white/20">
                <input
                  type="radio"
                  name="perfil"
                  value={item.id}
                  checked={profile?.id === item.id}
                  onChange={() => onPick(item.id)}
                  disabled={busy}
                  className="mt-1 h-4 w-4"
                />
                <span className="min-w-0">
                  <span className="font-semibold text-fg">{item.title}</span>
                  <span className="ml-2 text-[0.75rem] text-muted">
                    versão {item.version}
                  </span>
                  {item.summary ? (
                    <span className="mt-1 block text-[0.8rem] text-muted">
                      {item.summary}
                    </span>
                  ) : null}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      {profile ? (
        <section className="rounded-2xl border border-white/6 bg-ink p-5">
          <h4 className="text-sm font-semibold text-fg">
            Relacione os campos às suas colunas
          </h4>
          <p className="mt-2 text-[0.85rem] leading-relaxed text-muted">
            Para cada conceito do perfil, escolha a coluna correspondente na sua
            planilha. Campos opcionais podem ficar como “Não usar”.
          </p>

          <div className="mt-4 space-y-3">
            {profile.fields.map((campo) => {
              const inputId = `mapeamento-${campo.name}`;
              const pendente = campo.required && !mapping[campo.name];
              return (
                <div
                  key={campo.name}
                  className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-center"
                >
                  <label htmlFor={inputId} className="text-sm">
                    <span className="font-semibold text-fg">{campo.name}</span>
                    {campo.required ? (
                      <span className="ml-2 text-[0.7rem] uppercase tracking-wider text-warn">
                        obrigatório
                      </span>
                    ) : (
                      <span className="ml-2 text-[0.7rem] uppercase tracking-wider text-muted">
                        opcional
                      </span>
                    )}
                    {campo.doc ? (
                      <span className="mt-0.5 block text-[0.78rem] text-muted">
                        {campo.doc}
                      </span>
                    ) : null}
                  </label>
                  <select
                    id={inputId}
                    value={mapping[campo.name] ?? ""}
                    onChange={(e) => onChange(campo.name, e.target.value)}
                    disabled={busy}
                    aria-invalid={pendente || undefined}
                    className={`w-full rounded-lg border bg-surface px-3 py-2 text-sm text-fg ${
                      pendente ? "border-warn" : "border-white/12"
                    }`}
                  >
                    <option value="">
                      {campo.required ? "— selecione —" : "Não usar"}
                    </option>
                    {columns.map((coluna) => (
                      <option key={coluna} value={coluna}>
                        {coluna}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>

          {obrigatoriosPendentes.length > 0 ? (
            <p className="mt-4 text-[0.85rem] text-warn">
              Falta relacionar:{" "}
              {obrigatoriosPendentes.map((f) => f.name).join(", ")}.
            </p>
          ) : null}

          {repetidas.length > 0 ? (
            <p role="alert" className="mt-2 text-[0.85rem] text-danger">
              A coluna “{repetidas[0]}” foi usada em mais de um campo. Cada
              campo precisa de uma coluna própria.
            </p>
          ) : null}
        </section>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {error}
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onSubmit}
          disabled={!podeEnviar}
          className="rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Gerando schema…" : "Gerar schema do perfil"}
        </button>
        <button
          type="button"
          onClick={onBack}
          disabled={busy}
          className="rounded-lg border border-white/12 px-5 py-2.5 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
        >
          Voltar
        </button>
      </div>
    </div>
  );
}
