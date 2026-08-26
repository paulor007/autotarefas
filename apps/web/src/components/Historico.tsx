import { useCallback, useEffect, useState } from "react";

import { listarHistorico, type Execucao } from "../lib/plataforma";

interface Props {
  /** Vazio = toda a organização. Preenchido = só aquela máquina. */
  dispositivoId?: string;
}

/** Quanto tempo entre uma leitura e a seguinte. */
const INTERVALO_MS = 30_000;

/**
 * Histórico de execuções: o que rodou, quando, e o que produziu.
 *
 * A linha mais importante desta tela é a que ninguém pediu para acontecer: a
 * execução com origem `agendamento`, feita de madrugada, com o navegador
 * fechado. É ela que separa "o cliente pode mandar fazer backup" de "o cliente
 * tem backup", e por isso ela vem marcada.
 *
 * Duas recusas de mentir governam o resto:
 *
 * 1. **"Com ressalva" não é sucesso.** Um backup que copiou quase tudo tem
 *    ausências, e quem um dia for restaurar precisa saber disso antes.
 * 2. **Histórico vazio é dito como vazio.** Não há linha de exemplo, nem
 *    "aguardando" para uma máquina que nunca executou nada.
 */
export default function Historico({ dispositivoId = "" }: Props) {
  const [execucoes, setExecucoes] = useState<Execucao[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const resposta = await listarHistorico(dispositivoId);
      setExecucoes(resposta.execucoes);
      setErro(null);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível carregar");
    }
  }, [dispositivoId]);

  useEffect(() => {
    void carregar();
    // O histórico ganha linhas sozinho: a máquina reconecta e manda o que
    // rodou enquanto ninguém olhava. Sem recarregar, a tela mostraria um
    // retrato do momento em que foi aberta.
    const relogio = setInterval(() => void carregar(), INTERVALO_MS);
    return () => clearInterval(relogio);
  }, [carregar]);

  if (erro) {
    return (
      <p className="rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
        {erro}
      </p>
    );
  }

  if (execucoes === null) {
    return <p className="text-sm text-muted">Carregando histórico…</p>;
  }

  if (execucoes.length === 0) {
    return (
      <p className="text-sm text-muted">
        Nenhuma execução registrada ainda. Assim que um backup rodar — pela tela
        ou pelo horário agendado — ele aparece aqui.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {execucoes.map((item) => (
        <li
          key={item.id}
          className="rounded-lg border border-white/10 bg-surface px-4 py-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-fg">
                {quando(item.iniciada_em)}
              </p>
              <p className="text-[0.8rem] text-muted">
                {item.arquivos} arquivo(s) · pacote de {emMB(item.bytes_copiados)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {item.origem === "agendamento" && (
                <span className="rounded-full bg-signal/15 px-2 py-0.5 text-[0.7rem] font-semibold text-signal">
                  Pelo horário agendado
                </span>
              )}
              <span
                className={`rounded-full px-2 py-0.5 text-[0.7rem] font-semibold ${corDoResultado(
                  item.resultado,
                )}`}
              >
                {rotuloDoResultado(item.resultado)}
              </span>
            </div>
          </div>

          {item.ressalva && (
            <p className="mt-2 text-[0.85rem] text-muted">{item.ressalva}</p>
          )}

          {item.artefatos.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1">
              {item.artefatos.map((artefato) => (
                <li key={artefato.id} className="text-[0.8rem] text-muted">
                  <span className="font-mono text-fg">{artefato.nome}</span>{" "}
                  · {emMB(artefato.tamanho_bytes)} · guardado na própria máquina
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * "Com ressalva" ganha cor própria, e não a de sucesso.
 *
 * Pintar de verde um backup com ausências é a forma mais silenciosa de esconder
 * o que faltou de quem um dia vai restaurar.
 */
function corDoResultado(resultado: Execucao["resultado"]): string {
  if (resultado === "sucesso") return "bg-ok/15 text-ok";
  if (resultado === "com_ressalva") return "bg-signal/15 text-signal";
  if (resultado === "em_andamento") return "bg-white/5 text-muted";
  return "bg-danger/15 text-danger";
}

function rotuloDoResultado(resultado: Execucao["resultado"]): string {
  const nomes: Record<Execucao["resultado"], string> = {
    em_andamento: "Em andamento",
    sucesso: "Concluído",
    com_ressalva: "Concluído com ressalva",
    falha: "Falhou",
    cancelada: "Cancelada",
  };
  return nomes[resultado] ?? resultado;
}

/** Data legível, ou o texto cru quando não dá para interpretar. */
function quando(bruto: string): string {
  if (!bruto) return "sem data";
  const data = new Date(bruto);
  if (Number.isNaN(data.getTime())) return bruto;
  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function emMB(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
