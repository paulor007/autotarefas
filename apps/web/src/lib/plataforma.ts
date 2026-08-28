/**
 * Chamadas da plataforma: identidade, dispositivos e execução pelo Agente.
 *
 * Separado de `api.ts` de propósito. Aquele atende o Live aberto — catálogo,
 * upload avulso, execução em espaço isolado. Este atende a parte que exige
 * organização, sessão e dispositivo pareado. Misturar os dois faria a tela do
 * visitante carregar código que só serve para quem tem conta.
 *
 * Nenhuma função aqui inventa capacidade. Quando o servidor diz que não há
 * provedor de identidade configurado, ou que o dispositivo está desligado, a
 * resposta chega inteira para a tela decidir o que mostrar — em vez de virar
 * um erro genérico que esconde a diferença entre "não dá" e "quebrou".
 */

/** Quem está logado, e por qual organização. */
export interface EstadoDeSessao {
  autenticado: boolean;
  /** Há provedor OIDC configurado neste servidor? */
  provedor_configurado: boolean;
  /** O banco está vazio: ainda não existe organização nenhuma. */
  precisa_bootstrap: boolean;
  usuario: { id: string; nome: string; email: string } | null;
  organizacao: { id: string; nome: string; papel: string } | null;
  organizacoes: { id: string; nome: string }[];
}

/** Um dispositivo cadastrado nesta organização. */
export interface Dispositivo {
  id: string;
  nome: string;
  sistema: string;
  versao_agente: string;
  estado: "aguardando_pareamento" | "ativo" | "suspenso" | "revogado";
  /** Impressão digital da chave pública, igual à que o Agente mostra. */
  impressao: string;
  pareado_em: string;
  ultimo_contato: string;
}

/** Presença: quem está com o canal aberto **agora**. */
export interface Presenca {
  dispositivo_id: string;
  nome: string;
  conectado: boolean;
  desde: string;
}

/** O que o dispositivo respondeu sobre si mesmo. */
export interface EstadoDoDispositivo {
  ok: boolean;
  versao_agente?: string;
  raizes?: string[];
  /** Falso quando não há pasta autorizada: o Agente não copiaria nada. */
  pode_copiar?: boolean;
  erro?: string;
}

/** Código temporário para parear uma máquina. */
export interface CodigoDePareamento {
  codigo: string;
  expira_em: string;
  validade_minutos: number;
}

/** Resultado de um backup disparado pela tela. */
export interface ResultadoDeBackup {
  execucao_id: string;
  ok: boolean;
  pacote?: string;
  erro?: string;
}

/** Uma linha da trilha de auditoria. */
export interface LinhaDeAuditoria {
  id: string;
  acao: string;
  alvo: string;
  detalhe: string;
  quando: string;
  dispositivo_id: string;
}

/**
 * A trilha, e se ela continua íntegra.
 *
 * `integra` vem junto porque a corrente de hashes só vale enquanto se pode
 * conferir: mostrar as linhas sem dizer se elas ainda batem seria pedir
 * exatamente a confiança que o encadeamento existe para dispensar.
 */
export function listarAuditoria(): Promise<{
  integra: boolean;
  explicacao: string;
  linhas: LinhaDeAuditoria[];
}> {
  return pedir("/api/historico/auditoria");
}

/** Ficha de um pacote produzido por uma execução. */
export interface ArtefatoDaExecucao {
  id: string;
  nome: string;
  tamanho_bytes: number;
  sha256: string;
  /** Onde o pacote está, do ponto de vista do dispositivo. Nunca um caminho. */
  localizacao: string;
}

/** Uma rodada de backup registrada no histórico. */
export interface Execucao {
  id: string;
  dispositivo_id: string;
  politica_id: string;
  /** `manual` veio da tela; `agendamento` rodou sozinho, na máquina. */
  origem: string;
  resultado:
    "em_andamento" | "sucesso" | "com_ressalva" | "falha" | "cancelada";
  iniciada_em: string;
  terminada_em: string;
  arquivos: number;
  bytes_copiados: number;
  ressalva: string;
  artefatos: ArtefatoDaExecucao[];
}

