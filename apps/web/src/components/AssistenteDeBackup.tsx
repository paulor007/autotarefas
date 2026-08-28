import { useEffect, useState } from "react";

import {
  consultarDispositivo,
  criarPolitica,
  type ConfiguracaoDePolitica,
  type Dispositivo,
  type Politica,
  type Sincronizacao,
} from "../lib/plataforma";

/** O que o assistente começa oferecendo. */
export const PADRAO: ConfiguracaoDePolitica = {
  origens: [],
  destino: { tipo: "externo", caminho: "" },
  agendamento: {
    tipo: "diario",
    hora: "02:00",
    dia_da_semana: 0,
    dia_do_mes: 1,
  },
  retencao: { diarias: 7, semanais: 4, mensais: 12 },
  retry: { tentativas: 3, espera_inicial_min: 5 },
  notificacao: { quando: "problema", emails: [] },
  usar_vss: false,
  cifrar: false,
  assinar: true,
  verificar: true,
  incremental: false,
};

const DESTINOS: Record<string, string> = {
  externo: "um disco externo",
  rede: "uma pasta de rede",
  nuvem: "a nuvem",
  local: "outra pasta da mesma máquina",
  nenhum: "a própria máquina",
};

const QUANDO: Record<string, string> = {
  diario: "todo dia",
  semanal: "toda semana",
  mensal: "todo mês",
  desligado: "só quando alguém mandar",
};

interface Props {
  dispositivos: Dispositivo[];
  aoSalvar: (
    resultado: Politica & { sincronizacao: Sincronizacao },
  ) => Promise<void>;
  aoFalhar: (mensagem: string) => void;
  mensagemDe: (erro: unknown) => string;
}

/**
 * Configurar um backup, em seis decisões numeradas.
 *
 * Era um formulário corrido de vinte campos, todos com o mesmo peso: o nome da
 * política ao lado do VSS, a hora ao lado da assinatura do manifesto. Quem
 * abria não sabia quais escolhas mudavam alguma coisa.
 *
 * Duas escolhas de desenho, e os motivos:
 *
 * **Seis passos numa tela só, e não seis telas.** Quatro dos seis passos são
 * um clique cada — a máquina costuma ser uma, e as pastas já vêm marcadas.
 * Um assistente de seis telas cobraria seis cliques para mostrar o que cabe
 * numa, e tiraria da vista o conjunto das escolhas justamente na hora de
 * revisá-las.
 *
 * **O que é raro fica atrás de "Configurações avançadas".** Retry, aviso por
 * e-mail, incremental, cifra, assinatura e VSS têm padrão sensato e quase
 * ninguém muda. Mostrá-los sempre faz a tela parecer difícil e esconde as
 * quatro decisões que importam.
 *
 * O passo 6 não é um campo: é a frase do que vai acontecer, em português, para
 * ser lida antes de ativar.
 */
