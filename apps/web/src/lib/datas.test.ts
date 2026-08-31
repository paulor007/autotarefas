import { describe, expect, it } from "vitest";

import { desdeQuando } from "./datas";


/**
 * "Ha quanto tempo", em palavras.
 *
 * A pergunta do cartao da maquina e "isto esta vivo agora?". Uma data absoluta
 * obriga quem le a fazer a conta com o relogio para responde-la.
 */
describe("desdeQuando", () => {
  const AGORA = new Date("2026-08-30T22:00:00Z");

  it("segundos viram 'agora há pouco'", () => {
    expect(desdeQuando("2026-08-30T21:59:48Z", AGORA)).toBe("agora há pouco");
  });

  it("minutos são contados", () => {
    expect(desdeQuando("2026-08-30T21:43:00Z", AGORA)).toBe("há 17 minutos");
  });

  it("horas são contadas, com plural certo", () => {
    expect(desdeQuando("2026-08-30T21:00:00Z", AGORA)).toBe("há 1 hora");
    expect(desdeQuando("2026-08-30T17:00:00Z", AGORA)).toBe("há 5 horas");
  });

  it("acima de um dia volta para a data", () => {
    // "há 37 dias" é pior do que a data: a pessoa perde a referência de
    // quando foi.
    expect(desdeQuando("2026-07-24T10:00:00Z", AGORA)).toContain("2026");
  });

  it("relógios diferentes não produzem tempo negativo", () => {
    // O servidor pode estar alguns segundos à frente. "há -3 segundos" seria
    // pior do que arredondar para agora.
    expect(desdeQuando("2026-08-30T22:00:05Z", AGORA)).toBe("agora há pouco");
  });

  it("sem data, diz que não houve contato", () => {
    expect(desdeQuando("")).toBe("sem contato");
  });
});
