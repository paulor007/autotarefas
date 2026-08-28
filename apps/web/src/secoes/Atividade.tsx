import Auditoria from "../components/Auditoria";
import Historico from "../components/Historico";

/**
 * O que aconteceu, e a prova de que aconteceu.
 *
 * Historico e auditoria eram duas secoes soltas no fim do painel. Sao a mesma
 * pergunta em dois niveis: o que rodou, e o registro encadeado que ninguem
 * reescreveu depois.
 */
export default function Atividade() {
  return (
    <div className="flex flex-col gap-8">
      <section>
        <h2 className="text-lg font-semibold text-fg">Execuções</h2>
        <p className="mt-1 text-[0.85rem] text-muted">
          Inclui o que rodou pelo horário agendado, com o navegador fechado.
        </p>
        <div className="mt-3">
          <Historico />
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-fg">Auditoria</h2>
        <p className="mt-1 text-[0.85rem] text-muted">
          O que foi feito nesta organização, encadeado por hash.
        </p>
        <div className="mt-3">
          <Auditoria />
        </div>
      </section>
    </div>
  );
}
