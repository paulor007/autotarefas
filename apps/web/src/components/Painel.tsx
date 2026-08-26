import { useCallback, useEffect, useState } from "react";

import Auditoria from "./Auditoria";
import Dispositivos from "./Dispositivos";
import Historico from "./Historico";
import Politicas from "./Politicas";
import PrimeiroAcesso from "./PrimeiroAcesso";
import {
  conviteDaUrl,
  obterEstadoDeSessao,
  sair,
  type EstadoDeSessao,
} from "../lib/plataforma";

/**
 * A parte do Live que exige conta: organização, dispositivos e execução real.
 *
 * O painel decide o que mostrar a partir do que o servidor **diz**, e não do
 * que seria conveniente supor:
 *
 * - banco vazio → primeiro acesso (o convite está no console do servidor);
 * - sem sessão e com provedor configurado → botão de entrar, que funciona;
 * - sem sessão e **sem** provedor → a tela diz isso, em vez de mostrar um
 *   botão que levaria a lugar nenhum. Botão que não funciona é a mentira mais
 *   fácil de cometer numa interface, e a mais cara de descobrir.
 */
export default function Painel() {
  const [estado, setEstado] = useState<EstadoDeSessao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      setEstado(await obterEstadoDeSessao());
      setErro(null);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível carregar");
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (erro) {
    return (
      <section className="mx-auto max-w-3xl rounded-2xl border border-danger/30 bg-danger/5 p-6">
        <p className="text-sm text-danger">{erro}</p>
      </section>
    );
  }

  if (!estado) {
    return (
      <section className="mx-auto max-w-3xl p-6">
        <p className="text-sm text-muted">Carregando…</p>
      </section>
    );
  }

  if (estado.precisa_bootstrap) {
    return <PrimeiroAcesso convite={conviteDaUrl()} aoCriar={() => void carregar()} />;
  }

  if (!estado.autenticado) {
    return (
      <section className="mx-auto max-w-3xl rounded-2xl border border-white/10 bg-surface p-6">
        <h2 className="text-lg font-semibold text-fg">Entrar</h2>
        {estado.provedor_configurado ? (
          <>
            <p className="mt-2 text-sm text-muted">
              Use a conta que sua empresa já usa. O AutoTarefas não guarda
              senha: quem confirma quem você é será o seu provedor.
            </p>
            <a
              href="/api/auth/entrar"
              className="mt-4 inline-block rounded-lg border border-white/12 px-4 py-2 text-sm font-semibold text-fg hover:border-white/25"
            >
              Entrar com a conta da empresa
            </a>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">
            Este servidor ainda não tem um provedor de identidade configurado,
            então não há como entrar por aqui. Quem administra o servidor
            precisa configurar <code>OIDC_ISSUER</code>,{" "}
            <code>OIDC_CLIENT_ID</code> e <code>OIDC_CLIENT_SECRET</code>.
          </p>
        )}
      </section>
    );
  }

  const papel = estado.organizacao?.papel ?? "leitor";

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-surface px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-fg">
            {estado.organizacao?.nome}
          </p>
          <p className="text-[0.8rem] text-muted">
            {estado.usuario?.email} · {papel}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void sair().then(() => carregar())}
          className="rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] text-fg hover:border-white/25"
        >
          Sair
        </button>
      </header>

      <Dispositivos papel={papel} />

      <Politicas papel={papel} />

      <section>
        <h2 className="text-lg font-semibold text-fg">Histórico</h2>
        <p className="mt-1 text-[0.8rem] text-muted">
          Inclui o que rodou pelo horário agendado, com o navegador fechado.
        </p>
        <div className="mt-3">
          <Historico />
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-fg">Auditoria</h2>
        <p className="mt-1 text-[0.8rem] text-muted">
          O que foi feito nesta organização, encadeado por hash.
        </p>
        <div className="mt-3">
          <Auditoria />
        </div>
      </section>
    </div>
  );
}
