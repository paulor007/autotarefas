import "@testing-library/react";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// O jsdom nao rola pagina: `window.scrollTo` existe so para reclamar. Como a
// navegacao do produto rola para o topo a cada troca de tela, sem este esboco
// cada teste de rota imprime "Not implemented" e polui a saida real.
window.scrollTo = () => {};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
