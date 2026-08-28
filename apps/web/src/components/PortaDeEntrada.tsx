import PrimeiroAcesso from "./PrimeiroAcesso";
import { conviteDaUrl, type EstadoDeSessao } from "../lib/plataforma";

/**
 * O que o produto mostra a quem ainda nao entrou.
 *
 * Tudo aqui e decidido pelo que o servidor **diz**, e nao pelo que seria
 * conveniente supor:
 *
 * - banco vazio → primeiro acesso (o convite esta no console do servidor);
 * - sem sessao e com provedor configurado → botao de entrar, que funciona;
 * - sem sessao e **sem** provedor → a tela diz isso, em vez de mostrar um
 *   botao que levaria a lugar nenhum. Botao que nao funciona e a mentira mais
 *   facil de cometer numa interface, e a mais cara de descobrir.
 */
export default function PortaDeEntrada({
  estado,
  erro,
  aoEntrar,
}: {
  estado: EstadoDeSessao | null;
  erro: string | null;
  aoEntrar: () => void;
}) {
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
    return <PrimeiroAcesso convite={conviteDaUrl()} aoCriar={aoEntrar} />;
  }

  return (
    <section className="mx-auto max-w-3xl rounded-2xl border border-white/10 bg-surface p-6">
      <h2 className="text-lg font-semibold text-fg">Entrar</h2>
      {estado.provedor_configurado ? (
        <>
          <p className="mt-2 text-sm text-muted">
            Use a conta que sua empresa já usa. O AutoTarefas não guarda senha:
            quem confirma quem você é será o seu provedor.
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
          então não há como entrar por aqui. Quem administra o servidor precisa
          configurar <code>OIDC_ISSUER</code>, <code>OIDC_CLIENT_ID</code> e{" "}
          <code>OIDC_CLIENT_SECRET</code>.
        </p>
      )}
    </section>
  );
}
