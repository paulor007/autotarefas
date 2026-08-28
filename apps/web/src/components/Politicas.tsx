import { useCallback, useEffect, useRef, useState } from "react";

import AssistenteDeBackup from "./AssistenteDeBackup";
import { cliqueDeNavegacao, comVolta, enderecoDa } from "../lib/rotas";

import {
  ErroDaPlataforma,
  executarBackup,
  listarDispositivos,
  listarPoliticas,
  removerPolitica,
  type ConfiguracaoDePolitica,
  type Dispositivo,
  type Politica,
  type Sincronizacao,
} from "../lib/plataforma";

interface Props {
  /** Papel de quem está olhando: só quem administra cria e remove política. */
  papel: string;
}

const ADMINISTRAM = new Set(["dono", "administrador"]);

/** O pareamento, com o caminho de volta para esta mesma tela. */
const PARA_PAREAR = comVolta(enderecoDa("dispositivos"), enderecoDa("backups"));

/**
 * Políticas de backup: o que copiar, para onde, quando, por quanto tempo.
 *
 * Esta é a tela que transforma "posso mandar fazer backup" em "tenho backup".
 * Sem ela, criar uma política exigiria chamar a API na mão — e o produto teria
 * um requisito de linha de comando escondido no meio do caminho.
 *
 * Quatro coisas que a tela se recusa a esconder:
 *
 * 1. **"Só nesta máquina" não é backup.** Um pacote no mesmo computador não
 *    protege contra o disco morrer nem contra ransomware. Quando o destino é
 *    esse, a tela diz — e continua deixando salvar, porque é um começo
 *    legítimo. O que não pode é a pessoa achar que está protegida.
 * 2. **"Vai valer" não é "está valendo".** Se a máquina está desligada, a
 *    política sobe na próxima conexão, e a tela diz isso em vez de fingir que
 *    já aplicou.
 * 3. **Origens são as pastas autorizadas na máquina.** Elas vêm do próprio
 *    dispositivo. Nenhuma tela na nuvem concede acesso ao disco de ninguém.
 * 4. **Agendamento desligado é dito como desligado.** "Só executa quando
 *    alguém manda" é uma escolha válida — desde que ninguém a confunda com
 *    backup automático.
 */
