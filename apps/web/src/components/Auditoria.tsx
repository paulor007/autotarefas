import { useCallback, useEffect, useState } from "react";

import { listarAuditoria, type LinhaDeAuditoria } from "../lib/plataforma";

/** Quantas linhas mostrar sem pedir para expandir. */
const PREVIA = 12;

/**
 * Trilha de auditoria: o que foi feito, por quem, e se o registro continua íntegro.
 *
 * A trilha já era gravada e encadeada por hash desde o começo da plataforma,
 * mas não aparecia em lugar nenhum — e uma evidência que ninguém consegue
 * olhar não serve como evidência.
 *
 * O selo de integridade fica em cima, e não escondido no rodapé. A corrente de
 * hashes existe justamente para dispensar a confiança cega; mostrar as linhas
 * sem dizer se elas ainda batem devolveria o problema para quem lê.
 */
export default function Auditoria() {
  const [linhas, setLinhas] = useState<LinhaDeAuditoria[] | null>(null);
  const [integra, setIntegra] = useState(true);
  const [explicacao, setExplicacao] = useState("");
  const [erro, setErro] = useState("");
  const [tudo, setTudo] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const resposta = await listarAuditoria();
      setLinhas(resposta.linhas);
      setIntegra(resposta.integra);
      setExplicacao(resposta.explicacao);
      setErro("");
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível carregar a trilha");
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (erro) {
    return (
      <p className="rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm text-danger">
        {erro}
      </p>
    );
  }

  if (linhas === null) {
    return <p className="text-sm text-muted">Carregando trilha…</p>;
  }

  const mostradas = tudo ? linhas : linhas.slice(0, PREVIA);

  return (
    <div>
      <p
        className={`text-[0.85rem] font-semibold ${integra ? "text-ok" : "text-danger"}`}
      >
        {integra
          ? "Trilha íntegra: cada linha confere com a anterior."
          : `Trilha ALTERADA: ${explicacao}`}
      </p>

      {linhas.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          Nada registrado ainda. A trilha guarda o que muda estado: pareamento,
          política, execução, restauração, revogação.
        </p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1">
          {mostradas.map((linha) => (
            <li key={linha.id} className="text-[0.8rem] text-muted">
              <span className="font-mono text-fg">{linha.acao}</span>
              {linha.alvo && <> · {linha.alvo}</>}
              {linha.detalhe && <> · {linha.detalhe}</>}
              <span className="ml-1 opacity-70">{quando(linha.quando)}</span>
            </li>
          ))}
        </ul>
      )}

      {linhas.length > PREVIA && (
        <button
          type="button"
          onClick={() => setTudo((atual) => !atual)}
          className="mt-2 rounded-lg border border-white/12 px-3 py-1 text-[0.75rem] text-fg hover:border-white/25"
        >
          {tudo ? "Mostrar menos" : `Ver as ${linhas.length} linhas`}
        </button>
      )}
    </div>
  );
}

function quando(bruto: string): string {
  const data = new Date(bruto);
  if (Number.isNaN(data.getTime())) return bruto;
  return data.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
