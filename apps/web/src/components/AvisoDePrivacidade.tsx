import { ShieldCheck } from "lucide-react";

/**
 * O que acontece com o arquivo que a pessoa está prestes a enviar.
 *
 * A política existe e funciona — o workspace expira em 15 minutos, o log sai
 * mascarado, nada disso depende de o visitante saber. Mas cumprir em silêncio
 * uma política que ninguém enunciou não é transparência: é bom comportamento
 * que o usuário não tem como verificar. Esta é a lacuna (2) do RF-GOV-003.
 *
 * Fica **antes** do campo de upload, não no rodapé. Depois de enviar já não é
 * informação, é aviso tardio.
 *
 * O texto diz também o que **fica**: o servidor registra o evento da execução
 * em log mascarado por 30 dias. Sem essa frase o aviso contaria meia verdade —
 * prometeria que nada sobrevive aos 15 minutos, e sobrevive. A frase é a mesma
 * que o `SECURITY.md` sustenta, conferida contra `core/logger.py`.
 */
export default function AvisoDePrivacidade() {
  return (
    <div
      role="note"
      aria-label="Privacidade e retenção"
      className="rounded-lg border border-signal/25 bg-signal/[0.07] px-4 py-3"
    >
      <div className="flex items-start gap-2.5">
        <ShieldCheck aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
        <div className="space-y-1.5 text-[0.8rem] leading-relaxed text-fg">
          <p>
            <strong className="font-semibold text-signal">
              O que acontece com o seu arquivo.
            </strong>{" "}
            Ele é processado para demonstrar a automação em funcionamento — só
            isso. <strong>O arquivo enviado e o resultado são apagados em 15
            minutos</strong>, automaticamente.
          </p>
          <p className="text-muted">
            O que fica no servidor é o evento da execução em log mascarado, por
            30 dias — não o conteúdo da sua planilha.
          </p>
          <p className="text-muted">
            Há <strong className="font-medium text-fg">arquivos de exemplo</strong>{" "}
            prontos para testar, e eles bastam para ver o resultado. Se preferir
            enviar o seu,{" "}
            <strong className="font-medium text-fg">
              não envie dados pessoais que não sejam necessários
            </strong>{" "}
            — nem os seus, nem os de terceiros.
          </p>
          <p className="text-muted">
            Este é o ambiente público. Na instalação privada da empresa os dados
            ficam na máquina do operador, com outras regras de retenção.
          </p>
        </div>
      </div>
    </div>
  );
}