export default function AssistenteDeBackup({
  dispositivos,
  aoSalvar,
  aoFalhar,
  mensagemDe,
}: Props) {
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
  }, [dispositivoId, mensagemDe]);

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

  const maquina =
    dispositivos.find((item) => item.id === dispositivoId)?.nome ?? "a máquina";
  const pronto = Boolean(dispositivoId) && origens.length > 0;

  return (
    <div className="mt-4 rounded-xl border border-white/12 bg-ink px-5 py-4">
      <div className="flex flex-col gap-6 text-[0.85rem]">
        <Passo numero={1} titulo="Máquina">
          <label className="flex flex-col gap-1">
            <span className="text-muted">Qual computador será protegido</span>
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
          <label className="flex flex-col gap-1">
            <span className="text-muted">Como chamar este backup</span>
            <input
              aria-label="Nome da política"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-fg"
            />
          </label>
        </Passo>

        <Passo numero={2} titulo="O que proteger">
          <fieldset className="flex flex-col gap-1">
            <legend className="sr-only">Pastas a copiar</legend>
            {semRaizes ? (
              <p className="text-[0.8rem] text-danger">{semRaizes}</p>
            ) : (
              <p className="text-muted">
                As pastas que o Agente foi autorizado a ler, no próprio
                computador. Nenhuma tela aqui concede acesso a disco.
              </p>
            )}
            {raizes.map((raiz) => (
              <label
                key={raiz}
                className="flex items-center gap-2 font-mono text-[0.8rem]"
              >
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
        </Passo>

        <Passo numero={3} titulo="Destino">
          <div className="flex flex-wrap gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-muted">Para onde vai a cópia</span>
              <select
                aria-label="Tipo de destino"
                value={config.destino.tipo}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    destino: { ...config.destino, tipo: e.target.value },
                  })
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
                placeholder="E:\Backups  ou  \\servidor\backups"
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
          {(config.destino.tipo === "nenhum" ||
            config.destino.tipo === "local") && (
            <p className="text-[0.8rem] text-signal">
              O pacote fica no mesmo computador. Isso não protege contra o disco
              morrer nem contra ransomware.
            </p>
          )}
        </Passo>

        <Passo numero={4} titulo="Quando">
          <div className="flex flex-wrap gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-muted">Com que frequência</span>
              <select
                aria-label="Frequência"
                value={config.agendamento.tipo}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    agendamento: {
                      ...config.agendamento,
                      tipo: e.target.value,
                    },
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
              <span className="text-muted">A que horas</span>
              <input
                aria-label="Hora"
                value={config.agendamento.hora}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    agendamento: {
                      ...config.agendamento,
                      hora: e.target.value,
                    },
                  })
                }
                className="w-24 rounded-lg border border-white/12 bg-surface px-2 py-1 font-mono text-fg"
              />
            </label>
          </div>
          {config.agendamento.tipo === "desligado" && (
            <p className="text-[0.8rem] text-signal">
              Sem horário não há backup automático: só executa quando alguém
              clicar.
            </p>
          )}
        </Passo>

        <Passo numero={5} titulo="Quanto guardar">
          <fieldset className="flex flex-wrap gap-3">
            <legend className="mb-1 text-muted">
              Quantas cópias antigas manter antes de apagar as mais velhas
            </legend>
            <Numero
              rotulo="Diários"
              valor={config.retencao.diarias}
              aoMudar={(v) =>
                setConfig({
                  ...config,
                  retencao: { ...config.retencao, diarias: v },
                })
              }
            />
            <Numero
              rotulo="Semanais"
              valor={config.retencao.semanais}
              aoMudar={(v) =>
                setConfig({
                  ...config,
                  retencao: { ...config.retencao, semanais: v },
                })
              }
            />
            <Numero
              rotulo="Mensais"
              valor={config.retencao.mensais}
              aoMudar={(v) =>
                setConfig({
                  ...config,
                  retencao: { ...config.retencao, mensais: v },
                })
              }
            />
          </fieldset>
        </Passo>

        <details className="rounded-lg border border-white/10 px-3 py-2">
          <summary className="cursor-pointer text-muted">
            Configurações avançadas
          </summary>
          <div className="mt-3 flex flex-col gap-4">
            <fieldset className="flex flex-wrap gap-3">
              <legend className="mb-1 text-muted">Se falhar</legend>
              <Numero
                rotulo="Tentativas"
                valor={config.retry.tentativas}
                aoMudar={(v) =>
                  setConfig({
                    ...config,
                    retry: { ...config.retry, tentativas: v },
                  })
                }
              />
              <Numero
                rotulo="Espera inicial (min)"
                valor={config.retry.espera_inicial_min}
                aoMudar={(v) =>
                  setConfig({
                    ...config,
                    retry: { ...config.retry, espera_inicial_min: v },
                  })
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
                      notificacao: {
                        ...config.notificacao,
                        quando: e.target.value,
                      },
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
              <legend className="mb-1 text-muted">Como copiar</legend>
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
          </div>
        </details>

        <Passo numero={6} titulo="Ativar">
          {/* A frase existe para ser lida antes do clique. Uma tela que só
              mostra campos deixa a pessoa ativar sem nunca ter visto, junto,
              o que combinou. */}
          {/* `status`: a frase muda a cada escolha, e quem usa leitor de tela
              precisa ouvir a mudanca sem sair do campo onde esta. */}
          <p role="status" className="text-fg">
            {pronto ? (
              <>
                Copiar{" "}
                <strong>
                  {origens.length === 1
                    ? "1 pasta"
                    : `${origens.length} pastas`}
                </strong>{" "}
                de <strong>{maquina}</strong> para{" "}
                <strong>{DESTINOS[config.destino.tipo]}</strong>,{" "}
                <strong>
                  {QUANDO[config.agendamento.tipo]}
                  {config.agendamento.tipo !== "desligado" &&
                    ` às ${config.agendamento.hora}`}
                </strong>
                , guardando {config.retencao.diarias} diários,{" "}
                {config.retencao.semanais} semanais e {config.retencao.mensais}{" "}
                mensais.
              </>
            ) : (
              <span className="text-muted">
                Escolha ao menos uma pasta para continuar.
              </span>
            )}
          </p>
          <button
            type="button"
            onClick={() => void salvar()}
            disabled={salvando || !pronto}
            className="self-start rounded-lg border border-signal/40 bg-signal/10 px-4 py-2 text-sm font-semibold text-signal hover:border-signal/70 disabled:opacity-40"
          >
            {salvando ? "Ativando…" : "Ativar backup"}
          </button>
        </Passo>
      </div>
    </div>
  );
}

function Passo({
  numero,
  titulo,
  children,
}: {
  numero: number;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex gap-3">
      <span
        aria-hidden
        className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/15 text-[0.75rem] font-semibold text-muted"
      >
        {numero}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h4 className="text-[0.95rem] font-semibold text-fg">{titulo}</h4>
        {children}
      </div>
    </section>
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
        aria-label={rotulo}
        type="number"
        min={0}
        value={valor}
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
    <label className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={valor}
        onChange={(e) => aoMudar(e.target.checked)}
      />
      <span className="text-fg">{rotulo}</span>
    </label>
  );
}
