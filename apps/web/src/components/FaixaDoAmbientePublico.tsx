import { Eye } from "lucide-react";

/**
 * A faixa que diz, em toda tela, o que este ambiente é.
 *
 * Ela já se chamou "Demonstração pública", e o nome era o problema:
 * "demonstração" sugere maquete, protótipo, coisa montada para a foto — e o
 * que está do outro lado é o AutoTarefas funcionando, com máquina, agendador e
 * execuções de verdade. O rótulo trabalhava contra o que a tela mostra.
 *
 * "Ambiente público" diz o que é sem sugerir o que não é. A condição de só
 * leitura fica no texto, e não no título: ela é uma característica **desta
 * sessão**, não a natureza do ambiente.
 *
 * Fica fixa no topo, e não num aviso que se fecha: quem entra por um link
 * direto numa seção interna precisa da mesma informação que quem entrou pela
 * porta da frente.
 */
export default function FaixaDoAmbientePublico() {
  return (
    <div
      role="note"
      aria-label="Ambiente público"
      className="border-b border-signal/25 bg-signal/[0.07]"
    >
      <div className="container-page flex items-start gap-2.5 py-2">
        <Eye aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
        <p className="text-[0.8rem] leading-relaxed text-fg">
          <strong className="font-semibold text-signal">Ambiente público.</strong>{" "}
          Máquinas, políticas, execuções e evidências exibidas aqui são
          produzidas pelo ambiente real do AutoTarefas.{" "}
          <span className="text-muted">
            Nesta sessão você pode navegar e consultar os dados, sem alterar a
            configuração do ambiente.
          </span>
        </p>
      </div>
    </div>
  );
}
