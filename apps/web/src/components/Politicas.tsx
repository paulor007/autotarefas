import { useCallback, useEffect, useState } from "react";

import { cliqueDeNavegacao, comVolta, enderecoDa } from "../lib/rotas";

import {
  ErroDaPlataforma,
  consultarDispositivo,
  criarPolitica,
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

/** O que o formulário começa oferecendo. */
const PADRAO: ConfiguracaoDePolitica = {
  origens: [],
  destino: { tipo: "externo", caminho: "" },
  agendamento: { tipo: "diario", hora: "02:00", dia_da_semana: 0, dia_do_mes: 1 },
  retencao: { diarias: 7, semanais: 4, mensais: 12 },
  retry: { tentativas: 3, espera_inicial_min: 5 },
  notificacao: { quando: "problema", emails: [] },
  usar_vss: false,
  cifrar: false,
  assinar: true,
  verificar: true,
  incremental: false,
};

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
      setPoliticas(comPoliticas.politicas);
      setDispositivos(comDispositivos.dispositivos.filter((item) => item.estado !== "revogado"));
      setErro("");
    } catch (e: unknown) {
      setErro(mensagemDe(e));
    } finally {
      setCarregado(true);
    }
  }, []);

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
        <h2 className="text-lg font-semibold text-fg">Políticas de backup</h2>
        {administra && dispositivos.length > 0 && (
          <button
            type="button"
            onClick={() => setAbrindo((atual) => !atual)}
            className="rounded-lg border border-white/12 px-3 py-1.5 text-sm font-semibold text-fg hover:border-white/25"
          >
            {abrindo ? "Cancelar" : "Nova política"}
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

      {abrindo && (
        <Formulario
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

interface PropsDoFormulario {
  dispositivos: Dispositivo[];
  aoSalvar: (resultado: Politica & { sincronizacao: Sincronizacao }) => Promise<void>;
  aoFalhar: (mensagem: string) => void;
}

/** O formulário. Um campo por decisão, com o padrão já preenchido. */
function Formulario({ dispositivos, aoSalvar, aoFalhar }: PropsDoFormulario) {
  const [nome, setNome] = useState("Backup diário");
  const [dispositivoId, setDispositivoId] = useState(dispositivos[0]?.id ?? "");
  const [raizes, setRaizes] = useState<string[]>([]);
  const [origens, setOrigens] = useState<string[]>([]);
  const [config, setConfig] = useState<ConfiguracaoDePolitica>(PADRAO);
  const [salvando, setSalvando] = useState(false);
  const [semRaizes, setSemRaizes] = useState("");

  useEffect(() => {
    if (!dispositivoId) return;
    setSemRaizes("");
    consultarDispositivo(dispositivoId)
      .then((resposta) => {
        const autorizadas = resposta.estado.raizes ?? [];
        setRaizes(autorizadas);
        setOrigens(autorizadas);
        if (autorizadas.length === 0) {
          setSemRaizes(
            "Esta máquina não tem pasta autorizada: a política não copiaria nada. A autorização é dada no próprio computador, pelo Agente.",
          );
        }
      })
      .catch((e: unknown) => setSemRaizes(mensagemDe(e)));
  }, [dispositivoId]);

  const salvar = async () => {
    setSalvando(true);
    try {
      const resultado = await criarPolitica({
        nome,
        dispositivo_id: dispositivoId,
        configuracao: { ...config, origens },
      });
      await aoSalvar(resultado);
    } catch (e: unknown) {
      aoFalhar(mensagemDe(e));
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-white/12 bg-bg/40 px-4 py-3">
      <div className="flex flex-col gap-3 text-[0.85rem]">
        <label className="flex flex-col gap-1">
          <span className="text-muted">Nome</span>
          <input
            aria-label="Nome da política"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-muted">Máquina</span>
          <select
            aria-label="Máquina"
            value={dispositivoId}
            onChange={(e) => setDispositivoId(e.target.value)}
            className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
          >
            {dispositivos.map((item) => (
              <option key={item.id} value={item.id}>
                {item.nome}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="flex flex-col gap-1">
          <legend className="text-muted">Pastas a copiar</legend>
          {semRaizes && <p className="text-[0.8rem] text-danger">{semRaizes}</p>}
          {raizes.map((raiz) => (
            <label key={raiz} className="flex items-center gap-2 font-mono text-[0.8rem]">
              <input
                type="checkbox"
                checked={origens.includes(raiz)}
                onChange={(e) =>
                  setOrigens((atual) =>
                    e.target.checked
                      ? [...atual, raiz]
                      : atual.filter((item) => item !== raiz),
                  )
                }
              />
              <span className="text-fg">{raiz}</span>
            </label>
          ))}
        </fieldset>

        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-muted">Destino</span>
            <select
              aria-label="Tipo de destino"
              value={config.destino.tipo}
              onChange={(e) =>
                setConfig({ ...config, destino: { ...config.destino, tipo: e.target.value } })
              }
              className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
            >
              <option value="externo">Disco externo</option>
              <option value="rede">Pasta de rede</option>
              <option value="nuvem">Nuvem compatível com S3</option>
              <option value="local">Outra pasta desta máquina</option>
              <option value="nenhum">Só nesta máquina</option>
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1">
            <span className="text-muted">Caminho do destino</span>
            <input
              aria-label="Caminho do destino"
              value={config.destino.caminho}
              placeholder="E:\\Backups  ou  \\\\servidor\\backups"
              onChange={(e) =>
                setConfig({
                  ...config,
                  destino: { ...config.destino, caminho: e.target.value },
                })
              }
              className="rounded-lg border border-white/12 bg-surface px-2 py-1 font-mono text-fg"
            />
          </label>
        </div>

        {config.destino.tipo === "nenhum" && (
          <p className="text-[0.8rem] text-signal">
            O pacote fica só nesta máquina. Isso não protege contra o disco
            morrer nem contra ransomware.
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-muted">Quando</span>
            <select
              aria-label="Frequência"
              value={config.agendamento.tipo}
              onChange={(e) =>
                setConfig({
                  ...config,
                  agendamento: { ...config.agendamento, tipo: e.target.value },
                })
              }
              className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
            >
              <option value="diario">Todo dia</option>
              <option value="semanal">Toda semana</option>
              <option value="mensal">Todo mês</option>
              <option value="desligado">Só quando eu mandar</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-muted">Hora</span>
            <input
              aria-label="Hora"
              value={config.agendamento.hora}
              onChange={(e) =>
                setConfig({
                  ...config,
                  agendamento: { ...config.agendamento, hora: e.target.value },
                })
              }
              className="w-24 rounded-lg border border-white/12 bg-surface px-2 py-1 font-mono text-fg"
            />
          </label>
        </div>

        <fieldset className="flex flex-wrap gap-3">
          <legend className="text-muted">Guardar por quanto tempo</legend>
          <Numero
            rotulo="Diários"
            valor={config.retencao.diarias}
            aoMudar={(v) => setConfig({ ...config, retencao: { ...config.retencao, diarias: v } })}
          />
          <Numero
            rotulo="Semanais"
            valor={config.retencao.semanais}
            aoMudar={(v) => setConfig({ ...config, retencao: { ...config.retencao, semanais: v } })}
          />
          <Numero
            rotulo="Mensais"
            valor={config.retencao.mensais}
            aoMudar={(v) => setConfig({ ...config, retencao: { ...config.retencao, mensais: v } })}
          />
        </fieldset>

        <fieldset className="flex flex-wrap gap-3">
          <legend className="text-muted">Se falhar</legend>
          <Numero
            rotulo="Tentativas"
            valor={config.retry.tentativas}
            aoMudar={(v) => setConfig({ ...config, retry: { ...config.retry, tentativas: v } })}
          />
          <Numero
            rotulo="Espera inicial (min)"
            valor={config.retry.espera_inicial_min}
            aoMudar={(v) =>
              setConfig({ ...config, retry: { ...config.retry, espera_inicial_min: v } })
            }
          />
        </fieldset>

        <label className="flex flex-col gap-1">
          <span className="text-muted">Avisar por e-mail</span>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Quando avisar"
              value={config.notificacao.quando}
              onChange={(e) =>
                setConfig({
                  ...config,
                  notificacao: { ...config.notificacao, quando: e.target.value },
                })
              }
              className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
            >
              <option value="problema">Só quando houver problema</option>
              <option value="sempre">Sempre</option>
              <option value="nunca">Nunca</option>
            </select>
            <input
              aria-label="E-mails para aviso"
              placeholder="voce@empresa.com.br"
              value={config.notificacao.emails.join(", ")}
              onChange={(e) =>
                setConfig({
                  ...config,
                  notificacao: {
                    ...config.notificacao,
                    emails: e.target.value
                      .split(",")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  },
                })
              }
              className="flex-1 rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
            />
          </div>
        </label>

        <fieldset className="flex flex-col gap-1">
          <legend className="text-muted">Como copiar</legend>
          <Marcador
            rotulo="Copiar só o que mudou (incremental)"
            valor={config.incremental}
            aoMudar={(v) => setConfig({ ...config, incremental: v })}
          />
          <Marcador
            rotulo="Proteger o pacote com senha (AES-256)"
            valor={config.cifrar}
            aoMudar={(v) => setConfig({ ...config, cifrar: v })}
          />
          <Marcador
            rotulo="Assinar o manifesto, para detectar adulteração"
            valor={config.assinar}
            aoMudar={(v) => setConfig({ ...config, assinar: v })}
          />
          <Marcador
            rotulo="Conferir o pacote depois de gerar"
            valor={config.verificar}
            aoMudar={(v) => setConfig({ ...config, verificar: v })}
          />
          <Marcador
            rotulo="Copiar arquivo aberto usando instantâneo (VSS, exige administrador)"
            valor={config.usar_vss}
            aoMudar={(v) => setConfig({ ...config, usar_vss: v })}
          />
        </fieldset>

        <button
          type="button"
          onClick={() => void salvar()}
          disabled={salvando || !dispositivoId || origens.length === 0}
          className="self-start rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] font-semibold text-fg hover:border-white/25 disabled:opacity-50"
        >
          {salvando ? "Salvando…" : "Salvar política"}
        </button>
      </div>
    </div>
  );
}

function Numero({
  rotulo,
  valor,
  aoMudar,
}: {
  rotulo: string;
  valor: number;
  aoMudar: (valor: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-muted">{rotulo}</span>
      <input
        type="number"
        aria-label={rotulo}
        value={valor}
        min={0}
        onChange={(e) => aoMudar(Number(e.target.value))}
        className="w-24 rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
      />
    </label>
  );
}

function Marcador({
  rotulo,
  valor,
  aoMudar,
}: {
  rotulo: string;
  valor: boolean;
  aoMudar: (valor: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-[0.8rem] text-muted">
      <input type="checkbox" checked={valor} onChange={(e) => aoMudar(e.target.checked)} />
      <span>{rotulo}</span>
    </label>
  );
}

/**
 * O recado depois de salvar.
 *
 * Junta as duas coisas que a pessoa precisa saber e que são fáceis de supor
 * errado: se a política já chegou à máquina, e se o destino escolhido protege
 * de alguma coisa.
 */
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
