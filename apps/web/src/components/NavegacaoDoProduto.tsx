import {
  Activity,
  HardDrive,
  LayoutDashboard,
  Settings,
  ShieldCheck,
} from "lucide-react";
import type { ComponentType } from "react";

import {
  cliqueDeNavegacao,
  enderecoDa,
  SECOES,
  type Secao,
} from "../lib/rotas";

const ROTULOS: Record<Secao, { nome: string; icone: ComponentType<{ className?: string }> }> = {
  inicio: { nome: "Início", icone: LayoutDashboard },
  backups: { nome: "Backups", icone: ShieldCheck },
  dispositivos: { nome: "Dispositivos", icone: HardDrive },
  atividade: { nome: "Atividade", icone: Activity },
  configuracoes: { nome: "Configurações", icone: Settings },
};

/**
 * A navegacao do produto.
 *
 * Cinco secoes fixas, sempre visiveis. O que estava dentro de um bloco no meio
 * de uma pagina longa — dispositivos, politicas, historico, auditoria — agora
 * tem lugar proprio e distancia igual: um clique de qualquer outro.
 */
export default function NavegacaoDoProduto({ atual }: { atual: Secao }) {
  return (
    <nav
      aria-label="Seções do produto"
      className="border-b border-white/[0.06] bg-ink/60"
    >
      <div className="container-page flex gap-1 overflow-x-auto">
        {SECOES.map((secao) => {
          const { nome, icone: Icone } = ROTULOS[secao];
          const aqui = secao === atual;
          const destino = enderecoDa(secao);
          return (
            <a
              key={secao}
              href={destino}
              onClick={cliqueDeNavegacao(destino)}
              aria-current={aqui ? "page" : undefined}
              className={`flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium transition-colors ${
                aqui
                  ? "border-signal text-fg"
                  : "border-transparent text-muted hover:text-fg"
              }`}
            >
              <Icone className="h-4 w-4" />
              {nome}
            </a>
          );
        })}
      </div>
    </nav>
  );
}
