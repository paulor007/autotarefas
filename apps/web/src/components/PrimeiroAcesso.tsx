import { useState } from "react";

import { primeiroAcesso, type EstadoDeSessao } from "../lib/plataforma";

interface Props {
  /** Convite lido da URL. Vazio quando a pessoa chegou sem o link. */
  convite: string;
  /** Chamado depois de criar a organização, para a tela recarregar o estado. */
  aoCriar: () => void;
}

/**
 * Primeiro acesso: cria a organização e o primeiro administrador.
 *
 * Aparece só enquanto **não existe organização nenhuma**. O convite é impresso
 * no console de quem subiu o serviço — é a única parte do fluxo que exige
 * provar acesso à máquina onde o AutoTarefas roda.
 *
 * Sem o convite na URL, a tela não mostra um formulário que vai falhar: ela
 * diz onde encontrar o link. Um campo que aceita qualquer coisa e depois
 * recusa transforma um passo simples num chamado de suporte.
 */
export default function PrimeiroAcesso({ convite, aoCriar }: Props) {
  const [organizacao, setOrganizacao] = useState("");
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const criar = async () => {
    if (enviando) return;
    setEnviando(true);
    setErro(null);
    try {
      await primeiroAcesso({ convite, organizacao, email, nome });
      aoCriar();
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível criar");
    } finally {
      setEnviando(false);
    }
  };

  if (!convite) {
    return (
      <section className="mx-auto max-w-xl rounded-2xl border border-white/10 bg-surface p-6">
        <h2 className="text-lg font-semibold text-fg">Primeiro acesso</h2>
        <p className="mt-2 text-sm text-muted">
          Ainda não existe nenhuma organização neste servidor. O endereço para
          criar a primeira foi impresso <strong>no console</strong> de quem
          subiu o serviço, e vale por poucos minutos.
        </p>
        <p className="mt-2 text-sm text-muted">
          Procure a linha que começa com{" "}
          <code className="rounded bg-black/30 px-1">
            AutoTarefas - primeira execucao
          </code>{" "}
          e abra o endereço que aparece nela.
        </p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-xl rounded-2xl border border-white/10 bg-surface p-6">
      <h2 className="text-lg font-semibold text-fg">Primeiro acesso</h2>
      <p className="mt-1 text-sm text-muted">
        Você vai criar a organização e ficar como responsável por ela.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-muted">
          Nome da empresa
          <input
            value={organizacao}
            onChange={(e) => setOrganizacao(e.target.value)}
            placeholder="Padaria Sol"
            className="rounded-lg border border-white/12 bg-surface px-3 py-2 text-fg"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted">
          Seu e-mail
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="voce@suaempresa.com.br"
            className="rounded-lg border border-white/12 bg-surface px-3 py-2 text-fg"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted">
          Seu nome
          <input
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="rounded-lg border border-white/12 bg-surface px-3 py-2 text-fg"
          />
        </label>
      </div>

      {erro && (
        <p className="mt-3 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
          {erro}
        </p>
      )}

      <button
        type="button"
        onClick={() => void criar()}
        disabled={enviando || !organizacao || !email}
        className="mt-4 rounded-lg border border-white/12 px-4 py-2 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
      >
        {enviando ? "Criando…" : "Criar organização"}
      </button>

      <p className="mt-3 text-[0.8rem] text-muted">
        Este convite vale uma vez só. Depois de criada a primeira organização,
        esta tela deixa de existir.
      </p>
    </section>
  );
}

export type { EstadoDeSessao };
