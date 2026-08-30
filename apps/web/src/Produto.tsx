/**
 * O produto: `/app`.
 *
 * A parte que exige sessao. Aqui ficam as maquinas, as politicas, o historico
 * e a auditoria — o AutoTarefas que uma empresa contrata, separado da vitrine
 * que qualquer visitante ve.
 *
 * Era um bloco no fim da vitrine, com tudo empilhado numa coluna so. Agora sao
 * cinco secoes a um clique uma da outra, e cada uma tem endereco proprio.
 */

import { useEffect } from "react";
import { CheckSquare } from "lucide-react";

import Dispositivos from "./components/Dispositivos";
import FaixaDeDemonstracao from "./components/FaixaDeDemonstracao";
import NavegacaoDoProduto from "./components/NavegacaoDoProduto";
import Politicas from "./components/Politicas";
import PortaDeEntrada from "./components/PortaDeEntrada";
import Atividade from "./secoes/Atividade";
import Configuracoes from "./secoes/Configuracoes";
import Inicio from "./secoes/Inicio";
import { useSessao } from "./hooks/useSessao";
import {
  cliqueDeNavegacao,
  secaoDe,
  useCaminho,
  VITRINE,
  type Secao,
} from "./lib/rotas";
import type { EstadoDeSessao } from "./lib/plataforma";

/**
 * A faixa de cima: onde voce esta, e em nome de quem.
 *
 * A organizacao fica aqui, em toda tela, porque e o contexto de tudo que se
 * faz adiante — quem administra mais de uma empresa precisa ver isso sem
 * procurar. O que NAO fica aqui e o "Sair": ele era o botao mais destacado do
 * painel antigo, ao lado deste mesmo nome, e foi clicado por engano por quem
 * procurava "Parear nova maquina". Terminar a sessao mora em Configuracoes.
 */
function Cabecalho({ estado }: { estado: EstadoDeSessao | null }) {
  return (
    <header className="border-b border-white/[0.06] bg-ink/85 backdrop-blur-xl">
      <div className="container-page flex h-16 items-center justify-between gap-4">
        <a
          href={VITRINE}
          onClick={cliqueDeNavegacao(VITRINE)}
          className="flex items-center gap-2.5"
        >
          <CheckSquare className="h-5 w-5 text-signal" />
          <span className="text-[1.05rem] font-bold tracking-tight">
            AutoTarefas
          </span>
        </a>
        {estado?.autenticado && (
          <div className="min-w-0 text-right">
            <p className="truncate text-sm font-semibold text-fg">
              {estado.organizacao?.nome}
            </p>
            <p className="truncate text-[0.75rem] text-muted">
              {estado.usuario?.email}
            </p>
          </div>
        )}
      </div>
    </header>
  );
}

/**
 * A entrada do visitante, que acontece sozinha.
 *
 * Quem chega pelo portfólio clicou em "Acessar projeto" e espera estar dentro.
 * Uma tela de login no caminho — mesmo com um botão só — é um obstáculo entre a
 * pessoa e a coisa que ela veio ver, e ela não tem conta nenhuma para usar.
 *
 * Por que uma navegação de página inteira, e não um `fetch`: a rota devolve um
 * redirecionamento com o cookie da sessão, e é o navegador quem precisa
 * recebê-lo. Um `fetch` guardaria o cookie e deixaria a tela sem saber que
 * agora há sessão.
 *
 * A tela existe entre o clique e o redirecionamento, e por isso é uma frase e
 * não um formulário: se algo der errado no meio, o servidor responde 404 e o
 * navegador mostra o motivo — em vez de esta tela ficar girando para sempre.
 */
function EntrandoComoVisitante() {
  useEffect(() => {
    // Leva junto para onde a pessoa estava indo. Um link de portfolio nem
    // sempre aponta para a porta da frente: alguem compartilha
    // `/app/atividade`, ou o visitante recarrega estando numa secao. Sem isto,
    // toda entrada caia em `/app` e o lugar se perdia.
    //
    // Quem valida o destino e o SERVIDOR — ele chega pela URL, e um destino
    // fora de `/app` seria um redirecionamento aberto.
    const daqui = window.location.pathname + window.location.search;
    window.location.href = `/api/auth/visitante?destino=${encodeURIComponent(daqui)}`;
  }, []);

  return (
    <section className="mx-auto max-w-3xl rounded-2xl border border-white/10 bg-surface p-6">
      <p className="text-sm text-muted" role="status">
        Abrindo a demonstração pública do AutoTarefas…
      </p>
    </section>
  );
}

function Secao({
  secao,
  estado,
  aoSair,
}: {
  secao: Secao;
  estado: EstadoDeSessao;
  aoSair: () => void;
}) {
  const papel = estado.organizacao?.papel ?? "leitor";
  // Vem do servidor, e nao do papel. Sao duas travas independentes de
  // proposito: um `leitor` de uma empresa de verdade continua vendo a tela do
  // jeito de sempre, e so a sessao publica muda de comportamento.
  const somenteLeitura = estado.somente_leitura === true;
  switch (secao) {
    case "backups":
      return <Politicas papel={papel} somenteLeitura={somenteLeitura} />;
    case "dispositivos":
      return <Dispositivos papel={papel} somenteLeitura={somenteLeitura} />;
    case "atividade":
      return <Atividade />;
    case "configuracoes":
      return <Configuracoes estado={estado} aoSair={aoSair} />;
    default:
      return <Inicio />;
  }
}

export default function Produto() {
  const { estado, erro, recarregar } = useSessao();
  const caminho = useCaminho();

  if (!estado?.autenticado) {
    return (
      <div className="min-h-screen">
        <Cabecalho estado={estado} />
        <main id="produto" className="container-page py-10">
          {estado?.demonstracao_publica === true ? (
            <EntrandoComoVisitante />
          ) : (
            <PortaDeEntrada estado={estado} erro={erro} aoEntrar={recarregar} />
          )}
        </main>
      </div>
    );
  }

  const secao = secaoDe(caminho);

  return (
    <div className="min-h-screen">
      <Cabecalho estado={estado} />
      {estado.somente_leitura === true && <FaixaDeDemonstracao />}
      <NavegacaoDoProduto atual={secao} />
      {/* `id` fixo: e por ele que a homologacao de ponta a ponta limita o
          escopo do que procura. Sem isso, um "Executar agora" da demonstracao
          da vitrine passaria por um do produto. */}
      <main id="produto" className="container-page py-8">
        {/* A largura e decidida aqui, uma vez. Antes cada bloco trazia a
            propria, e as secoes nao se alinhavam entre si. */}
        <div className="mx-auto max-w-4xl">
          <Secao secao={secao} estado={estado} aoSair={recarregar} />
        </div>
      </main>
    </div>
  );
}
