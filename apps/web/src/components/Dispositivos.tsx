import { useCallback, useEffect, useState } from "react";

import InstalarAgente from "./InstalarAgente";
import Restauracao from "./Restauracao";

import {
  consultarDispositivo,
  emitirCodigo,
  ErroDaPlataforma,
  executarBackup,
  listarDispositivos,
  listarPresenca,
  revogarDispositivo,
  type CodigoDePareamento,
  type Dispositivo,
  type EstadoDoDispositivo,
} from "../lib/plataforma";

interface Props {
  /** Papel de quem está olhando: só quem administra parea e revoga. */
  papel: string;
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
export default function Dispositivos({ papel }: Props) {
  const [dispositivos, setDispositivos] = useState<Dispositivo[]>([]);
  const [conectados, setConectados] = useState<Record<string, boolean>>({});
  const [codigo, setCodigo] = useState<CodigoDePareamento | null>(null);
  const [estados, setEstados] = useState<Record<string, EstadoDoDispositivo>>({});
  const [avisos, setAvisos] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [restaurando, setRestaurando] = useState("");

  const administra = ADMINISTRAM.has(papel);
  const opera = OPERAM.has(papel);

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
    }
  }, []);

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
    <section className="mx-auto max-w-3xl">
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

      {dispositivos.length === 0 && !erro && (
        <p className="mt-4 text-sm text-muted">
          Nenhuma máquina pareada ainda. O backup de pastas do computador
          depende do Agente instalado e pareado.
        </p>
      )}

      <ul className="mt-4 flex flex-col gap-3">
        {dispositivos.map((item) => {
          const online = conectados[item.id] === true;
          const estado = estados[item.id];
          // Máquina revogada não recebe comando — o servidor recusa. Deixar
          // os botões na tela seria oferecer uma ação que só pode falhar.
          const emServico = item.estado !== "revogado";
          return (
            <li
              key={item.id}
              className="rounded-lg border border-white/10 bg-surface px-4 py-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-fg">{item.nome}</p>
                  <p className="text-[0.8rem] text-muted">
                    {item.sistema || "sistema não informado"} · Agente{" "}
                    {item.versao_agente || "?"} · impressão {item.impressao}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[0.7rem] font-semibold ${corDoEstado(
                    item.estado,
                    online,
                  )}`}
                >
                  {rotuloDeEstado(item.estado, online)}
                </span>
              </div>

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
                {emServico && (
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
