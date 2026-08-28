import { ArrowRight, ShieldCheck } from "lucide-react";

import { cliqueDeNavegacao, enderecoDa } from "../lib/rotas";

const BACKUPS = enderecoDa("backups");
const DISPOSITIVOS = enderecoDa("dispositivos");

interface UltimoBackup {
  resultado: string;
  em: string;
}

const CORES: Record<string, string> = {
  sucesso: "text-ok",
  com_ressalva: "text-signal",
  falha: "text-danger",
  cancelada: "text-muted",
  em_andamento: "text-cyan",
};

const NOMES: Record<string, string> = {
  sucesso: "concluído",
  com_ressalva: "concluído com ressalva",
  falha: "falhou",
  cancelada: "cancelado",
  em_andamento: "em andamento",
};

/**
 * O cartao do backup automatico.
 *
 * A regra que ele obedece: um cartao representa uma capacidade real e leva
 * direto ao lugar onde ela se opera. Sem nada configurado, ele diz o que
 * falta e abre exatamente esse passo; configurado, mostra o estado e abre o
 * painel. Em nenhum dos dois casos ele e so um texto bonito.
 */
export default function CartaoDeAutomacao({
  carregando,
  maquinas,
  conectadas,
  backupsAtivos,
  ultimoBackup,
}: {
  carregando: boolean;
  maquinas: number;
  conectadas: number;
  backupsAtivos: number;
  ultimoBackup: UltimoBackup | null;
}) {
  const semMaquina = maquinas === 0;
  const semBackup = backupsAtivos === 0;
  const destino = semMaquina ? DISPOSITIVOS : BACKUPS;
  const acao = semMaquina
    ? "Adicionar máquina"
    : semBackup
      ? "Configurar backup"
      : "Abrir";

  return (
    <article className="rounded-2xl border border-white/10 bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="rounded-lg bg-signal/10 p-2">
            <ShieldCheck className="h-5 w-5 text-signal" />
          </span>
          <div>
            <h2 className="text-base font-semibold text-fg">
              Backup automático
            </h2>
            <p className="text-[0.8rem] text-muted">
              Pastas do computador, no horário, com o navegador fechado.
            </p>
          </div>
        </div>
      </div>

      {carregando ? (
        <p className="mt-5 text-sm text-muted">Carregando…</p>
      ) : semMaquina ? (
        <p className="mt-5 text-sm text-muted">
          Nenhuma máquina conectada. O backup roda no computador, então ele
          precisa do Agente instalado lá — nenhum navegador alcança o disco de
          ninguém.
        </p>
      ) : semBackup ? (
        <p className="mt-5 text-sm text-muted">
          {/* O selo acima ja disse que nao ha backup ativo. Repetir a frase
              aqui gastaria a atencao da pessoa duas vezes com a mesma
              informacao; o cartao diz o que FALTA. */}
          {maquinas === 1 ? "1 máquina pronta" : `${maquinas} máquinas prontas`}
          . Falta dizer o que copiar, para onde e em que horário.
        </p>
      ) : (
        <dl className="mt-5 grid gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
              Backups ativos
            </dt>
            <dd className="mt-0.5 text-sm text-fg">{backupsAtivos}</dd>
          </div>
          <div>
            <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
              Máquinas
            </dt>
            <dd className="mt-0.5 text-sm text-fg">
              {conectadas} de {maquinas} conectada{maquinas === 1 ? "" : "s"}
            </dd>
          </div>
          <div>
            <dt className="text-[0.75rem] uppercase tracking-wide text-muted">
              Último backup
            </dt>
            <dd className="mt-0.5 text-sm text-fg">
              {ultimoBackup ? (
                <>
                  <span className={CORES[ultimoBackup.resultado] ?? "text-fg"}>
                    {NOMES[ultimoBackup.resultado] ?? ultimoBackup.resultado}
                  </span>
                  <span className="text-muted"> · {ultimoBackup.em}</span>
                </>
              ) : (
                <span className="text-muted">ainda não rodou</span>
              )}
            </dd>
          </div>
        </dl>
      )}

      <a
        href={destino}
        onClick={cliqueDeNavegacao(destino)}
        className="mt-5 inline-flex items-center gap-2 rounded-lg border border-signal/40 bg-signal/10 px-4 py-2 text-sm font-semibold text-signal transition-colors hover:border-signal/70"
      >
        {acao}
        <ArrowRight className="h-4 w-4" />
      </a>
    </article>
  );
}
