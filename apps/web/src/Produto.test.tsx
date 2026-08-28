import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Produto from "./Produto";
import { enderecoDa, PRODUTO } from "./lib/rotas";

/**
 * Testes do produto autenticado.
 *
 * Duas coisas se protegem aqui. A primeira é a recusa de mentir na porta de
 * entrada: botão que não funciona é a mentira mais fácil de cometer numa
 * interface. A segunda é a navegação — o motivo desta reorganização foi
 * alguém não encontrar "Parear nova máquina" e clicar em "Sair" no lugar.
 */

const SEM_ORGANIZACAO = {
  autenticado: false,
  provedor_configurado: false,
  precisa_bootstrap: true,
  usuario: null,
  organizacao: null,
  organizacoes: [],
};

const LOGADO = {
  autenticado: true,
  provedor_configurado: true,
  precisa_bootstrap: false,
  usuario: { id: "u1", nome: "Ana", email: "ana@padaria.com.br" },
  organizacao: { id: "o1", nome: "Padaria Sol", papel: "dono" },
  organizacoes: [{ id: "o1", nome: "Padaria Sol" }],
};

const MAQUINA = {
  id: "d1",
  nome: "PC da loja",
  sistema: "Windows 11",
  versao_agente: "0.1.0",
  estado: "ativo",
  impressao: "AAAA-BBBB-CCCC-DDDD",
  pareado_em: "2026-08-25T10:00:00+00:00",
  ultimo_contato: "2026-08-25T10:05:00+00:00",
};

const VAZIO = {
  "/api/auth/estado": { corpo: LOGADO },
  "/api/dispositivos": { corpo: { dispositivos: [] } },
  "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
  "/api/politicas": { corpo: { politicas: [] } },
  "/api/historico": { corpo: { execucoes: [] } },
  "/api/historico/auditoria": {
    corpo: { integra: true, explicacao: "", linhas: [] },
  },
  "/api/protecao": {
    corpo: {
      nivel: "sem_configuracao",
      titulo: "Nenhum backup configurado",
      resumo: "Nenhum backup ativo. Enquanto não houver política, nada é copiado.",
      backups: [],
    },
  },
};

function mockRotas(
  respostas: Record<string, { corpo: unknown; status?: number }>,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      // Casa pelo FIM da URL primeiro: `/api/historico` também aparece dentro
      // de `/api/historico/auditoria`.
      const rotas = Object.keys(respostas);
      const chave =
        rotas.find((rota) => url.endsWith(rota)) ??
        rotas.find((rota) => url.includes(rota));
      const item = chave ? respostas[chave] : undefined;
      const status = item?.status ?? (item ? 200 : 404);
      return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => item?.corpo ?? { detail: "rota não simulada" },
      } as Response;
    }),
  );
}

function irPara(caminho: string): void {
  window.history.replaceState(null, "", caminho);
}

beforeEach(() => {
  vi.restoreAllMocks();
  irPara(PRODUTO);
});

