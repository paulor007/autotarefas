import { sair, type EstadoDeSessao } from "../lib/plataforma";

/**
 * Conta e organização.
 *
 * "Sair" mora aqui, e não no cabeçalho. No painel antigo ele era o botão mais
 * destacado da tela — ao lado do nome da empresa, no topo, sozinho — enquanto
 * "Parear nova máquina" ficava cinco blocos abaixo. Alguém procurando parear
 * clicou em Sair, porque era o que estava à vista. Terminar a sessão não é uma
 * função do produto; é o fim do uso dele.
 *
 * No **ambiente público** esta tela é outra, e por um motivo simples: não há
 * conta. "Sair" encerraria o quê? A sessão nasce sozinha na entrada e
 * renasceria no próximo clique — o botão seria um gesto sem consequência.
 * "Você" e "Papel" também não dizem nada a quem não tem cadastro.
 *
 * O que sobra é o que a pessoa de fato quer saber ali: o que é este ambiente,
 * e o que esta sessão pode fazer nele.
 */
export default function Configuracoes({
  estado,
  aoSair,
}: {
  estado: EstadoDeSessao;
  aoSair: () => void;
}) {
  const papel = estado.organizacao?.papel ?? "leitor";
  const publico = estado.somente_leitura === true;

  if (publico) {
    return (
      <div className="flex flex-col gap-6">
        <section className="rounded-2xl border border-white/10 bg-surface p-5">
          <h2 className="text-lg font-semibold text-fg">Esta sessão</h2>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
                Acesso
              </dt>
              <dd className="mt-0.5 text-sm text-fg">Ambiente público</dd>
            </div>
            <div>
              <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
                O que você pode fazer
              </dt>
              <dd className="mt-0.5 text-sm text-fg">
                Navegar e consultar os dados
              </dd>
            </div>
          </dl>
        </section>

        <section className="rounded-2xl border border-white/10 bg-surface p-5">
          <h2 className="text-lg font-semibold text-fg">Sobre este ambiente</h2>
          <p className="mt-2 text-[0.85rem] leading-relaxed text-muted">
            As máquinas, políticas e execuções que aparecem aqui pertencem a um
            ambiente que o próprio projeto mantém no ar. O Agente roda como
            serviço no computador, o agendador dispara nos horários de cada
            política, e o histórico é o que aconteceu — não há nada montado para
            a tela.
          </p>
          <p className="mt-3 text-[0.85rem] leading-relaxed text-muted">
            A configuração deste ambiente não muda por aqui. Num AutoTarefas de
            uma empresa, esta mesma tela é onde se administra a organização e se
            encerra a sessão.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl border border-white/10 bg-surface p-5">
        <h2 className="text-lg font-semibold text-fg">Organização</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          <div>
            <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
              Empresa
            </dt>
            <dd className="mt-0.5 text-sm text-fg">{estado.organizacao?.nome}</dd>
          </div>
          <div>
            <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
              Você
            </dt>
            <dd className="mt-0.5 text-sm text-fg">{estado.usuario?.email}</dd>
          </div>
          <div>
            <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
              Papel
            </dt>
            <dd className="mt-0.5 text-sm text-fg">{papel}</dd>
          </div>
        </dl>
      </section>

      <section className="rounded-2xl border border-white/10 bg-surface p-5">
        <h2 className="text-lg font-semibold text-fg">Sessão</h2>
        <p className="mt-1 text-[0.85rem] text-muted">
          Sair encerra apenas este navegador. O Agente continua rodando nas
          máquinas e os backups agendados continuam acontecendo.
        </p>
        <button
          type="button"
          onClick={() => void sair().then(aoSair)}
          className="mt-4 rounded-lg border border-white/12 px-4 py-2 text-sm text-fg hover:border-white/25"
        >
          Sair
        </button>
      </section>
    </div>
  );
}