/** Um pacote que existe na máquina agora. */
export interface PacoteNaMaquina {
  nome: string;
  tamanho_bytes: number;
  criado_em: string;
}

/** Um arquivo declarado dentro de um pacote. */
export interface ItemDoPacote {
  arquivo: string;
  neste_pacote: string;
  onde: string;
}

/**
 * O que a restauração fez, e o que não fez.
 *
 * `restaurados` é uma **contagem**, e `completa` vem decidido pelo núcleo. A
 * tela não recalcula: quem sabe se a restauração entregou tudo que o pacote
 * prometia é quem abriu o pacote.
 */
export interface RelatorioDeRestauracao {
  ok?: boolean;
  erro?: string;
  destino?: string;
  restaurados?: number;
  completa?: boolean;
  ja_existiam?: string[];
  recusados?: string[];
  faltando?: string[];
  corrompidos?: string[];
  protecao?: string;
}

/**
 * Erro com o código HTTP preservado.
 *
 * A tela precisa distinguir 409 ("a máquina está desligada", que é normal) de
 * 500 ("algo quebrou"). Um `Error` sem código apagaria essa diferença, e a
 * pessoa veria "erro" toda noite, quando o computador da loja está fechado.
 */
export class ErroDaPlataforma extends Error {
  constructor(
    readonly status: number,
    mensagem: string,
  ) {
    super(mensagem);
    this.name = "ErroDaPlataforma";
  }
}

async function pedir<T>(
  caminho: string,
  opcoes: RequestInit = {},
): Promise<T> {
  const resposta = await fetch(caminho, {
    // O cookie de sessão é `HttpOnly`: o JavaScript não o lê, mas o navegador
    // o envia. `same-origin` é o que faz isso acontecer sem abrir a porta
    // para outro site.
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });

  let corpo: unknown = null;
  try {
    corpo = await resposta.json();
  } catch {
    corpo = null;
  }

  if (!resposta.ok) {
    const detalhe =
      (corpo as { detail?: string; erro?: string } | null)?.detail ??
      (corpo as { erro?: string } | null)?.erro ??
      `erro ${resposta.status}`;
    throw new ErroDaPlataforma(resposta.status, detalhe);
  }
  return corpo as T;
}

export function obterEstadoDeSessao(): Promise<EstadoDeSessao> {
  return pedir<EstadoDeSessao>("/api/auth/estado");
}

export function sair(): Promise<{ ok: boolean }> {
  return pedir<{ ok: boolean }>("/api/auth/sair", { method: "POST" });
}

