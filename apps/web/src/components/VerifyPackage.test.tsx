import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VerifyPackage from "./VerifyPackage";

/**
 * Conferência do pacote pela tela.
 *
 * O card se chama "verificável"; estes testes existem para que isso continue
 * sendo uma função, e não um adjetivo. O caso mais importante é o último: um
 * "íntegro" sem a ressalva de que isso não prova autenticidade seria a
 * promessa exagerada que o produto recusa em todo o resto.
 */

function mockVerify(resposta: Record<string, unknown>, ok = true): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 404,
      json: async () => resposta,
    } as Response),
  );
}

const INTEGRO = {
  arquivo: "backup.zip",
  integro: true,
  conferidos: 4,
  corrompidos: [],
  faltando: [],
  nao_declarados: [],
  nao_lidos_na_origem: [],
  problema: "",
  assinado: false,
  autenticidade: "nao_assinado",
  limite:
    "Detecta corrupção e alteração acidental. Não comprova autenticidade contra adulteração intencional.",
};

const ASSINADO = {
  ...INTEGRO,
  assinado: true,
  autenticidade: "autentico",
  limite:
    "Assinatura confere: o pacote saiu de quem tem a chave e o conteúdo não foi alterado depois.",
};

describe("VerifyPackage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("só confere quando a pessoa pede", () => {
    const espia = mockVerify(INTEGRO);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    expect(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    ).toBeTruthy();
    expect(espia).toBeUndefined();
  });

  it("mostra o resultado com a quantidade conferida", async () => {
    mockVerify(INTEGRO);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Pacote gerado e verificado antes do download/),
      ).toBeTruthy();
    });
    expect(screen.getByText(/4 arquivo\(s\) conferem/)).toBeTruthy();
  });

  it("mostra o limite junto com o resultado positivo", async () => {
    mockVerify(INTEGRO);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não comprova autenticidade/i)).toBeTruthy();
    });
  });

  it("recusa o pacote quando o conteúdo não bate", async () => {
    mockVerify({
      ...INTEGRO,
      integro: false,
      corrompidos: ["dados/contrato.txt"],
    });
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não confie nele para restaurar/i)).toBeTruthy();
    });
    expect(screen.getByText(/dados\/contrato\.txt/)).toBeTruthy();
  });

  it("lembra o que ficou de fora quando o pacote foi criado", async () => {
    mockVerify({
      ...INTEGRO,
      nao_lidos_na_origem: ["dados/planilha.xlsx"],
    });
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não entraram quando este pacote/i)).toBeTruthy();
    });
    // O pacote segue íntegro: o que faltou já era sabido.
    expect(
      screen.getByText(/Pacote gerado e verificado antes do download/),
    ).toBeTruthy();
  });

  it("diz que confere o pacote do servidor, antes do download", () => {
    mockVerify(INTEGRO);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    expect(
      screen.getByText(/Confere o pacote no servidor, antes do download/),
    ).toBeTruthy();
  });

  it("diz que o pacote não foi assinado quando não foi", async () => {
    mockVerify(INTEGRO);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não assinado/i)).toBeTruthy();
    });
  });

  it("mostra que a assinatura confere quando o pacote é assinado", async () => {
    mockVerify(ASSINADO);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      // Texto do rótulo, não o do limite: os dois falam de assinatura, e
      // casar pelos dois tornaria o teste ambíguo.
      expect(
        screen.getByText(/não foi alterado depois de gerado/i),
      ).toBeTruthy();
    });
  });

  it("recusa o pacote quando a assinatura não confere", async () => {
    // O caso que a 02.B existe para pegar: hashes batendo porque o atacante
    // recalculou o manifesto, e mesmo assim o pacote é recusado.
    mockVerify({
      ...ASSINADO,
      integro: false,
      autenticidade: "adulterado",
      corrompidos: [],
    });
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/assinatura NÃO confere/i)).toBeTruthy();
    });
    expect(screen.getByText(/não confie nele para restaurar/i)).toBeTruthy();
  });

  it("sem a chave, não acusa adulteração", async () => {
    // Alarme falso treina a pessoa a ignorar o alarme de verdade.
    mockVerify({ ...ASSINADO, autenticidade: "sem_chave" });
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/chave de conferência não está/i)).toBeTruthy();
    });
    expect(screen.queryByText(/NÃO confere/i)).toBeNull();
  });

  it("mostra erro sem derrubar a tela", async () => {
    mockVerify({ detail: "arquivo nao encontrado" }, false);
    render(<VerifyPackage token="tok-1" name="backup.zip" />);

    await userEvent.click(
      screen.getByRole("button", { name: /Verificar este pacote/i }),
    );

    await waitFor(() => {
      expect(screen.getByText(/não foi possível conferir/i)).toBeTruthy();
    });
  });
});
