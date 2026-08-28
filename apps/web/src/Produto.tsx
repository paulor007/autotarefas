/**
 * O produto: `/app`.
 *
 * A parte que exige sessao. Aqui ficam as maquinas, as politicas, o historico
 * e a auditoria — o AutoTarefas que uma empresa contrata, separado da vitrine
 * que qualquer visitante ve.
 */

import { CheckSquare } from "lucide-react";

import Painel from "./components/Painel";
import { cliqueDeNavegacao, VITRINE } from "./lib/rotas";

export default function Produto() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-white/[0.06] bg-ink/85 backdrop-blur-xl">
        <div className="container-page flex h-16 items-center justify-between">
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
        </div>
      </header>
      {/* `id` fixo: e por ele que a homologacao de ponta a ponta limita o
          escopo do que procura. Sem isso, um "Executar agora" da
          demonstracao da vitrine passaria por um do produto. */}
      <main id="produto" className="container-page py-10">
        <Painel />
      </main>
    </div>
  );
}
