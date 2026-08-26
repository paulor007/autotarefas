import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Auditoria from "./Auditoria";

/**
 * Trilha de auditoria na tela.
 *
 * A trilha é encadeada por hash justamente para dispensar confiança cega.
 * Mostrar as linhas sem dizer se elas ainda batem devolveria o problema para
 * quem lê — por isso o selo de integridade é a primeira coisa da seção, e uma
 * trilha alterada tem que aparecer como alterada.
 */

const LINHA = {
  id: "a1",
  acao: "backup.pedido",
  alvo: "PC da loja",
  detalhe: "",
  quando: "2026-08-25T02:00:00+00:00",
  dispositivo_id: "d1",
};

function mockTrilha(corpo: unknown, ok = true): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok,
      status: ok ? 200 : 500,
      json: async () => corpo,
    })) as unknown as typeof fetch,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Auditoria", () => {
  it("diz que a trilha está íntegra quando ela está", async () => {
    mockTrilha({ integra: true, explicacao: "", linhas: [LINHA] });

    render(<Auditoria />);

    expect(await screen.findByText(/trilha íntegra/i)).toBeTruthy();
    expect(screen.getByText("backup.pedido")).toBeTruthy();
  });

  it("trilha alterada aparece como alterada, com o motivo", async () => {
    // O encadeamento só serve se a quebra for visível. Um selo que diz "ok"
    // sempre é pior do que nenhum selo.
    mockTrilha({
      integra: false,
      explicacao: "a linha a1 nao confere com a anterior",
      linhas: [LINHA],
    });

    render(<Auditoria />);

    expect(await screen.findByText(/trilha ALTERADA/i)).toBeTruthy();
    expect(screen.getByText(/nao confere com a anterior/i)).toBeTruthy();
  });

  it("trilha vazia diz o que ela guarda, em vez de ficar em branco", async () => {
    mockTrilha({ integra: true, explicacao: "", linhas: [] });

    render(<Auditoria />);

    expect(await screen.findByText(/nada registrado ainda/i)).toBeTruthy();
  });

  it("falha ao carregar não é confundida com trilha vazia", async () => {
    mockTrilha({ detail: "banco fora do ar" }, false);

    render(<Auditoria />);

    expect(await screen.findByText(/banco fora do ar/i)).toBeTruthy();
    expect(screen.queryByText(/trilha íntegra/i)).toBeNull();
  });
});
