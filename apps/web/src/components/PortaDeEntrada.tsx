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
        <>
          {/* Esta tela dizia "não há como entrar por aqui" e parava. Quem a lê
              é, quase sempre, a própria pessoa que administra o servidor — e
              ela ficava olhando uma tela sem nada para clicar, sem saber que a
              entrada existe e está no console. O caminho tem que estar escrito
              onde a pessoa emperrou. */}
          <p className="mt-2 text-sm text-muted">
            Este servidor não tem provedor de identidade, então não há login por
            formulário. A entrada é <strong className="text-fg">o link que o
            próprio servidor imprime no console</strong> quando sobe.
          </p>
          <ol className="mt-3 flex list-decimal flex-col gap-1 pl-5 text-sm text-muted">
            <li>Volte ao terminal onde o AutoTarefas está rodando.</li>
            <li>
              Se o link já venceu, reinicie o serviço — cada partida imprime um
              novo.
            </li>
            <li>Abra o link. Ele vale uma vez e por 30 minutos.</li>
          </ol>
          <p className="mt-3 text-[0.8rem] text-muted">
            Para uma empresa com contas próprias, o caminho é outro: configurar{" "}
            <code>OIDC_ISSUER</code>, <code>OIDC_CLIENT_ID</code> e{" "}
            <code>OIDC_CLIENT_SECRET</code>. Aí esta tela passa a mostrar o botão
            de entrar com a conta da empresa.
          </p>
        </>
      )}
    </section>
  );
}
