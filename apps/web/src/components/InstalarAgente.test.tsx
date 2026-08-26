import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InstalarAgente from "./InstalarAgente";
import { ENDERECO_DO_INSTALADOR } from "../lib/plataforma";

/**
 * Instalação do Agente.
 *
 * A tela tem dois roteiros, e o que se protege aqui é ela mostrar **o do
 * servidor que está atendendo**. Prometer "dois cliques" quando o servidor só
 * tem o pacote com Python é a mentira mais cara desta tela: a pessoa baixaria,
 * clicaria, e nada aconteceria.
 */

const CODIGO = {
  codigo: "ABC123",
  expira_em: "2026-08-25T12:00:00+00:00",
  validade_minutos: 15,
};

const COM_EXE = {
  formato: "exe",
  nome: "AutoTarefas-Agente.exe",
  tamanho_bytes: 30_450_854,
  arquivos: 1,
  precisa_de_python: "",
};

const SO_ZIP = {
  formato: "zip",
  nome: "autotarefas-agente.zip",
  tamanho_bytes: 451_000,
  arquivos: 152,
  precisa_de_python: "3.13",
  pasta_do_pacote: "AutoTarefas-Agente",
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

describe("Instalação do Agente", () => {
  it("o botão de baixar leva o código junto", async () => {
    // É o carimbo que dispensa a pessoa de digitar endereço e código. Sem o
    // código na URL, o executável baixado não saberia para onde ligar.
    mockFicha(COM_EXE);

    render(<InstalarAgente codigo={CODIGO} />);

    const link = screen.getByRole("link", { name: /baixar o agente/i });
    expect(link.getAttribute("href")).toBe(`${ENDERECO_DO_INSTALADOR}?codigo=ABC123`);
  });

  describe("quando o servidor tem o executável", () => {
    it("promete dois cliques, e não menciona terminal", async () => {
      mockFicha(COM_EXE);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText(/dois cliques no arquivo baixado/i)).toBeTruthy();
      expect(screen.queryByText(/instalar\.ps1/)).toBeNull();
      expect(screen.queryByText(/Python/)).toBeNull();
    });

    it("diz que não precisa instalar mais nada", async () => {
      mockFicha(COM_EXE);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText(/não precisa instalar mais nada/i)).toBeTruthy();
      expect(screen.getByText(/AutoTarefas-Agente\.exe/)).toBeTruthy();
    });

    it("mantém a conferência da impressão digital", async () => {
      // É o único momento em que a pessoa olha duas telas — e não dá para
      // evitar: é o que impede um servidor comprometido de se passar pela
      // máquina dela.
      mockFicha(COM_EXE);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText(/impressão digital/i)).toBeTruthy();
    });

    it("diz que a autorização de pasta é dada na própria máquina", async () => {
      mockFicha(COM_EXE);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText(/na própria máquina/i)).toBeTruthy();
    });

    it("diz que o arquivo é portátil, e que serve para um computador só", async () => {
      // O caso comum numa empresa pequena: a pessoa navega no notebook, mas a
      // máquina com os arquivos é a do balcão. O carimbo viaja junto — e o
      // código é de uso único, então um arquivo protege uma máquina.
      mockFicha(COM_EXE);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText(/copiá-lo para outro computador/i)).toBeTruthy();
      expect(screen.getByText(/uma vez só/i)).toBeTruthy();
    });
  });

  describe("quando o servidor só tem o pacote com Python", () => {
    it("diz que o instalador de um clique ainda não foi gerado", async () => {
      // Esconder isso faria a pessoa esperar um duplo clique que não existe.
      mockFicha(SO_ZIP);

      render(
        <InstalarAgente codigo={CODIGO} />,
      );

      expect(
        await screen.findByText(/ainda não gerou o instalador de um clique/i),
      ).toBeTruthy();
      expect(screen.getByText(/construir_agente\.py/)).toBeTruthy();
    });

    it("avisa que precisa de Python antes, e não na terceira tela", async () => {
      mockFicha(SO_ZIP);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText(/precisa de Python 3\.13/i)).toBeTruthy();
    });

    it("diz em qual pasta abrir o terminal", async () => {
      // O extrator do Windows cria uma pasta em volta da que vem no ZIP. Sem
      // este aviso, o comando não é encontrado — e foi exatamente o que
      // aconteceu na primeira homologação manual.
      mockFicha(SO_ZIP);

      render(<InstalarAgente codigo={CODIGO} />);

      expect(await screen.findByText("AutoTarefas-Agente")).toBeTruthy();
      expect(screen.getByText(/pasta em volta/i)).toBeTruthy();
    });

    it("mostra o comando com o código, e o desvio da política de execução", async () => {
      mockFicha(SO_ZIP);

      render(<InstalarAgente codigo={CODIGO} />);

      const comando = await screen.findByText(/instalar\.ps1/);
      expect(comando.textContent).toContain("-Codigo ABC123");
      expect(screen.getByText(/ExecutionPolicy Bypass/)).toBeTruthy();
    });
  });

  it("falha ao ler a ficha não some com o botão de baixar", async () => {
    // O download continua lá; o que faltou foi a descrição dele.
    mockFicha({ detail: "não foi possível montar o pacote" }, false);

    render(<InstalarAgente codigo={CODIGO} />);

    await waitFor(() =>
      expect(screen.getByText(/não foi possível montar o pacote/i)).toBeTruthy(),
    );
    expect(screen.getByRole("link", { name: /baixar o agente/i })).toBeTruthy();
  });
});
