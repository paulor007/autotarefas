import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DetalheDaExecucao from "./DetalheDaExecucao";

/**
 * A tela que responde "como eu sei?".
 *
 * A lista do histórico responde "aconteceu". Esta responde a pergunta
 * seguinte, e é ela que decide se alguém confia. O que se protege aqui é a
 * diferença entre um resumo mais longo e uma evidência: a soma inteira, e a
 * distinção entre "chegou" e "chegou e foi conferido".
 */

const BASE = {
  id: "e1",
  dispositivo_id: "d1",
  politica_id: "p1",
  origem: "agendamento",
  resultado: "sucesso" as const,
  iniciada_em: "2026-08-30T03:00:00",
  terminada_em: "2026-08-30T03:04:00",
  arquivos: 12,
  bytes_copiados: 2_097_152,
  ressalva: "",
  maquina: "SERVIDOR-01",
  artefatos: [
    {
      id: "a1",
      nome: "backup_2026-08-30_0300.zip",
      tamanho_bytes: 2_097_152,
      sha256: "b".repeat(64),
      localizacao: "dispositivo",
      entregas: [
        {
          tipo: "s3",
          destino: "Amazon S3 · balde backups-demo",
          objeto: "demo/backup_2026-08-30_0300.zip",
          conferido_no_destino: true,
        },
      ],
      nuvem_pendente: false,
      nuvem_em: "2026-08-30T03:05:00",
      nuvem_chave: "demo/backup_2026-08-30_0300.zip",
      nuvem_erro: "",
    },
  ],
  politica: {
    id: "p1",
    nome: "Backup diario 03:00",
    origens: ["/dados"],
    destino: { tipo: "nuvem", caminho: "" },
    agendamento: { tipo: "diario", hora: "03:00" },
    retencao: { diarias: 7, semanais: 4, mensais: 12 },
    protege_de_verdade: true,
  },
  trilha: [
    {
      acao: "execucao.registrada",
      alvo: "backup_2026-08-30_0300.zip",
      detalhe: "sucesso",
      quando: "2026-08-30T03:04:10",
      hash_atual: "f".repeat(64),
    },
  ],
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
});

describe("detalhe da execução", () => {
  it("mostra a soma inteira, e não um pedaço dela", async () => {
    // É a soma que alguém usa para conferir por fora. Cortar nos oito
    // primeiros caracteres transformaria a evidência num enfeite com cara de
    // evidência.
    mockResposta(BASE);

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(await screen.findByText(new RegExp("b".repeat(64)))).toBeTruthy();
  });

  it("distingue chegou de chegou e foi conferido", async () => {
    mockResposta(BASE);

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(
      await screen.findByText(/lido de volta no destino e conferido/i),
    ).toBeTruthy();
  });

  it("entrega sem conferência não é apresentada como conferida", async () => {
    mockResposta({
      ...BASE,
      artefatos: [
        {
          ...BASE.artefatos[0],
          entregas: [
            {
              tipo: "rede",
              destino: "pasta de rede",
              conferido_no_destino: false,
            },
          ],
        },
      ],
    });

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(
      await screen.findByText(/não há confirmação de conferência/i),
    ).toBeTruthy();
  });

  it("mostra o que a política pediu, para haver contra o que comparar", async () => {
    // "12 arquivos copiados" não diz se copiou o que devia sem o outro lado
    // da conta.
    mockResposta(BASE);

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(await screen.findByText("Backup diario 03:00")).toBeTruthy();
    expect(screen.getByText("/dados")).toBeTruthy();
    expect(screen.getByText(/7 diários/)).toBeTruthy();
  });

  it("pacote esperando a nuvem é dito como esperando", async () => {
    mockResposta({
      ...BASE,
      artefatos: [
        {
          ...BASE.artefatos[0],
          entregas: [],
          nuvem_pendente: true,
          nuvem_em: "",
          nuvem_chave: "",
        },
      ],
    });

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(
      await screen.findByText(/aguardando envio para a nuvem/i),
    ).toBeTruthy();
  });

  it("execução sem pacote não inventa um", async () => {
    mockResposta({ ...BASE, artefatos: [], resultado: "falha" });

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(await screen.findByText(/não produziu pacote/i)).toBeTruthy();
  });

  it("mostra a trilha encadeada", async () => {
    mockResposta(BASE);

    render(<DetalheDaExecucao execucaoId="e1" aoFechar={() => {}} />);

    expect(await screen.findByText("execucao.registrada")).toBeTruthy();
  });
});
