import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AvisoDePrivacidade from "./AvisoDePrivacidade";

/**
 * O aviso que fecha a lacuna (2) do RF-GOV-003.
 *
 * Cada asserção aqui corresponde a um item que a DP-05 exige que a pessoa
 * saiba **antes** de enviar um arquivo. Não são checagens de texto por gosto
 * de checar texto: se uma delas cair porque alguém reescreveu o aviso, o
 * requisito voltou a estar descoberto, e é isso que o teste protege.
 */

describe("AvisoDePrivacidade", () => {
  it("diz para que serve o processamento", () => {
    render(<AvisoDePrivacidade />);

    expect(
      screen.getByText(/demonstrar a automação em funcionamento/i),
    ).toBeTruthy();
  });

  it("diz que o arquivo e o resultado somem em 15 minutos, e o que sobra", () => {
    render(<AvisoDePrivacidade />);

    expect(screen.getByText(/apagados em 15\s*minutos/i)).toBeTruthy();
    // A outra metade da verdade: sem ela o aviso prometeria que nada
    // sobrevive aos 15 minutos, e o log do servidor sobrevive.
    expect(
      screen.getByText(/evento da execução em log mascarado, por\s*30\s*dias/i),
    ).toBeTruthy();
  });

  it("aponta os arquivos de exemplo como alternativa", () => {
    render(<AvisoDePrivacidade />);

    expect(screen.getByText(/arquivos de exemplo/i)).toBeTruthy();
  });

  it("recomenda não enviar dados pessoais desnecessários", () => {
    render(<AvisoDePrivacidade />);

    expect(
      screen.getByText(/não envie dados pessoais que não sejam necessários/i),
    ).toBeTruthy();
  });

  it("separa o ambiente público da instalação privada", () => {
    render(<AvisoDePrivacidade />);

    expect(screen.getByText(/Este é o ambiente público/i)).toBeTruthy();
    expect(screen.getByText(/instalação privada da empresa/i)).toBeTruthy();
  });

  it("é uma nota rotulada, encontrável por leitor de tela", () => {
    render(<AvisoDePrivacidade />);

    expect(
      screen.getByRole("note", { name: "Privacidade e retenção" }),
    ).toBeTruthy();
  });
});