describe("porta de entrada", () => {
  it("com banco vazio, manda procurar o convite no console", async () => {
    // Sem o convite na URL, um formulário que aceita qualquer coisa e depois
    // recusa transformaria um passo simples num chamado de suporte.
    mockRotas({ "/api/auth/estado": { corpo: SEM_ORGANIZACAO } });
    render(<Produto />);

    await waitFor(() => {
      expect(screen.getByText(/Primeiro acesso/)).toBeTruthy();
    });
    expect(screen.getByText(/no console/i)).toBeTruthy();
  });

  it("sem provedor configurado, não mostra botão de entrar", async () => {
    // Botão que não funciona é a mentira mais fácil de cometer numa interface.
    mockRotas({
      "/api/auth/estado": {
        corpo: { ...SEM_ORGANIZACAO, precisa_bootstrap: false },
      },
    });
    render(<Produto />);

    await waitFor(() => {
      expect(
        screen.getByText(/não tem provedor de identidade/i),
      ).toBeTruthy();
    });
    // Por PAPEL, e não por texto: a tela agora explica, em prosa, que existe
    // esse caminho para quem configurar OIDC. O que não pode existir é o
    // link — botão que não funciona é a mentira mais fácil de cometer.
    expect(
      screen.queryByRole("link", { name: /Entrar com a conta da empresa/i }),
    ).toBeNull();
  });

  it("com provedor configurado, oferece a entrada", async () => {
    mockRotas({
      "/api/auth/estado": {
        corpo: {
          ...SEM_ORGANIZACAO,
          precisa_bootstrap: false,
          provedor_configurado: true,
        },
      },
    });
    render(<Produto />);

    await waitFor(() => {
      expect(screen.getByText(/Entrar com a conta da empresa/i)).toBeTruthy();
    });
  });

  it("sem provedor, a tela diz ONDE está a entrada", async () => {
    // Antes ela dizia "não há como entrar por aqui" e parava. Quem lê essa
    // tela é, quase sempre, a própria pessoa que administra o servidor — e ela
    // ficava olhando uma tela sem nada para clicar, sem saber que a entrada
    // existe e está no console.
    mockRotas({
      "/api/auth/estado": {
        corpo: { ...SEM_ORGANIZACAO, precisa_bootstrap: false },
      },
    });
    render(<Produto />);

    await waitFor(() => {
      expect(screen.getByText(/imprime no console/i)).toBeTruthy();
    });
    expect(screen.getByText(/reinicie o serviço/i)).toBeTruthy();
    expect(screen.getByText(/vale uma vez e por 30 minutos/i)).toBeTruthy();
  });

  it("deslogado não mostra a navegação do produto", async () => {
    mockRotas({
      "/api/auth/estado": {
        corpo: { ...SEM_ORGANIZACAO, precisa_bootstrap: false },
      },
    });
    render(<Produto />);

    await waitFor(() => {
      expect(
        screen.getByText(/não tem provedor de identidade/i),
      ).toBeTruthy();
    });
    expect(screen.queryByRole("navigation", { name: /Seções/i })).toBeNull();
  });
});

describe("navegação", () => {
  it("as cinco seções ficam sempre à vista", async () => {
    mockRotas(VAZIO);
    render(<Produto />);

    const navegacao = await screen.findByRole("navigation", {
      name: /Seções/i,
    });
    for (const nome of [
      "Início",
      "Backups",
      "Dispositivos",
      "Atividade",
      "Configurações",
    ]) {
      expect(within(navegacao).getByRole("link", { name: nome })).toBeTruthy();
    }
  });

  it("Dispositivos leva direto ao pareamento, sem rolar tela nenhuma", async () => {
    // Este é o defeito que originou a reorganização: "Parear nova máquina"
    // ficava cinco blocos abaixo, no fim de uma página de vitrine, e quem
    // procurava clicava em "Sair" — que era o botão em evidência.
    mockRotas(VAZIO);
    render(<Produto />);

    const navegacao = await screen.findByRole("navigation", {
      name: /Seções/i,
    });
    await userEvent.click(
      within(navegacao).getByRole("link", { name: "Dispositivos" }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Parear nova máquina/i }),
      ).toBeTruthy();
    });
    expect(window.location.pathname).toBe(enderecoDa("dispositivos"));
  });

  it("Sair mora em Configurações, e não no topo de todas as telas", async () => {
    mockRotas(VAZIO);
    render(<Produto />);

    await screen.findByRole("navigation", { name: /Seções/i });
    expect(screen.queryByRole("button", { name: /^Sair$/ })).toBeNull();

    await userEvent.click(screen.getByRole("link", { name: "Configurações" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^Sair$/ })).toBeTruthy();
    });
  });

  it("a organização fica à vista em qualquer seção", async () => {
    // Em nome de quem você está operando é contexto de tudo o que vem depois,
    // e não um detalhe de configuração. Antes ficava no cabeçalho do painel —
    // ao lado do "Sair", que foi o problema; o nome não era.
    mockRotas(VAZIO);
    render(<Produto />);

    const faixa = await screen.findByRole("banner");
    expect(within(faixa).getByText("Padaria Sol")).toBeTruthy();
    expect(within(faixa).getByText("ana@padaria.com.br")).toBeTruthy();

    await userEvent.click(screen.getByRole("link", { name: "Atividade" }));
    expect(within(faixa).getByText("Padaria Sol")).toBeTruthy();
  });

  it("um endereço direto abre a seção certa", async () => {
    // `/app/atividade` vai para os favoritos de alguém e volta num F5.
    irPara(enderecoDa("atividade"));
    mockRotas(VAZIO);
    render(<Produto />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Execuções" })).toBeTruthy();
    });
    expect(screen.getByRole("heading", { name: "Auditoria" })).toBeTruthy();
  });
});

