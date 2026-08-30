import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AoVivo from "./AoVivo";

/**
 * O painel do agora.
 *
 * Ele é fácil de errar em duas direções opostas, e os testes cobrem as duas:
 * inventar movimento onde não há, e não dizer que o sistema está vivo quando
 * nada está rodando.
 */

const SEM_NADA = {
  agora: "2026-08-30T14:00:00+00:00",
  executando: [],
  proximas: [
    {
      politica_id: "p1",
      nome: "Backup diario 15:00",
      maquina: "SERVIDOR-DEMONSTRACAO",
      proxima_no_relogio_da_maquina: "2026-08-30T15:00:00",
      quando: "diario",
      hora: "15:00",
    },
  ],
};

const RODANDO = {
  agora: "2026-08-30T15:00:12+00:00",
  executando: [
    {
      politica_id: "p1",
      politica_nome: "Backup diario 15:00",
      maquina: "SERVIDOR-DEMONSTRACAO",
      dispositivo_id: "d1",
      etapa: "entregando",
      etapa_em_portugues: "Copiando para o destino",
      arquivos: 12,
      destino: "disco externo",
      desde: "2026-08-30T15:00:10+00:00",
    },
  ],
  proximas: SEM_NADA.proximas,
};

function mockResposta(corpo: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        ({ ok: true, status: 200, json: async () => corpo }) as Response,
    ),
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("atividade ao vivo", () => {
  it("com backup rodando, mostra a etapa em português", async () => {
    mockResposta(RODANDO);

    render(<AoVivo />);

    expect(
      await screen.findByText("Copiando para o destino"),
    ).toBeTruthy();
    expect(screen.getByText("Backup diario 15:00")).toBeTruthy();
  });

  it("sem nada rodando, diz isso e mostra o próximo horário", async () => {
    // Uma tela em branco não distingue "nada rodando agora" de "isto aqui
    // está morto". O próximo horário é o que transforma vazio em informação.
    mockResposta(SEM_NADA);

    render(<AoVivo />);

    expect(
      await screen.findByText(/nenhum backup rodando agora/i),
    ).toBeTruthy();
    expect(screen.getByText(/Backup diario 15:00/)).toBeTruthy();
  });

  it("o próximo horário se declara como sendo o da máquina", async () => {
    // O horário de uma política é o relógio de quem executa. Sem a ressalva, a
    // tela mostraria 03:00 do fuso do servidor com a confiança de um dado
    // exato.
    mockResposta(SEM_NADA);

    render(<AoVivo />);

    expect(await screen.findByText(/relógio da máquina/i)).toBeTruthy();
  });

  it("não inventa contagem quando a máquina não mandou", async () => {
    // Um "0 arquivos" na tela seria lido como fato — e o fato é que ainda não
    // se sabe.
    mockResposta({
      ...RODANDO,
      executando: [{ ...RODANDO.executando[0], arquivos: null }],
    });

    render(<AoVivo />);

    await screen.findByText("Copiando para o destino");
    expect(screen.queryByText(/arquivo/i)).toBeNull();
  });

  it("erro de rede não vira tela vermelha", async () => {
    // Este bloco é acessório: o assunto principal — se há backup — está logo
    // acima e continua correto.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("rede caiu");
      }),
    );

    render(<AoVivo />);

    await waitFor(() => {
      expect(screen.queryByRole("region")).toBeNull();
    });
  });

  it("pergunta de novo sozinho, para o vivo continuar vivo", async () => {
    const espiao = vi.fn(
      async () =>
        ({ ok: true, status: 200, json: async () => SEM_NADA }) as Response,
    );
    vi.stubGlobal("fetch", espiao);

    render(<AoVivo />);
    await screen.findByText(/nenhum backup rodando agora/i);
    const primeiras = espiao.mock.calls.length;
    await vi.advanceTimersByTimeAsync(9000);

    expect(espiao.mock.calls.length).toBeGreaterThan(primeiras);
  });
});
