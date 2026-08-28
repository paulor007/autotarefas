import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import {
  cliqueDeNavegacao,
  comVolta,
  destinoDeVolta,
  ehDoProduto,
  enderecoDa,
  navegar,
  parametro,
  PRODUTO,
  secaoDe,
  useCaminho,
  VITRINE,
} from "./rotas";

function irPara(caminho: string): void {
  window.history.replaceState(null, "", caminho);
}

beforeEach(() => {
  irPara(VITRINE);
});

describe("de que zona e o caminho", () => {
  it("a raiz e a vitrine", () => {
    expect(ehDoProduto("/")).toBe(false);
  });

  it("/app e o produto", () => {
    expect(ehDoProduto("/app")).toBe(true);
    expect(ehDoProduto("/app/backups")).toBe(true);
  });

  it("um caminho que so COMECA com as letras de /app nao e o produto", () => {
    // `/aplicativos` nao pode cair na area autenticada por parecer com `/app`.
    expect(ehDoProduto("/aplicativos")).toBe(false);
    expect(ehDoProduto("/appendice")).toBe(false);
  });

  it("a busca nao muda a zona", () => {
    expect(ehDoProduto("/app/backups?voltar=/app")).toBe(true);
  });

  it("o link do convite abre o produto, e nao a vitrine", () => {
    // O servidor imprime este endereco no console da primeira execucao. Quem
    // o segue vem criar a organizacao; cair no catalogo seria mandar a pessoa
    // procurar, na vitrine, o formulario pelo qual ela foi convidada.
    expect(ehDoProduto("/primeiro-acesso")).toBe(true);
    expect(ehDoProduto("/primeiro-acesso?convite=abc")).toBe(true);
  });
});

describe("qual secao do produto", () => {
  it("a raiz do produto e o inicio", () => {
    expect(secaoDe("/app")).toBe("inicio");
    expect(secaoDe("/app/")).toBe("inicio");
  });

  it("cada secao conhecida se reconhece", () => {
    expect(secaoDe("/app/backups")).toBe("backups");
    expect(secaoDe("/app/dispositivos")).toBe("dispositivos");
    expect(secaoDe("/app/atividade")).toBe("atividade");
    expect(secaoDe("/app/configuracoes")).toBe("configuracoes");
  });

  it("uma secao que nao existe cai no inicio, em vez de tela em branco", () => {
    expect(secaoDe("/app/inventada")).toBe("inicio");
  });

  it("o que vem depois da secao nao muda a secao", () => {
    expect(secaoDe("/app/backups/novo")).toBe("backups");
    expect(secaoDe("/app/backups?voltar=/app")).toBe("backups");
  });

  it("endereco e secao sao a ida e a volta do mesmo caminho", () => {
    for (const secao of [
      "inicio",
      "backups",
      "dispositivos",
      "atividade",
      "configuracoes",
    ] as const) {
      expect(secaoDe(enderecoDa(secao))).toBe(secao);
    }
  });
});

describe("parametro da busca", () => {
  it("devolve nulo quando nao ha busca", () => {
    expect(parametro("/app/backups", "voltar")).toBeNull();
  });

  it("le o parametro pedido", () => {
    expect(parametro("/app/dispositivos?voltar=%2Fapp%2Fbackups", "voltar")).toBe(
      "/app/backups",
    );
  });
});

describe("navegar", () => {
  it("muda o endereco do navegador", () => {
    navegar("/app/backups");
    expect(window.location.pathname).toBe("/app/backups");
  });

  it("a tela acompanha", () => {
    const { result } = renderHook(() => useCaminho());
    expect(result.current).toBe("/");
    act(() => {
      navegar("/app/dispositivos");
    });
    expect(result.current).toBe("/app/dispositivos");
  });

  it("o evento de voltar do navegador faz a tela reler o endereco", () => {
    // Aqui se prova a assinatura do `popstate`, nao a fidelidade do jsdom: o
    // `back()` dele nao caminha de forma confiavel depois de varios
    // `replaceState`. O que este projeto precisa garantir e que, quando o
    // navegador avisar que o endereco mudou por fora, a tela acompanhe — sem
    // isso, o botao voltar troca a barra de enderecos e deixa o conteudo
    // antigo na frente do usuario.
    const { result } = renderHook(() => useCaminho());
    act(() => {
      navegar("/app/atividade");
    });
    expect(result.current).toBe("/app/atividade");

    act(() => {
      window.history.replaceState(null, "", PRODUTO);
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current).toBe(PRODUTO);
  });

  it("navegar para onde ja se esta nao empilha historico", () => {
    const antes = window.history.length;
    navegar("/");
    expect(window.history.length).toBe(antes);
  });
});

describe("clique de navegacao", () => {
  function evento(extras: Record<string, unknown> = {}) {
    return {
      defaultPrevented: false,
      button: 0,
      metaKey: false,
      ctrlKey: false,
      shiftKey: false,
      altKey: false,
      preventDefault: () => {
        chamouPreventDefault = true;
      },
      ...extras,
    } as unknown as Parameters<ReturnType<typeof cliqueDeNavegacao>>[0];
  }

  let chamouPreventDefault = false;
  beforeEach(() => {
    chamouPreventDefault = false;
  });

  it("o clique simples navega sem recarregar", () => {
    cliqueDeNavegacao("/app")(evento());
    expect(chamouPreventDefault).toBe(true);
    expect(window.location.pathname).toBe("/app");
  });

  it("ctrl+clique fica com o navegador, para abrir em outra aba", () => {
    cliqueDeNavegacao("/app")(evento({ ctrlKey: true }));
    expect(chamouPreventDefault).toBe(false);
    expect(window.location.pathname).toBe("/");
  });

  it("o botao do meio fica com o navegador", () => {
    cliqueDeNavegacao("/app")(evento({ button: 1 }));
    expect(chamouPreventDefault).toBe(false);
    expect(window.location.pathname).toBe("/");
  });
});

describe("destino de volta", () => {
  it("aceita um caminho de dentro do produto", () => {
    expect(destinoDeVolta(comVolta("/app/dispositivos", "/app/backups"))).toBe(
      "/app/backups",
    );
  });

  it("nulo quando não há para onde voltar", () => {
    expect(destinoDeVolta("/app/dispositivos")).toBeNull();
    expect(destinoDeVolta("/app/dispositivos?voltar=")).toBeNull();
  });

  it("recusa um destino fora do produto", () => {
    // Sem esta recusa, `?voltar=https://algum-site` viraria um botão com a
    // cara do AutoTarefas levando para fora dele.
    for (const fora of [
      "https://exemplo.invalido",
      "//exemplo.invalido",
      "/",
      "/primeiro-acesso",
      "javascript:alert(1)",
    ]) {
      expect(destinoDeVolta(comVolta("/app/dispositivos", fora))).toBeNull();
    }
  });
});