describe("início", () => {
  it("sem máquina, o cartão diz o que falta e leva para lá", async () => {
    mockRotas(VAZIO);
    render(<Produto />);

    await waitFor(() => {
      expect(screen.getByText(/Nenhuma máquina conectada/i)).toBeTruthy();
    });
    const acao = screen.getByRole("link", { name: /Adicionar máquina/i });
    expect(acao.getAttribute("href")).toBe(enderecoDa("dispositivos"));
  });

  it("com máquina e sem política, o cartão manda configurar o backup", async () => {
    mockRotas({
      ...VAZIO,
      "/api/dispositivos": { corpo: { dispositivos: [MAQUINA] } },
    });
    render(<Produto />);

    await waitFor(() => {
      expect(screen.getByText(/Falta dizer o que copiar/i)).toBeTruthy();
    });
    const acao = screen.getByRole("link", { name: /Configurar backup/i });
    expect(acao.getAttribute("href")).toBe(enderecoDa("backups"));
  });
});

describe("estado da proteção", () => {
  function comProtecao(corpo: unknown) {
    return { ...VAZIO, "/api/protecao": { corpo } };
  }

  it("sem nada configurado, não acusa risco nem promete proteção", async () => {
    // "Em risco" para quem ainda não teve chance de configurar acusaria a
    // pessoa de um problema que ela não criou.
    mockRotas(VAZIO);
    render(<Produto />);

    const selo = await screen.findByRole("region", { name: /proteção/i });
    expect(within(selo).getByText(/Nenhum backup configurado/i)).toBeTruthy();
  });

  it("destino no mesmo computador vira Proteção parcial, com o motivo", async () => {
    mockRotas(
      comProtecao({
        nivel: "parcial",
        titulo: "Proteção parcial",
        resumo: "1 backup ativo. 1 precisa de atenção.",
        backups: [
          {
            politica_id: "p1",
            nome: "Backup da loja",
            maquina: "PC da loja",
            nivel: "parcial",
            titulo: "Proteção parcial",
            motivos: [
              "A cópia fica no mesmo computador dos arquivos originais.",
            ],
          },
        ],
      }),
    );
    render(<Produto />);

    const selo = await screen.findByRole("region", { name: /proteção/i });
    expect(within(selo).getByText("Proteção parcial")).toBeTruthy();
    expect(within(selo).getByText(/mesmo computador/i)).toBeTruthy();
    expect(within(selo).getByText("Backup da loja")).toBeTruthy();
  });

  it("o veredito da empresa é o pior dos backups, e diz de qual", async () => {
    mockRotas(
      comProtecao({
        nivel: "em_risco",
        titulo: "Proteção em risco",
        resumo: "2 backups ativos. 1 precisa de atenção.",
        backups: [
          {
            politica_id: "p1",
            nome: "Backup da loja",
            maquina: "PC da loja",
            nivel: "protegido",
            titulo: "Protegido",
            motivos: [],
          },
          {
            politica_id: "p2",
            nome: "Backup do escritório",
            maquina: "PC do escritório",
            nivel: "em_risco",
            titulo: "Proteção em risco",
            motivos: ["Este backup nunca concluiu uma execução."],
          },
        ],
      }),
    );
    render(<Produto />);

    const selo = await screen.findByRole("region", { name: /proteção/i });
    expect(within(selo).getByText("Proteção em risco")).toBeTruthy();
    expect(within(selo).getByText("Backup do escritório")).toBeTruthy();
    expect(within(selo).getByText(/nunca concluiu/i)).toBeTruthy();
    // O backup que está bem não vira ruído: sem motivo, não vira linha.
    expect(within(selo).queryByText("Backup da loja")).toBeNull();
  });
});
