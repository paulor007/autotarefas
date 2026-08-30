import { useEffect, useState } from "react";
import { Loader2, Clock } from "lucide-react";

import { obterAoVivo, type AtividadeAoVivo } from "../lib/plataforma";
import { quando } from "../lib/datas";

/** De quanto em quanto tempo perguntar. */
const INTERVALO_MS = 4000;

/**
 * O que está acontecendo agora, e o que vem depois.
 *
 * O histórico responde "funcionou", com data, tamanho e hash — evidência forte,
 * e ainda assim quem chega de fora olha uma lista de linhas prontas e não vê
 * nenhuma delas acontecer. A diferença entre ler que um backup ocorreu e ver um
 * ocorrendo é a mesma que há entre um extrato e uma máquina funcionando.
 *
 * Três decisões de honestidade, e cada uma tem um jeito fácil e errado de
 * fazer:
 *
 * **Nada rodando é uma resposta, e não uma tela para preencher.** O caminho
 * fácil seria disparar um backup quando alguém abre a página. Isso é mexer na
 * máquina do cliente para melhorar uma demonstração.
 *
 * **Nenhuma barra de porcentagem.** O Agente manda a etapa em que está, não
 * quanto falta — arquivo grande e arquivo pequeno levam tempos que ninguém
 * consegue prever antes de ler. Uma barra que avança sozinha é a forma mais
 * fácil de mentir sobre trabalho que não está acontecendo.
 *
 * **O próximo horário aparece sempre.** Sem ele, uma lista vazia não
 * distingue "nada rodando agora" de "isto aqui está morto".
 */
export default function AoVivo() {
  const [dados, setDados] = useState<AtividadeAoVivo | null>(null);

  useEffect(() => {
    let vivo = true;
    const perguntar = async () => {
      try {
        const resposta = await obterAoVivo();
        if (vivo) setDados(resposta);
      } catch {
        // Silêncio de propósito: este bloco é acessório. Uma falha de rede
        // aqui não pode encher de vermelho uma tela cujo assunto principal —
        // se há backup — está logo acima e continua correto.
      }
    };
    void perguntar();
    const relogio = setInterval(() => void perguntar(), INTERVALO_MS);
    return () => {
      vivo = false;
      clearInterval(relogio);
    };
  }, []);

  if (dados === null) return null;

  const rodando = dados.executando;
  const proxima = dados.proximas.find(
    (item) => item.proxima_no_relogio_da_maquina,
  );

  return (
    <section
      aria-label="Atividade agora"
      className="rounded-xl border border-white/10 bg-surface px-4 py-3"
    >
      {rodando.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {rodando.map((item) => (
            <li
              key={`${item.dispositivo_id}:${item.politica_id}`}
              className="flex flex-wrap items-center gap-2 text-sm"
            >
              <Loader2
                aria-hidden
                className="h-4 w-4 shrink-0 animate-spin text-signal"
              />
              <strong className="font-semibold text-fg">
                {item.politica_nome || "Backup"}
              </strong>
              <span className="text-signal">{item.etapa_em_portugues}</span>
              <span className="text-muted">· {item.maquina}</span>
              {typeof item.arquivos === "number" && (
                <span className="text-muted">
                  · {item.arquivos} arquivo{item.arquivos === 1 ? "" : "s"}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Clock aria-hidden className="h-4 w-4 shrink-0 text-muted" />
          <span className="text-muted">Nenhum backup rodando agora.</span>
          {proxima && (
            <span className="text-fg">
              Próximo: <strong className="font-semibold">{proxima.nome}</strong>
              {", "}
              {quando(proxima.proxima_no_relogio_da_maquina)}
              {/* "no relógio da máquina" não é preciosismo: o horário de uma
                  política é o relógio de quem executa, e o servidor pode estar
                  a três fusos dali. Sem a ressalva, a tela mostraria 03:00 do
                  fuso errado com toda a confiança de um dado exato. */}
              <span className="text-muted"> (relógio da máquina)</span>
            </span>
          )}
        </div>
      )}
    </section>
  );
}
