import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Restauracao from "./Restauracao";

/**
 * Restauração guiada.
 *
 * O que se protege aqui é a tela não virar um jeito bonito de perder arquivo.
 * Três coisas precisam continuar verdadeiras:
 *
 * 1. o conteúdo do pacote aparece **antes** de qualquer escrita;
 * 2. sobrescrita bloqueada é dita como bloqueio, e nada é anunciado como feito;
 * 3. restauração incompleta **não** se apresenta como sucesso.
 */

const PACOTES = {
  ok: true,
  pacotes: [
    { nome: "backup_2026-08-25_0200.zip", tamanho_bytes: 4096, criado_em: "2026-08-25T02:00" },
    { nome: "backup_2026-08-24_0200.zip", tamanho_bytes: 2048, criado_em: "2026-08-24T02:00" },
  ],
  tem_pasta_autorizada: true,
};

const ESTADO = {
  dispositivo_id: "d1",
  estado: {
    ok: true,
    pode_copiar: true,
    raizes: ["C:\\Loja\\Dados"],
  },
};

const CONTEUDO = {
  ok: true,
  pacote: "backup_2026-08-25_0200.zip",
  conteudo: [
    { arquivo: "docs/contrato.txt", neste_pacote: "sim", onde: "" },
    {
      arquivo: "docs/nota.txt",
      neste_pacote: "nao",
      onde: "backup_2026-08-24_0200.zip",
    },
  ],
};

/** Responde por rota, como o servidor faria. */
function mockRotas(respostas: Record<string, unknown>) {
  const espiao = vi.fn(async (url: string, opcoes?: RequestInit) => {
    void opcoes;
    const rotas = Object.keys(respostas);
    const chave =
      rotas.find((rota) => url.endsWith(rota)) ??
      rotas.find((rota) => url.includes(rota));
    const corpo = chave ? respostas[chave] : { detail: "rota não simulada" };
    return {
      ok: Boolean(chave),
      status: chave ? 200 : 404,
      json: async () => corpo,
    } as Response;
  });
  vi.stubGlobal("fetch", espiao as unknown as typeof fetch);
  return espiao;
}

