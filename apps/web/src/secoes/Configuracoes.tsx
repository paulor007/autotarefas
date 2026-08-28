import { sair, type EstadoDeSessao } from "../lib/plataforma";

/**
 * Conta e organizacao.
 *
 * "Sair" mora aqui, e nao no cabecalho. No painel antigo ele era o botao mais
 * destacado da tela — ao lado do nome da empresa, no topo, sozinho — enquanto
 * "Parear nova maquina" ficava cinco blocos abaixo. Alguem procurando parear
 * clicou em Sair, porque era o que estava a vista. Terminar a sessao nao e uma
 * funcao do produto; e o fim do uso dele.
 */
export default function Configuracoes({
  estado,
  aoSair,
}: {
  estado: EstadoDeSessao;
  aoSair: () => void;
}) {
  const papel = estado.organizacao?.papel ?? "leitor";

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
