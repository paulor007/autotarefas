import { AlertTriangle, HelpCircle, ShieldAlert, ShieldCheck } from "lucide-react";
import type { ComponentType } from "react";

import type { EstadoDeProtecao, NivelDeProtecao } from "../lib/plataforma";

const APARENCIA: Record<
  NivelDeProtecao,
  {
    icone: ComponentType<{ className?: string }>;
    cor: string;
    borda: string;
    fundo: string;
  }
> = {
  protegido: {
    icone: ShieldCheck,
    cor: "text-ok",
    borda: "border-ok/30",
    fundo: "bg-ok/5",
  },
  parcial: {
    icone: AlertTriangle,
    cor: "text-signal",
    borda: "border-signal/30",
    fundo: "bg-signal/5",
  },
  em_risco: {
    icone: ShieldAlert,
    cor: "text-danger",
    borda: "border-danger/30",
    fundo: "bg-danger/5",
  },
  sem_configuracao: {
    icone: HelpCircle,
    cor: "text-muted",
    borda: "border-white/10",
    fundo: "bg-surface",
  },
};

/**
 * A resposta para a única pergunta que um cliente de backup faz.
 *
 * Antes era preciso montar a resposta na cabeça: olhar as máquinas, cruzar
 * com as políticas, descer até o histórico e conferir a data do último
 * backup. Quem não soubesse que "cópia no mesmo disco" não é proteção
 * concluiria errado — e concluiria errado para o lado tranquilo.
 *
 * Cada motivo que aparece aqui é um fato registrado, nunca uma estimativa. E
 * o veredito nunca é melhor do que o pior dos backups: um "protegido" errado
 * troca a desconfiança saudável por confiança falsa, e a pessoa só descobre
 * no dia em que precisa restaurar.
 */
export default function SeloDeProtecao({
  estado,
}: {
  estado: EstadoDeProtecao | null;
}) {
  if (!estado) {
    return (
      <div className="rounded-2xl border border-white/10 bg-surface px-5 py-4">
        <p className="text-sm text-muted">Conferindo…</p>
      </div>
    );
  }

  const { icone: Icone, cor, borda, fundo } = APARENCIA[estado.nivel];

  // Agrupado POR MOTIVO, e nao por backup.
  //
  // Quatro politicas num servidor unico produzem quatro ressalvas identicas —
  // e quatro paragrafos iguais empilhados nao informam quatro vezes: informam
  // uma vez e cansam tres. Agrupar mostra o que e sistemico ("os quatro
  // backups estao no mesmo disco") em vez de repetir o que ja foi lido.
  const porMotivo = new Map<string, string[]>();
  for (const item of estado.backups) {
    for (const motivo of item.motivos) {
      porMotivo.set(motivo, [...(porMotivo.get(motivo) ?? []), item.nome]);
    }
  }
  const motivos = [...porMotivo.entries()].map(([motivo, backups]) => ({
    motivo,
    backups,
  }));

  return (
    <section
      aria-label="Estado da proteção"
      className={`rounded-2xl border ${borda} ${fundo} px-5 py-4`}
    >
      <div className="flex items-start gap-3">
        <Icone className={`mt-0.5 h-6 w-6 shrink-0 ${cor}`} />
        <div className="min-w-0">
          <h2 className={`text-lg font-semibold ${cor}`}>{estado.titulo}</h2>
          <p className="mt-0.5 text-[0.9rem] text-muted">{estado.resumo}</p>
        </div>
      </div>

      {motivos.length > 0 && (
        <ul className="mt-4 flex flex-col gap-2 border-t border-white/[0.06] pt-4">
          {motivos.map(({ motivo, backups }) => (
            <li key={motivo} className="text-[0.85rem] text-muted">
              <span className="font-semibold text-fg">
                {backups.length === 1
                  ? backups[0]
                  : `${backups.length} backups`}
              </span>{" "}
              — {motivo}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