function montar() {
  return render(
    <Restauracao
      dispositivoId="d1"
      nomeDoDispositivo="PC da loja"
      aoFechar={() => {}}
    />,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Restauração guiada", () => {
  it("lista os pacotes que estão na máquina", async () => {
    // Vem do dispositivo, e não do banco: listar do banco ofereceria para
    // restaurar um pacote que alguém já apagou.
    mockRotas({ "/pacotes": PACOTES, "/consultar": ESTADO });

    montar();

    expect(await screen.findByText("backup_2026-08-25_0200.zip")).toBeTruthy();
    expect(screen.getByText("backup_2026-08-24_0200.zip")).toBeTruthy();
  });

  it("mostra o conteúdo do pacote antes de escrever qualquer coisa", async () => {
    const espiao = mockRotas({
      "/pacotes": PACOTES,
      "/consultar": ESTADO,
      "/pacote": CONTEUDO,
    });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));

    expect(await screen.findByText("docs/contrato.txt")).toBeTruthy();
    const chamadas = espiao.mock.calls.map((c) => String(c[0]));
    expect(chamadas.some((url) => url.endsWith("/restaurar"))).toBe(false);
  });

  it("avisa que um arquivo está em pacote anterior", async () => {
    // Um pacote incremental não se sustenta sozinho, e quem vai restaurar
    // precisa saber disso antes de concluir que recuperou tudo.
    mockRotas({ "/pacotes": PACOTES, "/consultar": ESTADO, "/pacote": CONTEUDO });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));

    expect(
      await screen.findByText(/está em backup_2026-08-24_0200\.zip/i),
    ).toBeTruthy();
  });

  it("só oferece como destino as pastas autorizadas na máquina", async () => {
    mockRotas({ "/pacotes": PACOTES, "/consultar": ESTADO, "/pacote": CONTEUDO });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));

    const seletor = (await screen.findByLabelText(
      /pasta autorizada de destino/i,
    )) as HTMLSelectElement;
    expect([...seletor.options].map((o) => o.value)).toEqual(["C:\\Loja\\Dados"]);
  });

  it("máquina sem pasta autorizada diz o motivo, e não uma lista vazia", async () => {
    mockRotas({
      "/pacotes": { ok: true, pacotes: [], tem_pasta_autorizada: false },
      "/consultar": { dispositivo_id: "d1", estado: { ok: true, raizes: [] } },
    });

    montar();

    expect(
      await screen.findByText(/não tem pasta autorizada/i),
    ).toBeTruthy();
  });

  it("sobrescrita bloqueada é dita como bloqueio, sem nome de exceção", async () => {
    // A frase útil é a que diz o que resolver. "ProtecaoBloqueou" serve ao log
    // da máquina, não a quem está olhando a tela.
    mockRotas({
      "/pacotes": PACOTES,
      "/consultar": ESTADO,
      "/pacote": CONTEUDO,
      "/restaurar": {
        ok: false,
        erro: "ProtecaoBloqueou: nenhum backup encontrado em backups. Faca um backup antes. A acao 'sobrescrever_na_restauracao' foi bloqueada.",
      },
    });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));
    await userEvent.click(await screen.findByRole("button", { name: /restaurar$/i }));

    const aviso = await screen.findByText(/foi bloqueada/i);
    expect(aviso.textContent).not.toContain("ProtecaoBloqueou");
    expect(screen.queryByText(/restauração concluída/i)).toBeNull();
  });

  it("restauração incompleta não é anunciada como sucesso", async () => {
    mockRotas({
      "/pacotes": PACOTES,
      "/consultar": ESTADO,
      "/pacote": CONTEUDO,
      "/restaurar": {
        ok: true,
        restaurados: ["docs/contrato.txt"],
        ja_existiam: [],
        recusados: [],
        faltando: ["docs/nota.txt"],
        corrompidos: [],
        protecao: "",
      },
    });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));
    await userEvent.click(await screen.findByRole("button", { name: /restaurar$/i }));

    expect(await screen.findByText(/INCOMPLETA/i)).toBeTruthy();
    expect(screen.queryByText(/restauração concluída/i)).toBeNull();
  });

  it("restauração completa é dita como completa", async () => {
    mockRotas({
      "/pacotes": PACOTES,
      "/consultar": ESTADO,
      "/pacote": CONTEUDO,
      "/restaurar": {
        ok: true,
        restaurados: ["docs/contrato.txt", "docs/nota.txt"],
        ja_existiam: [],
        recusados: [],
        faltando: [],
        corrompidos: [],
      },
    });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));
    await userEvent.click(await screen.findByRole("button", { name: /restaurar$/i }));

    expect(await screen.findByText(/restauração concluída/i)).toBeTruthy();
  });

  it("máquina desligada é dita como desligada, e nada foi alterado", async () => {
    // 409 é situação normal — o computador da loja está fechado à noite.
    const espiao = vi.fn(async (url: string) => {
      if (String(url).endsWith("/restaurar")) {
        return {
          ok: false,
          status: 409,
          json: async () => ({ detail: "nao ha canal aberto com este dispositivo" }),
        } as Response;
      }
      const corpo = String(url).endsWith("/pacotes")
        ? PACOTES
        : String(url).endsWith("/consultar")
          ? ESTADO
          : CONTEUDO;
      return { ok: true, status: 200, json: async () => corpo } as Response;
    });
    vi.stubGlobal("fetch", espiao as unknown as typeof fetch);

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));
    await userEvent.click(await screen.findByRole("button", { name: /restaurar$/i }));

    await waitFor(() =>
      expect(screen.getByText(/está desligada.*nada foi alterado/i)).toBeTruthy(),
    );
  });

  it("pede a conferência de backup só quando a substituição foi marcada", async () => {
    // A tela não conhece pasta nenhuma da máquina: ela pede "confira nos meus
    // pacotes", e o Agente resolve qual pasta é essa.
    const espiao = mockRotas({
      "/pacotes": PACOTES,
      "/consultar": ESTADO,
      "/pacote": CONTEUDO,
      "/restaurar": { ok: true, restaurados: ["docs/contrato.txt"] },
    });

    montar();
    await userEvent.click(await screen.findByText("backup_2026-08-25_0200.zip"));
    await userEvent.click(await screen.findByRole("checkbox"));
    await userEvent.click(await screen.findByRole("button", { name: /restaurar$/i }));

    const pedido = espiao.mock.calls.find((c) =>
      String(c[0]).endsWith("/restaurar"),
    );
    const corpo = JSON.parse(String((pedido?.[1] as RequestInit)?.body));
    expect(corpo.sobrescrever).toBe(true);
    expect(corpo.conferir_backup).toBe(true);
    expect(corpo.pacote).toBe("backup_2026-08-25_0200.zip");
  });
});
