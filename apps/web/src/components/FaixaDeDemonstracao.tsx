import { Eye } from "lucide-react";

/**
 * A faixa que diz, em toda tela, o que este ambiente é.
 *
 * Sem ela o visitante fica com duas perguntas sem resposta, e as duas o levam
 * à conclusão errada:
 *
 * **"Isto é de verdade ou é uma maquete?"** Um painel que mostra máquina
 * conectada, execução concluída e pacote gerado é indistinguível de uma tela
 * pintada. Quem chega pelo portfólio não tem como saber a diferença — e vai
 * supor a versão mais barata, porque é a mais comum. A faixa afirma o
 * contrário, e o resto da tela sustenta a afirmação: o histórico é de
 * execuções que aconteceram, com hora, tamanho e hash.
 *
 * **"O que acontece se eu mexer?"** Nada, e é melhor dizer antes. O servidor
 * recusa qualquer escrita no middleware, antes de chegar em rota alguma; a
 * pessoa descobriria isso por um 403 no meio de um formulário preenchido.
 * Avisar na entrada troca uma frustração por uma informação.
 *
 * Fica fixa no topo, e não num aviso que se fecha: quem entra por um link
 * direto numa seção interna precisa da mesma informação que quem entrou pela
 * porta da frente.
 */
export default function FaixaDeDemonstracao() {
  return (
    <div
      role="note"
      aria-label="Demonstração pública"
      className="border-b border-signal/25 bg-signal/[0.07]"
    >
      <div className="container-page flex items-start gap-2.5 py-2">
        <Eye aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
        <p className="text-[0.8rem] leading-relaxed text-fg">
          <strong className="font-semibold text-signal">
            Demonstração pública.
          </strong>{" "}
          Tudo o que você vê aconteceu de verdade: as máquinas, os horários, as
          execuções e os pacotes são de um ambiente do projeto que roda sozinho.{" "}
          <span className="text-muted">
            Você pode abrir tudo e olhar tudo. Alterar, não — esta sessão é
            somente leitura.
          </span>
        </p>
      </div>
    </div>
  );
}
