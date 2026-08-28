import { useCallback, useEffect, useState } from "react";

import { obterEstadoDeSessao, type EstadoDeSessao } from "../lib/plataforma";

export interface Sessao {
  estado: EstadoDeSessao | null;
  erro: string | null;
  recarregar: () => void;
}

/**
 * Quem esta usando o produto, segundo o servidor.
 *
 * `estado` nulo significa "ainda nao sei" — e nao "nao ha ninguem". A
 * diferenca importa: tratar carregamento como deslogado pisca a tela de
 * entrada na cara de quem ja estava dentro.
 */
export function useSessao(): Sessao {
  const [estado, setEstado] = useState<EstadoDeSessao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      setEstado(await obterEstadoDeSessao());
      setErro(null);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível carregar");
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return {
    estado,
    erro,
    recarregar: () => {
      void carregar();
    },
  };
}
