/**
 * O roteador do Live — pequeno de proposito.
 *
 * O AutoTarefas tinha uma pagina so, com ancoras: `#catalogo`, `#execucao`,
 * `#empresa`. Funciona para uma vitrine e falha para um produto, porque
 * ancora nao separa "quem esta avaliando" de "quem ja e cliente": as duas
 * coisas dividem a mesma tela, e o produto acaba embaixo da demonstracao.
 *
 * Agora sao dois enderecos de verdade:
 *
 * - `/`     vitrine e demonstracoes, sem sessao;
 * - `/app`  o produto, com sessao.
 *
 * Nao ha biblioteca de rotas aqui. Sao duas zonas e cinco secoes; uma
 * dependencia inteira para isso seria mais codigo de configuracao do que este
 * arquivo. Se um dia houver rota aninhada, parametro de caminho ou carregamento
 * sob demanda, troque por uma biblioteca — este modulo existe para ser
 * substituivel.
 */

import type { MouseEvent } from "react";
import { useSyncExternalStore } from "react";

export const VITRINE = "/";
export const PRODUTO = "/app";

/**
 * O endereco que o servidor imprime no console da primeira execucao.
 *
 * E o produto antes de existir conta: quem abre este link vai criar a
 * organizacao. Nao e vitrine — mostrar catalogo e demonstracao a quem
 * chegou por um convite seria esconder a unica coisa que ele veio fazer.
 */
export const PRIMEIRO_ACESSO = "/primeiro-acesso";

/** As secoes do produto, na ordem em que aparecem na navegacao. */
export const SECOES = [
  "inicio",
  "backups",
  "dispositivos",
  "atividade",
  "configuracoes",
] as const;

export type Secao = (typeof SECOES)[number];

const ouvintes = new Set<() => void>();

function avisar(): void {
  for (const ouvinte of ouvintes) {
    ouvinte();
  }
}

function assinar(ouvinte: () => void): () => void {
  ouvintes.add(ouvinte);
  return () => {
    ouvintes.delete(ouvinte);
  };
}

/** Caminho + busca. A busca importa: e por ela que o "voltar para" viaja. */
function ler(): string {
  if (typeof window === "undefined") {
    return VITRINE;
  }
  return window.location.pathname + window.location.search;
}

if (typeof window !== "undefined") {
  // Botao "voltar" do navegador. Sem isto o endereco muda e a tela nao.
  window.addEventListener("popstate", avisar);
}

/** O caminho atual, reagindo a navegacao e ao botao voltar. */
export function useCaminho(): string {
  return useSyncExternalStore(assinar, ler, () => VITRINE);
}

export function navegar(destino: string, substituir = false): void {
  if (typeof window === "undefined" || destino === ler()) {
    return;
  }
  if (substituir) {
    window.history.replaceState(null, "", destino);
  } else {
    window.history.pushState(null, "", destino);
  }
  window.scrollTo({ top: 0 });
  avisar();
}

function semBusca(caminho: string): string {
  return caminho.split("?")[0] ?? "";
}

/** Uma secao do produto — `/primeiro-acesso` nao conta. */
function ehSecao(caminho: string): boolean {
  const so = semBusca(caminho);
  return so === PRODUTO || so.startsWith(`${PRODUTO}/`);
}

export function ehDoProduto(caminho: string): boolean {
  return ehSecao(caminho) || semBusca(caminho) === PRIMEIRO_ACESSO;
}

export function secaoDe(caminho: string): Secao {
  const resto = semBusca(caminho)
    .slice(PRODUTO.length)
    .replace(/^\/+/, "")
    .split("/")[0];
  return SECOES.includes(resto as Secao) ? (resto as Secao) : "inicio";
}

export function enderecoDa(secao: Secao): string {
  return secao === "inicio" ? PRODUTO : `${PRODUTO}/${secao}`;
}

/** Um parametro da busca do caminho dado. */
export function parametro(caminho: string, nome: string): string | null {
  const corte = caminho.indexOf("?");
  return corte < 0
    ? null
    : new URLSearchParams(caminho.slice(corte)).get(nome);
}

/**
 * Para onde voltar depois de resolver o que faltava.
 *
 * Adotar uma maquina leva minutos e quase sempre acontece em OUTRO computador.
 * Quem sai da configuracao do backup para parear precisa reencontrar o
 * caminho de volta sem refazer nada — e o caminho viaja na propria URL, para
 * sobreviver a um F5.
 *
 * O valor vem de fora, entao passa por filtro: so caminho dentro do produto.
 * Sem isso, `?voltar=https://algum-site` viraria um botao do AutoTarefas que
 * leva para fora dele — com a aparencia de ser do AutoTarefas.
 */
export function destinoDeVolta(caminho: string): string | null {
  const bruto = parametro(caminho, "voltar");
  // `ehSecao`, e nao `ehDoProduto`: `/primeiro-acesso` pertence ao produto mas
  // nao e lugar para onde se volta — a organizacao ja existe.
  return bruto && ehSecao(bruto) ? bruto : null;
}

/** `/app/dispositivos?voltar=/app/backups`, montado sem erro de escapamento. */
export function comVolta(destino: string, voltar: string): string {
  return `${destino}?voltar=${encodeURIComponent(voltar)}`;
}

/**
 * `onClick` para um `<a href>` de verdade.
 *
 * O `href` continua valendo: clique do meio, ctrl+clique e "abrir em nova aba"
 * seguem sendo do navegador. So o clique simples e interceptado.
 */
export function cliqueDeNavegacao(
  destino: string,
): (evento: MouseEvent) => void {
  return (evento: MouseEvent) => {
    if (
      evento.defaultPrevented ||
      evento.button !== 0 ||
      evento.metaKey ||
      evento.ctrlKey ||
      evento.shiftKey ||
      evento.altKey
    ) {
      return;
    }
    evento.preventDefault();
    navegar(destino);
  };
}
