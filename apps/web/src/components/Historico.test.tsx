import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Historico from "./Historico";

/**
 * Histórico de execuções na tela.
 *
 * O que se protege aqui é a recusa de mentir por arredondamento. Um backup
 * "com ressalva" pintado de verde esconde as ausências de quem um dia vai
 * restaurar; um histórico vazio com linha de exemplo faz a pessoa achar que
 * algo rodou.
 */

const AGENDADA = {
  id: "e1",
  dispositivo_id: "d1",
  politica_id: "p1",
  origem: "agendamento",
  resultado: "sucesso" as const,
  iniciada_em: "2026-08-25T02:00:00",
  terminada_em: "2026-08-25T02:04:00",
  arquivos: 12,
  bytes_copiados: 4096,
  ressalva: "",
  artefatos: [
    {
      id: "a1",
      nome: "backup_2026-08-25_0200.zip",
      tamanho_bytes: 4096,
      sha256: "a".repeat(64),
      localizacao: "dispositivo",
    },
  ],
};

const COM_RESSALVA = {
  ...AGENDADA,
  id: "e2",
  origem: "manual",
  resultado: "com_ressalva" as const,
  ressalva: "1 arquivo(s) não entraram",
  artefatos: [],
};

function mockHistorico(execucoes: unknown[], status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => ({ execucoes }),
    })) as unknown as typeof fetch,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Histórico", () => {
  it("marca o que rodou pelo horário agendado", async () => {
    // É a linha que separa "pode mandar fazer backup" de "tem backup": ela
    // aconteceu com o navegador fechado, sem ninguém olhando.
    mockHistorico([AGENDADA]);

    render(<Historico />);

    expect(await screen.findByText(/pelo horário agendado/i)).toBeTruthy();
    expect(screen.getByText(/concluído$/i)).toBeTruthy();
  });

  it("não chama de concluído o backup que teve ressalva", async () => {
    mockHistorico([COM_RESSALVA]);

    render(<Historico />);

    expect(await screen.findByText(/concluído com ressalva/i)).toBeTruthy();
    expect(screen.getByText(/1 arquivo\(s\) não entraram/i)).toBeTruthy();
  });

  it("mostra o pacote pelo nome, e diz que ele ficou na máquina", async () => {
    mockHistorico([AGENDADA]);

    render(<Historico />);

    expect(await screen.findByText("backup_2026-08-25_0200.zip")).toBeTruthy();
    expect(screen.getByText(/guardado na própria máquina/i)).toBeTruthy();
  });

  it("histórico vazio é dito como vazio, sem linha de exemplo", async () => {
    mockHistorico([]);

    render(<Historico />);

    expect(
      await screen.findByText(/nenhuma execução registrada ainda/i),
    ).toBeTruthy();
  });

  it("falha ao carregar aparece como falha, e não como histórico vazio", async () => {
    // "Vazio" e "não consegui perguntar" pedem ações diferentes de quem lê.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 500,
        json: async () => ({ detail: "banco fora do ar" }),
      })) as unknown as typeof fetch,
    );

    render(<Historico />);

    await waitFor(() =>
      expect(screen.getByText(/banco fora do ar/i)).toBeTruthy(),
    );
  });

  it("filtra por dispositivo quando recebe um", async () => {
    const espiao = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ execucoes: [] }),
    }));
    vi.stubGlobal("fetch", espiao as unknown as typeof fetch);

    render(<Historico dispositivoId="d1" />);

    await waitFor(() => expect(espiao).toHaveBeenCalled());
    const url = String((espiao.mock.calls[0] as unknown[])[0]);
    expect(url).toContain("dispositivo_id=d1");
  });
});
