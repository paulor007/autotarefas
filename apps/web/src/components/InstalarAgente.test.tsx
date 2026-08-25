import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InstalarAgente from "./InstalarAgente";
import { ENDERECO_DO_INSTALADOR } from "../lib/plataforma";

/**
 * Instalação guiada do Agente.
 *
 * O que se protege aqui é o botão não ser decorativo. "Baixar o Agente" tem que
 * apontar para um pacote de verdade, e a tela tem que dizer o que vem dentro e
 * o que a máquina precisa ter — antes do clique, não depois.
 */

const CODIGO = {
  codigo: "ABC123",
  expira_em: "2026-08-25T12:00:00+00:00",
  validade_minutos: 15,
};

const FICHA = {
  nome: "autotarefas-agente.zip",
  tamanho_bytes: 451_000,
  arquivos: 152,
  precisa_de_python: "3.13",
};

function mockFicha(corpo: unknown, ok = true): void {
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

describe("Instalação guiada do Agente", () => {
  it("o botão de baixar aponta para o pacote de verdade", async () => {
    // Botão que não funciona é a mentira mais fácil de cometer numa interface,
    // e a mais cara de descobrir.
    mockFicha(FICHA);

    render(<InstalarAgente codigo={CODIGO} />);

    const link = screen.getByRole("link", { name: /baixar o agente/i });
    expect(link.getAttribute("href")).toBe(ENDERECO_DO_INSTALADOR);
  });

  it("diz o tamanho e o que vem dentro antes do clique", async () => {
    mockFicha(FICHA);

    render(<InstalarAgente codigo={CODIGO} />);

    expect(await screen.findByText(/autotarefas-agente\.zip/)).toBeTruthy();
    expect(screen.getByText(/152 arquivos/)).toBeTruthy();
  });

  it("avisa que precisa de Python antes, e não na terceira tela", async () => {
    // Requisito escondido até o meio do caminho vira armadilha.
    mockFicha(FICHA);

    render(<InstalarAgente codigo={CODIGO} />);

    expect(await screen.findByText(/precisa de Python 3\.13/i)).toBeTruthy();
  });

  it("monta o comando com o código e o endereço deste Live", async () => {
    mockFicha(FICHA);

    render(<InstalarAgente codigo={CODIGO} />);

    const comando = screen.getByText(/instalar\.ps1/);
    expect(comando.textContent).toContain("-Codigo ABC123");
    expect(comando.textContent).toContain(window.location.origin);
  });

  it("diz que a autorização de pasta é dada na própria máquina", async () => {
    // É a regra que o produto inteiro sustenta: nenhuma tela na nuvem concede
    // acesso ao disco de ninguém.
    mockFicha(FICHA);

    render(<InstalarAgente codigo={CODIGO} />);

    expect(screen.getByText(/na própria máquina/i)).toBeTruthy();
  });

  it("falha ao ler a ficha não some com o botão de baixar", async () => {
    // O pacote continua lá; o que faltou foi a descrição dele.
    mockFicha({ detail: "não foi possível montar o pacote" }, false);

    render(<InstalarAgente codigo={CODIGO} />);

    await waitFor(() =>
      expect(screen.getByText(/não foi possível montar o pacote/i)).toBeTruthy(),
    );
    expect(screen.getByRole("link", { name: /baixar o agente/i })).toBeTruthy();
  });
});
