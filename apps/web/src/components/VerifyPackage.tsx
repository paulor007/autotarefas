import { useState } from "react";

import { verifyPackage, type VerifyReport } from "../lib/api";

interface Props {
  token: string;
  /** Nome do pacote dentro desta execução (ex.: `backup.zip`). */
  name: string;
}

/**
 * Conferência de um pacote de backup, pela tela.
 *
 * O card se chama "verificável". Sem um jeito de conferir na interface, isso
 * seria só um adjetivo — e a pessoa ficaria com um arquivo em que precisa
 * acreditar. A conferência lê o manifesto de DENTRO do pacote e recalcula o
 * hash de cada arquivo, sem depender dos originais: é exatamente a situação
 * de quem um dia precisar restaurar.
 *
 * O limite vem junto com o resultado, sempre. Um "íntegro" sem a ressalva de
 * que isso não prova autenticidade seria a mesma promessa exagerada que o
 * produto recusa em todos os outros lugares.
 */
export default function VerifyPackage({ token, name }: Props) {
  const [relatorio, setRelatorio] = useState<VerifyReport | null>(null);
  const [conferindo, setConferindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const conferir = async () => {
    if (conferindo) return;
    setConferindo(true);
    setErro(null);
    try {
      setRelatorio(await verifyPackage(token, name));
    } catch (e: unknown) {
      setRelatorio(null);
      setErro(e instanceof Error ? e.message : "não foi possível conferir");
    } finally {
      setConferindo(false);
    }
  };

  return (
    <div className="mx-auto mt-4 max-w-3xl">
      {!relatorio && (
        <button
          type="button"
          onClick={() => void conferir()}
          disabled={conferindo}
          className="rounded-lg border border-white/12 px-4 py-2 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
        >
          {conferindo ? "Conferindo…" : "Verificar este pacote"}
        </button>
      )}

      {erro && (
        <p className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-3 text-sm text-danger">
          {erro}
        </p>
      )}

      {relatorio && (
        <div
          className={`rounded-lg border px-4 py-3 ${
            relatorio.integro
              ? "border-ok/40 bg-ok/[0.05]"
              : "border-danger/40 bg-danger/5"
          }`}
        >
          <p
            className={`text-sm font-semibold ${
              relatorio.integro ? "text-ok" : "text-danger"
            }`}
          >
            {relatorio.integro
              ? `Pacote íntegro: ${relatorio.conferidos} arquivo(s) conferem com o manifesto`
              : "Pacote com problemas — não confie nele para restaurar"}
          </p>

          {relatorio.corrompidos.length > 0 && (
            <p className="mt-1.5 text-[0.85rem] text-muted">
              Conteúdo diferente do declarado: {relatorio.corrompidos.join(", ")}
            </p>
          )}
          {relatorio.faltando.length > 0 && (
            <p className="mt-1.5 text-[0.85rem] text-muted">
              Declarados no manifesto e ausentes: {relatorio.faltando.join(", ")}
            </p>
          )}
          {relatorio.nao_lidos_na_origem.length > 0 && (
            <p className="mt-1.5 text-[0.85rem] text-muted">
              {relatorio.nao_lidos_na_origem.length} arquivo(s) não entraram
              quando este pacote foi criado — o que está aqui dentro continua
              confiável.
            </p>
          )}

          <p className="mt-2 text-[0.8rem] text-muted">{relatorio.limite}</p>
        </div>
      )}
    </div>
  );
}