/** Cria a primeira organização, com o convite impresso no console do servidor. */
export function primeiroAcesso(dados: {
  convite: string;
  organizacao: string;
  email: string;
  nome: string;
}): Promise<{ ok: boolean; organizacao: string }> {
  return pedir("/api/auth/bootstrap", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function listarDispositivos(): Promise<{ dispositivos: Dispositivo[] }> {
  return pedir("/api/dispositivos");
}

export function listarPresenca(): Promise<{
  conectados: Presenca[];
  total_conectados: number;
}> {
  return pedir("/api/agente/conectados");
}

export function emitirCodigo(): Promise<CodigoDePareamento> {
  return pedir("/api/dispositivos/codigo", { method: "POST" });
}

export function revogarDispositivo(
  id: string,
): Promise<{ id: string; estado: string }> {
  return pedir(`/api/dispositivos/${encodeURIComponent(id)}/revogar`, {
    method: "POST",
  });
}

export function consultarDispositivo(
  id: string,
): Promise<{ dispositivo_id: string; estado: EstadoDoDispositivo }> {
  return pedir(`/api/dispositivos/${encodeURIComponent(id)}/consultar`, {
    method: "POST",
  });
}

export function executarBackup(
  id: string,
  pedidoDeBackup: {
    origens?: string[];
    destino?: string;
    usar_vss?: boolean;
    destino_externo?: string;
    tipo_do_destino?: string;
    enviar_para_nuvem?: boolean;
    incremental?: boolean;
  } = {},
): Promise<ResultadoDeBackup> {
  return pedir(`/api/dispositivos/${encodeURIComponent(id)}/backup`, {
    method: "POST",
    body: JSON.stringify(pedidoDeBackup),
  });
}

/**
 * Histórico de execuções desta organização.
 *
 * Inclui o que o Agente fez sozinho, no horário agendado, com o navegador
 * fechado. São essas linhas que provam que o backup não depende de alguém
 * estar olhando.
 */
export function listarHistorico(
  dispositivoId = "",
): Promise<{ execucoes: Execucao[] }> {
  const busca = dispositivoId
    ? `?dispositivo_id=${encodeURIComponent(dispositivoId)}`
    : "";
  return pedir(`/api/historico${busca}`);
}

/**
 * Pacotes que existem NAQUELA máquina, agora.
 *
 * Vem do dispositivo, e não do banco: o servidor guarda a ficha do artefato,
 * mas quem sabe se o arquivo ainda está lá é a máquina. Listar do banco
 * ofereceria para restaurar um pacote que alguém já apagou.
 */
export function listarPacotes(id: string): Promise<{
  ok: boolean;
  pacotes?: PacoteNaMaquina[];
  tem_pasta_autorizada?: boolean;
  erro?: string;
}> {
  return pedir(`/api/dispositivos/${encodeURIComponent(id)}/pacotes`, {
    method: "POST",
  });
}

/** O que há dentro de um pacote, antes de mexer em qualquer coisa. */
export function listarConteudoDoPacote(
  id: string,
  pacote: string,
): Promise<{
  ok: boolean;
  pacote?: string;
  conteudo?: ItemDoPacote[];
  erro?: string;
}> {
  return pedir(`/api/dispositivos/${encodeURIComponent(id)}/pacote`, {
    method: "POST",
    body: JSON.stringify({ pacote }),
  });
}

/**
 * Restaura arquivos de um pacote para uma pasta da máquina.
 *
 * O pacote vai pelo **nome**: o Live não conhece caminho nenhum da máquina, e
 * quem resolve onde o arquivo está é o Agente. `conferir_backup` é como a tela
 * pede a guarda de ação destrutiva sem precisar conhecer pastas.
 */
export function restaurarNoDispositivo(
  id: string,
  pedidoDeRestauracao: {
    pacote: string;
    destino: string;
    anteriores?: string[];
    apenas?: string[];
    sobrescrever?: boolean;
    conferir_backup?: boolean;
    dispensar_protecao?: string;
  },
): Promise<RelatorioDeRestauracao> {
  return pedir(`/api/dispositivos/${encodeURIComponent(id)}/restaurar`, {
    method: "POST",
    body: JSON.stringify(pedidoDeRestauracao),
  });
}

/** Configuração de uma política, no formato que o núcleo valida. */
export interface ConfiguracaoDePolitica {
  origens: string[];
  destino: { tipo: string; caminho: string };
  agendamento: {
    tipo: string;
    hora: string;
    dia_da_semana: number;
    dia_do_mes: number;
  };
  retencao: { diarias: number; semanais: number; mensais: number };
  retry: { tentativas: number; espera_inicial_min: number };
  notificacao: { quando: string; emails: string[] };
  usar_vss: boolean;
  cifrar: boolean;
  assinar: boolean;
  incremental: boolean;
}

/** Uma política gravada, com o que o servidor conclui sobre ela. */
export interface Politica {
  id: string;
  nome: string;
  dispositivo_id: string;
  ativa: boolean;
  configuracao: ConfiguracaoDePolitica;
  /** Falso quando o pacote fica só na própria máquina. */
  protege_de_verdade: boolean;
  criada_em: string;
  atualizada_em: string;
}

/** O que aconteceu ao tentar mandar a política para a máquina. */
export interface Sincronizacao {
  aplicada: boolean;
  motivo?: string;
  politicas?: number;
  proximas?: { id: string; proxima: string }[];
}

/** O veredito de um backup, e os fatos que o sustentam. */
export interface BackupAvaliado {
  politica_id: string;
  nome: string;
  maquina: string;
  nivel: NivelDeProtecao;
  titulo: string;
  motivos: string[];
}

export type NivelDeProtecao =
  | "sem_configuracao"
  | "em_risco"
  | "parcial"
  | "protegido";

/**
 * A resposta para "meus dados estão protegidos?".
 *
 * O nível da organização é o **pior** entre os backups: quem tem uma máquina
 * impecável e outra sem backup há dias não está protegido, e arredondar para
 * o melhor caso seria o erro exato que este veredito existe para evitar.
 */
export interface EstadoDeProtecao {
  nivel: NivelDeProtecao;
  titulo: string;
  resumo: string;
  backups: BackupAvaliado[];
}

export function obterProtecao(): Promise<EstadoDeProtecao> {
  return pedir("/api/protecao");
}

export function listarPoliticas(): Promise<{ politicas: Politica[] }> {
  return pedir("/api/politicas");
}

/**
 * Cria a política e tenta aplicá-la na mesma operação.
 *
 * A resposta traz `sincronizacao`: máquina desligada devolve "pendente", e não
 * erro. A diferença entre "vai valer" e "está valendo" é a diferença entre ter
 * backup hoje à noite e descobrir amanhã que não teve.
 */
export function criarPolitica(pedido: {
  nome: string;
  dispositivo_id: string;
  ativa?: boolean;
  configuracao: Partial<ConfiguracaoDePolitica>;
}): Promise<Politica & { sincronizacao: Sincronizacao }> {
  return pedir("/api/politicas", {
    method: "POST",
    body: JSON.stringify(pedido),
  });
}

export function alterarPolitica(
  id: string,
  pedido: {
    nome: string;
    dispositivo_id: string;
    ativa?: boolean;
    configuracao: Partial<ConfiguracaoDePolitica>;
  },
): Promise<Politica & { sincronizacao: Sincronizacao }> {
  return pedir(`/api/politicas/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(pedido),
  });
}

export function removerPolitica(
  id: string,
): Promise<{ removida: string; sincronizacao: Sincronizacao }> {
  return pedir(`/api/politicas/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/**
 * O que vem no download, antes do clique.
 *
 * `formato` muda o roteiro inteiro: com `exe` é duplo clique e acabou; com
 * `zip` é instalar o Python e rodar um script. A tela não pode prometer o
 * primeiro quando o servidor só tem o segundo.
 */
export interface FichaDoInstalador {
  formato: "exe" | "zip";
  nome: string;
  tamanho_bytes: number;
  arquivos: number;
  /** Vazio quando o executável já traz o Python dentro. */
  precisa_de_python: string;
  /** Pasta que aparece dentro do ZIP — é nela que o terminal precisa abrir. */
  pasta_do_pacote?: string;
}

/** Endereço do download do Agente. É um arquivo de verdade, não um link morto. */
export const ENDERECO_DO_INSTALADOR = "/api/agente/instalador";

/**
 * O endereço com o código de pareamento junto.
 *
 * É ele que faz o executável já saber para onde ligar: o servidor cola endereço
 * e código no fim do arquivo antes de entregar. Sem isso, a pessoa teria que
 * digitar os dois numa janela.
 */
export function enderecoDoInstalador(codigo: string): string {
  return codigo
    ? `${ENDERECO_DO_INSTALADOR}?codigo=${encodeURIComponent(codigo)}`
    : ENDERECO_DO_INSTALADOR;
}

/**
 * Tamanho e conteúdo do pacote, antes de baixar.
 *
 * Um botão de download que não diz o tamanho nem o que vem dentro pede um ato
 * de fé que ninguém deveria ter que dar.
 */
export function fichaDoInstalador(): Promise<FichaDoInstalador> {
  return pedir(`${ENDERECO_DO_INSTALADOR}/ficha`);
}

/** Lê o convite da URL de primeiro acesso, quando houver. */
export function conviteDaUrl(busca: string = window.location.search): string {
  return new URLSearchParams(busca).get("convite") ?? "";
}
