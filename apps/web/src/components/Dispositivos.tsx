import { useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";

import InstalarAgente from "./InstalarAgente";
import Restauracao from "./Restauracao";

import { desdeQuando, quando as formatarData } from "../lib/datas";
import {
  consultarDispositivo,
  emitirCodigo,
  ErroDaPlataforma,
  executarBackup,
  listarDispositivos,
  listarHistorico,
  listarPoliticas,
  listarPresenca,
  obterAoVivo,
  revogarDispositivo,
  type CodigoDePareamento,
  type Dispositivo,
  type EstadoDoDispositivo,
  type Execucao,
  type Politica,
  type ProximaExecucao,
} from "../lib/plataforma";
import {
  cliqueDeNavegacao,
  destinoDeVolta,
  useCaminho,
} from "../lib/rotas";

interface Props {
  /** Papel de quem está olhando: só quem administra parea e revoga. */
  papel: string;
  /**
   * Sessão do ambiente público: o servidor recusa qualquer escrita.
   *
   * "Ver pastas autorizadas" parece leitura e não é: a rota é `POST`, porque
   * manda um comando pelo canal até o computador. Nesta sessão ela responde
   * 403 — então o botão sai, em vez de existir só para falhar.
   */
  somenteLeitura?: boolean;
}

const ADMINISTRAM = new Set(["dono", "administrador"]);
const OPERAM = new Set(["dono", "administrador", "operador"]);

/** Quanto tempo entre uma leitura de presença e a seguinte. */
const INTERVALO_PRESENCA_MS = 10_000;

/**
 * Máquinas desta organização: parear, ver quem está no ar, executar e revogar.
 *
 * Duas regras de honestidade governam esta tela:
 *
 * 1. **"Conectado" vem da presença, não do cadastro.** Um dispositivo
 *    cadastrado e desligado aparece como desligado. Mostrar "ativo" só porque
 *    existe uma linha no banco faria alguém confiar num backup que não vai
 *    acontecer.
 * 2. **Máquina desligada não é erro.** O servidor responde 409 nesse caso, e a
 *    tela diz "está desligada". Tratar como falha faria a tela acusar problema
 *    toda noite, quando o computador da loja está simplesmente fechado.
 *
 * Autorizar pasta **não** acontece aqui, e isso é proposital: o consentimento é
 * dado na própria máquina. A tela mostra o que foi autorizado e diz onde
 * autorizar mais.
 */
export default function Dispositivos({ papel, somenteLeitura = false }: Props) {
  const [dispositivos, setDispositivos] = useState<Dispositivo[]>([]);
  // Lista vazia e "ainda nao perguntei" nao sao a mesma coisa. Sem esta
  // marca, a tela afirmava "Nenhuma maquina pareada ainda" no intervalo
  // entre abrir e o servidor responder — uma frase falsa, curta, na cara de
  // quem tem maquina pareada.
  const [carregado, setCarregado] = useState(false);
  const [conectados, setConectados] = useState<Record<string, boolean>>({});
  const [codigo, setCodigo] = useState<CodigoDePareamento | null>(null);
  const [estados, setEstados] = useState<Record<string, EstadoDoDispositivo>>({});
  const [avisos, setAvisos] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [restaurando, setRestaurando] = useState("");
  // O que cada maquina esta fazendo, para o cartao dizer mais do que
  // "conectado". Vem de rotas que a tela ja consome noutros lugares — nao ha
  // pergunta nova para a maquina do cliente.
  const [politicas, setPoliticas] = useState<Politica[]>([]);
  const [execucoes, setExecucoes] = useState<Execucao[]>([]);
  const [proximas, setProximas] = useState<ProximaExecucao[]>([]);

  // De onde a pessoa veio, quando veio de algum lugar. Parear e um desvio:
  // comeca numa configuracao, passa por outro computador e precisa terminar
  // onde comecou.
  const voltar = destinoDeVolta(useCaminho());

  const administra = ADMINISTRAM.has(papel) && !somenteLeitura;
  const opera = OPERAM.has(papel) && !somenteLeitura;

  const carregar = useCallback(async () => {
    try {
      const [lista, presenca] = await Promise.all([
        listarDispositivos(),
        listarPresenca(),
      ]);
      setDispositivos(lista.dispositivos);
      setConectados(
        Object.fromEntries(
          presenca.conectados.map((item) => [item.dispositivo_id, item.conectado]),
        ),
      );
      setErro(null);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível carregar");
    } finally {
      setCarregado(true);
    }
  }, []);

  /**
   * O que cada maquina esta fazendo — melhor esforco, de proposito.
   *
   * A afirmacao principal deste cartao e "existe uma maquina, e o Agente dela
   * esta conectado". Ela vem de `carregar`, e uma falha ali e erro de
   * verdade. O resto — quantos backups, qual foi o ultimo, quando e o
   * proximo — enriquece o cartao, e nao pode derruba-lo: uma rota acessoria
   * fora do ar apagaria da tela a maquina que esta ali, funcionando.
   */
  const enriquecer = useCallback(async () => {
    try {
      const [comPoliticas, historico, aoVivo] = await Promise.all([
        listarPoliticas(),
        listarHistorico(),
        obterAoVivo(),
      ]);
      setPoliticas(comPoliticas.politicas ?? []);
      setExecucoes(historico.execucoes ?? []);
      setProximas(aoVivo.proximas ?? []);
    } catch {
      // Sem ruido: o cartao continua dizendo o que sabe.
    }
  }, []);

  useEffect(() => {
    void enriquecer();
  }, [enriquecer]);

  useEffect(() => {
    void carregar();
    // A presença muda sozinha — a máquina cai, volta, é desligada à noite. Sem
    // recarregar, a tela mostraria um retrato do momento em que foi aberta.
    const relogio = setInterval(() => void carregar(), INTERVALO_PRESENCA_MS);
    return () => clearInterval(relogio);
  }, [carregar]);

  const gerarCodigo = async () => {
    setOcupado(true);
    try {
      setCodigo(await emitirCodigo());
      setErro(null);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível gerar o código");
    } finally {
      setOcupado(false);
    }
  };

  const consultar = async (id: string) => {
    setAvisos((atual) => ({ ...atual, [id]: "" }));
    try {
      const resposta = await consultarDispositivo(id);
      setEstados((atual) => ({ ...atual, [id]: resposta.estado }));
    } catch (e: unknown) {
      setAvisos((atual) => ({ ...atual, [id]: mensagemDe(e) }));
    }
  };

  const executar = async (id: string) => {
    setAvisos((atual) => ({ ...atual, [id]: "Executando…" }));
    try {
      const resultado = await executarBackup(id);
      setAvisos((atual) => ({
        ...atual,
        [id]: resultado.ok
          ? `Backup concluído: ${resultado.pacote ?? "pacote gerado"}`
          : `Backup não concluído: ${resultado.erro ?? "sem detalhe"}`,
      }));
    } catch (e: unknown) {
      setAvisos((atual) => ({ ...atual, [id]: mensagemDe(e) }));
    }
  };

  const revogar = async (id: string) => {
    try {
      await revogarDispositivo(id);
      await carregar();
    } catch (e: unknown) {
      setAvisos((atual) => ({ ...atual, [id]: mensagemDe(e) }));
    }
  };

  return (
    <section>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-fg">Dispositivos</h2>
        {administra && (
          <button
            type="button"
            onClick={() => void gerarCodigo()}
            disabled={ocupado}
            className="rounded-lg border border-white/12 px-3 py-1.5 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
          >
            Parear nova máquina
          </button>
        )}
      </div>

      {codigo && <InstalarAgente codigo={codigo} />}

      {erro && (
        <p className="mt-3 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
          {erro}
        </p>
      )}

      {voltar && (
        <a
          href={voltar}
          onClick={cliqueDeNavegacao(voltar)}
          className="mt-4 flex items-center gap-2 rounded-xl border border-signal/30 bg-signal/5 px-4 py-3 text-sm text-fg hover:border-signal/60"
        >
          <ArrowLeft className="h-4 w-4 shrink-0 text-signal" />
          <span>
            {dispositivos.length > 0 ? (
              <>
                <strong className="font-semibold">
                  {dispositivos.length === 1
                    ? "1 máquina pronta."
                    : `${dispositivos.length} máquinas prontas.`}
                </strong>{" "}
                Voltar para a configuração do backup
              </>
            ) : (
              <>
                Você estava configurando um backup. Assim que a máquina
                aparecer aqui, volte para terminar.
              </>
            )}
          </span>
        </a>
      )}

      {!carregado && !erro && (
        <p className="mt-4 text-sm text-muted">Carregando…</p>
      )}

      {carregado && dispositivos.length === 0 && !erro && (
        <p className="mt-4 text-sm text-muted">
          Nenhuma máquina pareada ainda. O backup de pastas do computador
          depende do Agente instalado e pareado.
        </p>
      )}

      {somenteLeitura && dispositivos.length > 0 && (
        <p className="mt-4 text-[0.8rem] text-muted">
          Esta máquina pertence ao ambiente do projeto e roda os backups no
          horário. Ela foi pareada pelo mesmo código temporário que qualquer
          cliente usaria, e autorizou as pastas no próprio computador — nenhuma
          tela concede acesso a disco.
        </p>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {dispositivos.map((item) => {
          const online = conectados[item.id] === true;
          const estado = estados[item.id];
          const daMaquina = politicas.filter(
            (politica) => politica.dispositivo_id === item.id && politica.ativa,
          );
          const ultima = execucoes.find(
            (execucao) => execucao.dispositivo_id === item.id,
          );
          const proxima = proximas.find(
            (agendada) =>
              agendada.maquina === item.nome &&
              agendada.proxima_no_relogio_da_maquina,
          );
          const proximaDaMaquina = proxima
            ? `${formatarData(proxima.proxima_no_relogio_da_maquina)} · ${proxima.nome}`
            : "sem horário marcado";
          // Máquina revogada não recebe comando — o servidor recusa. Deixar
          // os botões na tela seria oferecer uma ação que só pode falhar.
          const emServico = item.estado !== "revogado";
          return (
            <li
              key={item.id}
              className="rounded-lg border border-white/10 bg-surface px-4 py-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-fg">{item.nome}</p>
                <span
                  className={`rounded-full px-2 py-0.5 text-[0.7rem] font-semibold ${corDoEstado(
                    item.estado,
                    online,
                  )}`}
                >
                  {rotuloDeEstado(item.estado, online)}
                </span>
              </div>

              {/* Antes o cartao dizia "Windows 11 · Agente 0.1.0 · impressao
                  AAAA-..." numa linha so, e parava ai. Quem chega precisa
                  entender quatro coisas em sequencia: existe uma maquina,
                  existe um Agente, ele esta conectado, e as automacoes estao
                  acontecendo. As tres ultimas nao estavam na tela.

                  Nada aqui e pergunta nova a maquina do cliente: sao as
                  mesmas rotas que Backups e Atividade ja consomem. */}
              <dl className="mt-3 grid gap-x-6 gap-y-2 text-[0.8rem] sm:grid-cols-3">
                <Dado rotulo="Sistema" valor={item.sistema || "não informado"} />
                <Dado
                  rotulo="Agente"
                  valor={item.versao_agente ? `v${item.versao_agente}` : "?"}
                />
                {/* Relativo, e nao absoluto: a pergunta ali e "isto esta
                    vivo agora?", e uma data obriga quem le a fazer a conta com
                    o relogio para responde-la. */}
                <Dado
                  rotulo="Último contato"
                  valor={desdeQuando(item.ultimo_contato)}
                />
                <Dado rotulo="Backups ativos" valor={String(daMaquina.length)} />
                <Dado
                  rotulo="Último backup"
                  valor={
                    ultima
                      ? `${formatarData(ultima.terminada_em || ultima.iniciada_em)} · ${rotuloDoResultado(ultima.resultado)}`
                      : "nenhum ainda"
                  }
                />
                <Dado rotulo="Próxima execução" valor={proximaDaMaquina} />
              </dl>

              {estado?.ok && (
                <div className="mt-2 text-[0.85rem] text-muted">
                  {estado.pode_copiar ? (
                    <>
                      <p>Pastas autorizadas nesta máquina:</p>
                      <ul className="mt-1 list-inside list-disc font-mono text-[0.8rem]">
                        {(estado.raizes ?? []).map((raiz) => (
                          <li key={raiz}>{raiz}</li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="text-danger">
                      Nenhuma pasta autorizada: este dispositivo não copiaria
                      nada. A autorização é dada no próprio computador, pelo
                      Agente.
                    </p>
                  )}
                </div>
              )}

              {!emServico && (
                <p className="mt-2 text-[0.85rem] text-danger">
                  Esta máquina foi revogada: ela não recebe mais comando, e o
                  backup dela parou. O histórico continua aqui. Para voltar a
                  usar, pareie de novo — o pareamento antigo não volta.
                </p>
              )}

              {avisos[item.id] && (
                <p className="mt-2 text-[0.85rem] text-muted">{avisos[item.id]}</p>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                {emServico && !somenteLeitura && (
                  <button
                    type="button"
                    onClick={() => void consultar(item.id)}
                    className="rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] text-fg hover:border-white/25"
                  >
                    Ver pastas autorizadas
                  </button>
                )}
                {opera && emServico && (
                  <button
                    type="button"
                    onClick={() => void executar(item.id)}
                    className="rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] text-fg hover:border-white/25"
                  >
                    Executar backup agora
                  </button>
                )}
                {opera && emServico && (
                  <button
                    type="button"
                    onClick={() =>
                      setRestaurando((atual) => (atual === item.id ? "" : item.id))
                    }
                    className="rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] text-fg hover:border-white/25"
                  >
                    Restaurar arquivos
                  </button>
                )}
                {administra && item.estado !== "revogado" && (
                  <button
                    type="button"
                    onClick={() => void revogar(item.id)}
                    className="rounded-lg border border-danger/30 px-3 py-1.5 text-[0.8rem] text-danger hover:border-danger/60"
                  >
                    Revogar
                  </button>
                )}
              </div>

              {restaurando === item.id && (
                <Restauracao
                  dispositivoId={item.id}
                  nomeDoDispositivo={item.nome}
                  aoFechar={() => setRestaurando("")}
                />
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * O que dizer sobre o estado de uma máquina.
 *
 * "Revogado" ganha do resto: um dispositivo revogado que por acaso ainda
 * aparecesse conectado não pode ser mostrado como se estivesse em serviço.
 */
function rotuloDeEstado(estado: Dispositivo["estado"], online: boolean): string {
  if (estado === "revogado") return "Revogado";
  if (estado === "suspenso") return "Suspenso";
  return online ? "Conectado" : "Desligado";
}

/**
 * A cor segue o ESTADO, e não a presença.
 *
 * Pintar pela presença deixava um dispositivo revogado com crachá verde: a cor
 * dizia "em serviço" enquanto a palavra dizia "revogado", e a cor é o que se lê
 * primeiro.
 */
function corDoEstado(estado: Dispositivo["estado"], online: boolean): string {
  if (estado === "revogado") return "bg-danger/15 text-danger";
  if (estado === "suspenso") return "bg-signal/15 text-signal";
  return online ? "bg-ok/15 text-ok" : "bg-white/5 text-muted";
}

/**
 * Traduz o erro sem apagar a diferença entre "não dá" e "quebrou".
 *
 * 409 é a máquina desligada — situação normal. 504 é a máquina no ar que não
 * respondeu, que é outra conversa.
 */
function mensagemDe(erro: unknown): string {
  if (erro instanceof ErroDaPlataforma) {
    if (erro.status === 409) {
      return "A máquina está desligada ou sem conexão com o Live.";
    }
    if (erro.status === 504) {
      return "A máquina está conectada mas não respondeu a tempo.";
    }
    return erro.message;
  }
  return erro instanceof Error ? erro.message : "não foi possível";
}


/** Um par rótulo/valor do cartão da máquina. */
function Dado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt className="text-[0.7rem] uppercase tracking-wide text-muted">
        {rotulo}
      </dt>
      <dd className="mt-0.5 text-fg">{valor}</dd>
    </div>
  );
}

const RESULTADOS: Record<string, string> = {
  sucesso: "Concluído",
  com_ressalva: "Concluído com ressalva",
  falha: "Falhou",
  em_andamento: "Em andamento",
  cancelada: "Cancelada",
};

/**
 * "Com ressalva" não vira "Concluído".
 *
 * Um backup que copiou quase tudo tem ausências, e quem um dia for restaurar
 * precisa saber disso antes — e não no dia.
 */
function rotuloDoResultado(resultado: string): string {
  return RESULTADOS[resultado] ?? resultado;
}
