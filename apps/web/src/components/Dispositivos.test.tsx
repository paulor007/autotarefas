import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Dispositivos from "./Dispositivos";

/**
 * Testes da tela de máquinas.
 *
 * O que se protege aqui não é layout: é a recusa de mentir. Botão que não
 * funciona, "conectado" para máquina desligada e "erro" para computador
 * fechado à noite são os três jeitos mais fáceis de uma interface enganar
 * quem confia nela.
 */

const DISPOSITIVO = {
  id: "d1",
  nome: "PC da loja",
  sistema: "Windows 11",
  versao_agente: "0.1.0",
  estado: "ativo" as const,
  impressao: "AAAA-BBBB-CCCC-DDDD",
  pareado_em: "2026-08-25T10:00:00+00:00",
  ultimo_contato: "2026-08-25T10:05:00+00:00",
};

/** Responde por rota, como o servidor faria. */
function mockRotas(
  respostas: Record<string, { corpo: unknown; status?: number }>,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      // Casa pelo FIM da URL primeiro. `/api/dispositivos` também aparece
      // dentro de `/api/dispositivos/d1/consultar`, e casar por conteúdo
      // faria a consulta receber a lista de dispositivos.
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

describe("Dispositivos", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("mostra 'Desligado' para máquina cadastrada e sem canal aberto", async () => {
    // Mostrar "ativo" só porque existe uma linha no banco faria alguém
    // confiar num backup que não vai acontecer.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC da loja", conectado: false, desde: "" },
          ],
          total_conectados: 0,
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("Desligado")).toBeTruthy();
    });
  });

  it("mostra 'Conectado' quando há canal aberto", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            {
              dispositivo_id: "d1",
              nome: "PC da loja",
              conectado: true,
              desde: "2026-08-25T10:00:00+00:00",
            },
          ],
          total_conectados: 1,
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("Conectado")).toBeTruthy();
    });
  });

  it("revogado ganha do estado de conexão", async () => {
    // Um dispositivo revogado que por acaso ainda aparecesse conectado não
    // pode ser mostrado como se estivesse em serviço.
    mockRotas({
      "/api/dispositivos": {
        corpo: { dispositivos: [{ ...DISPOSITIVO, estado: "revogado" }] },
      },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC", conectado: true, desde: "" },
          ],
          total_conectados: 1,
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("Revogado")).toBeTruthy();
    });
  });

  it("máquina desligada vira frase clara, não erro", async () => {
    // Tratar como falha faria a tela acusar problema toda noite, quando o
    // computador da loja está simplesmente fechado.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
      "/consultar": {
        corpo: { detail: "nao ha canal aberto com este dispositivo" },
        status: 409,
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Ver pastas autorizadas/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/está desligada ou sem conexão/i)).toBeTruthy();
    });
  });

  it("avisa quando o dispositivo não tem pasta autorizada", async () => {
    // Um Agente pareado sem pasta autorizada não copia nada, e isso é fácil
    // de confundir com "está funcionando".
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": {
        corpo: {
          conectados: [
            { dispositivo_id: "d1", nome: "PC", conectado: true, desde: "" },
          ],
          total_conectados: 1,
        },
      },
      "/consultar": {
        corpo: {
          dispositivo_id: "d1",
          estado: { ok: true, raizes: [], pode_copiar: false, versao_agente: "0.1.0" },
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Ver pastas autorizadas/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não copiaria nada/i)).toBeTruthy();
    });
    expect(screen.getByText(/no próprio computador/i)).toBeTruthy();
  });

  it("quem só lê não vê botão de parear nem de revogar", async () => {
    // O papel vem do servidor; a tela não pode oferecer o que ele recusaria.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="leitor" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: /Parear nova máquina/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Revogar/i })).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Executar backup agora/i }),
    ).toBeNull();
  });

  it("operador executa mas não pareia", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [DISPOSITIVO] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="operador" />);

    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
    expect(
      screen.getByRole("button", { name: /Executar backup agora/i }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Parear nova máquina/i })).toBeNull();
  });

  it("enquanto carrega, não afirma que não há máquina", async () => {
    // A frase "Nenhuma máquina pareada ainda" aparecia no intervalo entre
    // abrir a tela e o servidor responder — falsa, curta, e exatamente na
    // cara de quem tem máquina pareada.
    let responder: (valor: unknown) => void = () => {};
    const espera = new Promise((pronto) => {
      responder = pronto;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        await espera;
        return {
          ok: true,
          status: 200,
          json: async () =>
            url.includes("conectados")
              ? { conectados: [], total_conectados: 0 }
              : { dispositivos: [DISPOSITIVO] },
        } as Response;
      }),
    );
    render(<Dispositivos papel="dono" />);

    expect(screen.queryByText(/Nenhuma máquina pareada/i)).toBeNull();
    expect(screen.getByText(/Carregando/i)).toBeTruthy();

    responder(null);
    await waitFor(() => {
      expect(screen.getByText("PC da loja")).toBeTruthy();
    });
  });

  it("sem máquina pareada, explica o que falta", async () => {
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(screen.getByText(/Nenhuma máquina pareada ainda/i)).toBeTruthy();
    });
    expect(screen.getByText(/depende do Agente instalado/i)).toBeTruthy();
  });

  it("parear leva ao roteiro de instalação, com o código dentro do comando", async () => {
    // O código sozinho não instala nada. Quem vai proteger a máquina precisa do
    // pacote, do comando e do prazo — e o prazo importa porque o código serve
    // uma vez só.
    mockRotas({
      "/api/dispositivos": { corpo: { dispositivos: [] } },
      "/api/agente/conectados": { corpo: { conectados: [], total_conectados: 0 } },
      "/api/dispositivos/codigo": {
        corpo: {
          codigo: "ABCD-EFGH",
          expira_em: "2026-08-25T10:10:00+00:00",
          validade_minutos: 10,
        },
      },
      "/api/agente/instalador/ficha": {
        corpo: {
          nome: "autotarefas-agente.zip",
          tamanho_bytes: 451000,
          arquivos: 152,
          precisa_de_python: "3.13",
        },
      },
    });
    render(<Dispositivos papel="dono" />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Parear nova máquina/i }),
      ).toBeTruthy();
    });
    await userEvent.click(
      screen.getByRole("button", { name: /Parear nova máquina/i }),
    );

    const comando = await screen.findByText(/instalar\.ps1/);
    expect(comando.textContent).toContain("ABCD-EFGH");
    expect(screen.getByText(/serve uma vez só/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /baixar o agente/i })).toBeTruthy();
  });
});
