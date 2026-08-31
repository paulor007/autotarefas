/**
 * Como a configuração de um backup é dita para gente.
 *
 * O produto guarda `{"tipo": "local", "caminho": "D:\\...\\vitrine\\dados"}`,
 * e isso é o certo: é o que o Agente precisa para trabalhar. O que estava
 * errado era mostrar isso na tela.
 *
 * Duas regras governam este arquivo.
 *
 * **Caminho interno não é informação para quem visita.** `D:\Projetos\...` diz
 * onde o desenvolvedor guardou uma pasta, e não o que está sendo protegido.
 * Pior: numa instalação de cliente, o mesmo campo revelaria a estrutura de
 * pastas da empresa a quem só deveria estar olhando. Quem administra a própria
 * máquina continua vendo o caminho — para essa pessoa ele é o dado.
 *
 * **Nada é inventado.** Cada rótulo aqui é uma tradução do que existe, e não um
 * enfeite: `desligado` vira "Sem horário", e não some da tela.
 */

/** Tipos de destino, no vocabulário de quem contrata e não de quem programa. */
const DESTINOS: Record<string, string> = {
  nenhum: "Somente nesta máquina",
  local: "Outra pasta desta máquina",
  externo: "Disco externo",
  rede: "Pasta de rede",
  nuvem: "Armazenamento em nuvem",
};

const DIAS = [
  "segunda-feira",
  "terça-feira",
  "quarta-feira",
  "quinta-feira",
  "sexta-feira",
  "sábado",
  "domingo",
];

export function destinoEmPalavras(tipo: string): string {
  return DESTINOS[tipo] ?? tipo;
}

/**
 * O agendamento numa frase.
 *
 * "Todos os dias às 03:00" responde a pergunta que `{"tipo":"diario"}` só
 * responde a quem já sabe o formato.
 */
export function agendamentoEmPalavras(agendamento: {
  tipo: string;
  hora: string;
  dia_da_semana?: number;
  dia_do_mes?: number;
}): string {
  const hora = agendamento.hora;
  switch (agendamento.tipo) {
    case "diario":
      return `Todos os dias às ${hora}`;
    case "semanal":
      return `Toda ${DIAS[agendamento.dia_da_semana ?? 0] ?? "semana"} às ${hora}`;
    case "mensal":
      return `Todo dia ${agendamento.dia_do_mes ?? 1} do mês, às ${hora}`;
    default:
      // Não some da tela: "sem horário" é uma escolha válida, e confundi-la
      // com backup automático é o mal-entendido mais caro desta tela.
      return "Sem horário — só quando alguém manda";
  }
}

/**
 * O nome legível de uma pasta, a partir do caminho dela.
 *
 * Fica com o último trecho: é ele que a pessoa reconhece. `financeiro-2026`
 * vira "Financeiro 2026"; `D:\Empresa\Contratos` vira "Contratos".
 *
 * Não é disfarce — a pasta chama-se assim. O que se remove é a árvore acima
 * dela, que diz respeito a quem administra a máquina e a mais ninguém.
 */
export function pastaEmPalavras(caminho: string): string {
  const partes = caminho.split(/[\\/]+/).filter(Boolean);
  const ultima = partes[partes.length - 1] ?? caminho;
  const limpa = ultima.replace(/[-_]+/g, " ").trim();
  if (!limpa) return caminho;
  return limpa.charAt(0).toUpperCase() + limpa.slice(1);
}

/**
 * As origens de uma política, prontas para a tela.
 *
 * Lista vazia é uma informação, e não um vazio: significa "todas as pastas
 * autorizadas na máquina", que é o padrão útil de quem autorizou uma pasta
 * justamente para que ela fosse copiada.
 */
export function origensEmPalavras(origens: string[]): string {
  if (origens.length === 0) return "Todas as pastas autorizadas na máquina";
  return origens.map(pastaEmPalavras).join(" · ");
}

export function retencaoEmPalavras(retencao: {
  diarias: number;
  semanais: number;
  mensais: number;
}): string[] {
  return [
    `${retencao.diarias} ${retencao.diarias === 1 ? "diário" : "diários"}`,
    `${retencao.semanais} ${retencao.semanais === 1 ? "semanal" : "semanais"}`,
    `${retencao.mensais} ${retencao.mensais === 1 ? "mensal" : "mensais"}`,
  ];
}

const AVISOS: Record<string, string> = {
  problema: "Somente em caso de problema",
  sempre: "A cada execução",
  nunca: "Nunca",
};

export function notificacaoEmPalavras(quando: string): string {
  return AVISOS[quando] ?? quando;
}

export function ligadoOuNao(valor: boolean): string {
  return valor ? "Ativo" : "Desligado";
}

/**
 * O motivo curto de uma proteção que não está inteira.
 *
 * A lista de backups mostrava o parágrafo completo em cada linha, e com quatro
 * políticas eram quatro cópias do mesmo texto — que a pessoa deixa de ler na
 * segunda. Aqui fica a etiqueta; o motivo por extenso vive no painel de Início
 * e dentro de "Ver configuração".
 *
 * Vazio quando não há ressalva **daquela** natureza: uma etiqueta que aparece
 * sempre não distingue nada.
 */
export function ressalvaCurta(config: {
  destino: { tipo: string };
  agendamento: { tipo: string };
}): string {
  if (config.destino.tipo === "nenhum" || config.destino.tipo === "local") {
    return "destino local";
  }
  if (config.agendamento.tipo === "desligado") return "sem horário";
  return "";
}
