import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SpreadsheetProfileMapping from "./SpreadsheetProfileMapping";
import type { ProfileInfo } from "../lib/spreadsheets";

/**
 * Tela de mapeamento de perfis.
 *
 * O que ela precisa garantir: as opções vêm SEMPRE do backend (perfis e
 * colunas), nada é adivinhado, e um campo obrigatório sem coluna impede o
 * envio antes de gastar uma ida ao servidor.
 */

const PERFIL: ProfileInfo = {
  id: "cadastro_contatos",
  title: "Cadastro de contatos (pessoas ou empresas)",
  version: 1,
  summary: "Regras estruturais de uma lista de contatos.",
  fields: [
    { name: "nome", required: true, doc: "Nome da pessoa ou razão social." },
    { name: "email", required: false, doc: "Endereço de e-mail principal." },
    { name: "cpf", required: false, doc: "CPF, com ou sem máscara." },
  ],
};

const COLUNAS = ["Nome Completo", "Contato principal", "Documento"];

function montar(
  over: Partial<Parameters<typeof SpreadsheetProfileMapping>[0]> = {},
) {
  const props = {
    profiles: [PERFIL],
    profile: PERFIL,
    columns: COLUNAS,
    mapping: {} as Record<string, string>,
    busy: false,
    error: null,
    onPick: vi.fn(),
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    onBack: vi.fn(),
    ...over,
  };
  return { props, ...render(<SpreadsheetProfileMapping {...props} />) };
}

describe("SpreadsheetProfileMapping", () => {
  it("lista os perfis vindos do backend", () => {
    montar();
    expect(screen.getByText(/Cadastro de contatos/)).toBeTruthy();
    expect(screen.getByText(/versão 1/)).toBeTruthy();
  });

  it("mostra estado vazio quando não há perfis", () => {
    montar({ profiles: [], profile: null });
    expect(screen.getByText(/Nenhum perfil disponível/)).toBeTruthy();
  });

  it("oferece apenas as colunas da análise atual", () => {
    montar();
    const select = screen.getByLabelText(/nome/i) as HTMLSelectElement;
    const opcoes = [...select.options].map((o) => o.value).filter(Boolean);
    expect(opcoes).toEqual(COLUNAS);
  });

  it("distingue campo obrigatório de opcional", () => {
    montar();
    expect(screen.getByText("obrigatório")).toBeTruthy();
    expect(screen.getAllByText("opcional")).toHaveLength(2);
  });

  it("exibe a documentação de cada campo", () => {
    montar();
    expect(screen.getByText(/Nome da pessoa ou razão social/)).toBeTruthy();
  });

  it("opcional oferece 'Não usar'", () => {
    montar();
    const select = screen.getByLabelText(/email/i) as HTMLSelectElement;
    expect(select.options[0].textContent).toBe("Não usar");
  });

  it("bloqueia o envio enquanto falta um obrigatório", () => {
    montar({ mapping: { email: "Contato principal" } });
    const botao = screen.getByRole("button", {
      name: /Gerar schema do perfil/i,
    });
    expect((botao as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Falta relacionar: nome/)).toBeTruthy();
  });

  it("libera o envio com o obrigatório preenchido", () => {
    montar({ mapping: { nome: "Nome Completo" } });
    const botao = screen.getByRole("button", {
      name: /Gerar schema do perfil/i,
    });
    expect((botao as HTMLButtonElement).disabled).toBe(false);
  });

  it("avisa quando duas regras usam a mesma coluna", () => {
    montar({ mapping: { nome: "Nome Completo", cpf: "Nome Completo" } });
    expect(screen.getByRole("alert").textContent).toContain("mais de um campo");
    const botao = screen.getByRole("button", {
      name: /Gerar schema do perfil/i,
    });
    expect((botao as HTMLButtonElement).disabled).toBe(true);
  });

  it("propaga a escolha de coluna", async () => {
    const { props } = montar();
    await userEvent.selectOptions(
      screen.getByLabelText(/nome/i),
      "Nome Completo",
    );
    expect(props.onChange).toHaveBeenCalledWith("nome", "Nome Completo");
  });

  it("propaga a escolha de perfil", async () => {
    const { props } = montar({ profile: null });
    await userEvent.click(screen.getByRole("radio"));
    expect(props.onPick).toHaveBeenCalledWith("cadastro_contatos");
  });

  it("envia o mapeamento válido", async () => {
    const { props } = montar({ mapping: { nome: "Nome Completo" } });
    await userEvent.click(
      screen.getByRole("button", { name: /Gerar schema/i }),
    );
    expect(props.onSubmit).toHaveBeenCalled();
  });

  it("mostra o erro do backend sem esconder a tela", () => {
    montar({
      mapping: { nome: "Nome Completo" },
      error: "coluna(s) nao encontrada(s) na planilha: Fantasma",
    });
    expect(screen.getByRole("alert").textContent).toContain("nao encontrada");
    // a tela continua utilizável para corrigir
    expect(screen.getByLabelText(/nome/i)).toBeTruthy();
  });

  it("desabilita tudo enquanto ocupado", () => {
    montar({ mapping: { nome: "Nome Completo" }, busy: true });
    expect(
      (
        screen.getByRole("button", {
          name: /Gerando schema/i,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect((screen.getByLabelText(/nome/i) as HTMLSelectElement).disabled).toBe(
      true,
    );
  });

  it("não mostra campos antes de escolher um perfil", () => {
    montar({ profile: null });
    expect(screen.queryByLabelText(/nome/i)).toBeNull();
  });

  it("permite voltar", async () => {
    const { props } = montar();
    await userEvent.click(screen.getByRole("button", { name: /Voltar/i }));
    expect(props.onBack).toHaveBeenCalled();
  });
});
