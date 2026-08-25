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
 * O limite vem junto com o resultado, sempre — e desde a 02.B ele depende de
 * o pacote estar assinado. São duas perguntas diferentes:
 *
 * - **integridade**: o conteúdo bate com o manifesto?
 * - **autenticidade**: a assinatura do manifesto confere com a chave externa?
 *
 * Sem assinatura, só a primeira tem resposta, e a tela diz isso. Anunciar
 * "íntegro" sem essa distinção seria a promessa exagerada que o produto
 * recusa em todos os outros lugares.
 *
 * Escopo: confere o pacote que está no servidor, na pasta desta execução —
 * o mesmo arquivo que o botão de download entrega. Não confere a cópia já
 * baixada, que o navegador guarda fora do alcance da página.
 */
/**
 * Uma linha curta por desfecho da assinatura.
 *
 * "sem chave" nunca vira "adulterado": alarme falso treina a pessoa a ignorar
 * o alarme de verdade.
 */
const ROTULO_AUTENTICIDADE: Record<VerifyReport["autenticidade"], string> = {
  nao_assinado: "Pacote não assinado — autenticidade não comprovada.",
  autentico: "Assinatura confere: o pacote não foi alterado depois de gerado.",
  adulterado: "A assinatura NÃO confere: o pacote foi alterado depois de assinado.",
  sem_chave: "Pacote assinado; a chave de conferência não está disponível aqui.",
  outra_chave: "Pacote assinado com outra chave.",
};

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
        <div>
          <button
            type="button"
            onClick={() => void conferir()}
            disabled={conferindo}
            className="rounded-lg border border-white/12 px-4 py-2 text-sm font-semibold text-fg hover:border-white/25 disabled:opacity-50"
          >
            {conferindo ? "Conferindo…" : "Verificar este pacote"}
          </button>
          <p className="mt-1.5 text-[0.8rem] text-muted">
            Confere o pacote no servidor, antes do download.
          </p>
        </div>
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
              ? "Pacote gerado e verificado antes do download."
              : "Pacote com problemas — não confie nele para restaurar"}
          </p>

          {relatorio.integro && (
            <p className="mt-1.5 text-[0.85rem] text-muted">
              {relatorio.conferidos} arquivo(s) conferem com o manifesto, lido
              de dentro do próprio pacote.
            </p>
          )}

          <p
            className={`mt-1.5 text-[0.85rem] ${
              relatorio.autenticidade === "autentico"
                ? "text-ok"
                : relatorio.autenticidade === "adulterado" ||
                    relatorio.autenticidade === "outra_chave"
                  ? "text-danger"
                  : "text-muted"
            }`}
          >
            {ROTULO_AUTENTICIDADE[relatorio.autenticidade]}
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