export default function Politicas({ papel }: Props) {
  const [politicas, setPoliticas] = useState<Politica[] | null>(null);
  const [dispositivos, setDispositivos] = useState<Dispositivo[]>([]);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [abrindo, setAbrindo] = useState(false);
  // Como em Dispositivos: lista vazia e "ainda nao perguntei" sao coisas
  // diferentes, e so uma delas merece a tela de "nenhuma maquina".
  const [carregado, setCarregado] = useState(false);
  const jaDecidiu = useRef(false);

  const administra = ADMINISTRAM.has(papel);

  const carregar = useCallback(async () => {
    try {
      // As duas listas juntas: uma política sem máquina não existe, e mostrar
      // a lista de políticas antes de saber quais máquinas há faria o nome do
      // dispositivo piscar como "máquina removida".
      const [comPoliticas, comDispositivos] = await Promise.all([
        listarPoliticas(),
        listarDispositivos(),
      ]);
      const maquinas = comDispositivos.dispositivos.filter(
        (item) => item.estado !== "revogado",
      );
      setPoliticas(comPoliticas.politicas);
      setDispositivos(maquinas);
      // Quem chega aqui com maquina e sem nenhuma politica veio configurar —
      // e obriga-lo a clicar em "Configurar backup" para ver o assistente
      // seria cobrar um clique por uma tela vazia. So na PRIMEIRA carga:
      // depois de cancelar, reabrir sozinho seria teimosia.
      setAbrindo((atual) => {
        if (jaDecidiu.current) return atual;
        jaDecidiu.current = true;
        return (
          administra && comPoliticas.politicas.length === 0 && maquinas.length > 0
        );
      });
      setErro("");
    } catch (e: unknown) {
      setErro(mensagemDe(e));
    } finally {
      setCarregado(true);
    }
  }, [administra]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const executarAgora = async (item: Politica) => {
    setAviso(`Executando "${item.nome}"…`);
    try {
      // Manda as MESMAS escolhas da politica. Um "executar agora" que rodasse
      // diferente do horario faria o cliente testar uma coisa e receber outra
      // de madrugada.
      const resultado = await executarBackup(item.dispositivo_id, {
        origens: item.configuracao.origens,
        destino_externo: item.configuracao.destino.caminho,
        tipo_do_destino: item.configuracao.destino.tipo,
        usar_vss: item.configuracao.usar_vss,
        incremental: item.configuracao.incremental,
      });
      setAviso(
        resultado.ok
          ? `Backup concluído: ${resultado.pacote ?? "pacote gerado"}`
          : `Backup não concluído: ${resultado.erro ?? "sem detalhe"}`,
      );
    } catch (e: unknown) {
      setAviso("");
      setErro(mensagemDe(e));
    }
  };

  const apagar = async (id: string) => {
    try {
      const resultado = await removerPolitica(id);
      setAviso(
        resultado.sincronizacao.aplicada
          ? "Política removida e a máquina já foi avisada."
          : `Política removida. ${resultado.sincronizacao.motivo ?? ""}`,
      );
      await carregar();
    } catch (e: unknown) {
      setErro(mensagemDe(e));
    }
  };

  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* "Backups" e a palavra da barra e a palavra do cliente. "Politica" e
            jargao, e aparece adiante em cada botao — entao o subtitulo
            apresenta o termo em vez de supor que ele ja e conhecido. */}
        <div>
          <h2 className="text-lg font-semibold text-fg">Backups</h2>
          <p className="text-[0.8rem] text-muted">
            Cada backup é uma política: o que copiar, para onde e quando.
          </p>
        </div>
        {administra && dispositivos.length > 0 && (
          <button
            type="button"
            onClick={() => setAbrindo((atual) => !atual)}
            className="rounded-lg border border-white/12 px-3 py-1.5 text-sm font-semibold text-fg hover:border-white/25"
          >
            {abrindo ? "Cancelar" : "Configurar backup"}
          </button>
        )}
      </div>

      {carregado && dispositivos.length === 0 && (
        <div className="mt-4 rounded-xl border border-white/10 bg-ink px-4 py-4">
          <p className="text-sm font-semibold text-fg">
            Nenhuma máquina conectada
          </p>
          <p className="mt-1 text-[0.85rem] text-muted">
            O backup roda no computador, e quem executa é o Agente. Antes de
            configurar o que copiar, é preciso ter uma máquina.
          </p>
          {/* Leva ao pareamento CARREGANDO o caminho de volta. Adotar uma
              maquina leva minutos e quase sempre acontece em outro computador;
              sem isso, quem sai daqui volta perdido. */}
          <a
            href={PARA_PAREAR}
            onClick={cliqueDeNavegacao(PARA_PAREAR)}
            className="mt-3 inline-block rounded-lg border border-signal/40 bg-signal/10 px-4 py-2 text-sm font-semibold text-signal hover:border-signal/70"
          >
            Adicionar máquina
          </a>
        </div>
      )}

      {abrindo && administra && (
        <AssistenteDeBackup
          mensagemDe={mensagemDe}
          dispositivos={dispositivos}
          aoSalvar={async (resultado) => {
            setAbrindo(false);
            setAviso(recado(resultado.sincronizacao, resultado.protege_de_verdade));
            await carregar();
          }}
          aoFalhar={(mensagem) => setErro(mensagem)}
        />
      )}

      {erro && (
        <p className="mt-3 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
          {erro}
        </p>
      )}
      {aviso && <p className="mt-3 text-[0.85rem] text-muted">{aviso}</p>}

      {politicas !== null && politicas.length === 0 && !abrindo && (
        <p className="mt-3 text-sm text-muted">
          Nenhuma política ainda. Sem política, o backup só acontece quando
          alguém clica em "Executar backup agora".
        </p>
      )}

      <ul className="mt-3 flex flex-col gap-2">
        {(politicas ?? []).map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-white/10 bg-surface px-4 py-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-fg">{item.nome}</p>
                <p className="text-[0.8rem] text-muted">
                  {resumo(item.configuracao)} ·{" "}
                  {nomeDoDispositivo(dispositivos, item.dispositivo_id)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void executarAgora(item)}
                  className="rounded-lg border border-white/12 px-3 py-1 text-[0.75rem] text-fg hover:border-white/25"
                >
                  Executar agora
                </button>
                {administra && (
                  <button
                    type="button"
                    onClick={() => void apagar(item.id)}
                    className="rounded-lg border border-danger/30 px-3 py-1 text-[0.75rem] text-danger hover:border-danger/60"
                  >
                    Remover
                  </button>
                )}
              </div>
            </div>

            {!item.protege_de_verdade && (
              <p className="mt-2 text-[0.8rem] text-signal">
                O pacote fica só nesta máquina. Isso não protege contra o disco
                morrer nem contra ransomware — escolha um disco externo, uma
                pasta de rede ou a nuvem para ter backup de verdade.
              </p>
            )}
            {item.configuracao.agendamento.tipo === "desligado" && (
              <p className="mt-2 text-[0.8rem] text-signal">
                Sem horário: só executa quando alguém manda.
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function recado(sincronizacao: Sincronizacao, protege: boolean): string {
  const aplicacao = sincronizacao.aplicada
    ? "Política salva e já aplicada na máquina."
    : `Política salva. ${sincronizacao.motivo ?? "a máquina será avisada na próxima conexão"}.`;
  if (protege) return aplicacao;
  return `${aplicacao} Atenção: o pacote fica só na própria máquina, o que não protege contra o disco morrer.`;
}

function resumo(config: ConfiguracaoDePolitica): string {
  const quando: Record<string, string> = {
    desligado: "sem horário",
    diario: `todo dia às ${config.agendamento.hora}`,
    semanal: `toda semana às ${config.agendamento.hora}`,
    mensal: `todo mês às ${config.agendamento.hora}`,
  };
  const destino: Record<string, string> = {
    nenhum: "só nesta máquina",
    local: "outra pasta desta máquina",
    externo: "disco externo",
    rede: "pasta de rede",
    nuvem: "nuvem",
  };
  return `${quando[config.agendamento.tipo] ?? config.agendamento.tipo} · ${
    destino[config.destino.tipo] ?? config.destino.tipo
  }`;
}

function nomeDoDispositivo(dispositivos: Dispositivo[], id: string): string {
  return dispositivos.find((item) => item.id === id)?.nome ?? "máquina removida";
}

function mensagemDe(erro: unknown): string {
  if (erro instanceof ErroDaPlataforma) {
    if (erro.status === 409) {
      return "A máquina está desligada ou sem conexão com o Live.";
    }
    return erro.message;
  }
  return erro instanceof Error ? erro.message : "não foi possível";
}
