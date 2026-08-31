import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";

import { obterDetalheDaExecucao, type DetalheDeExecucao } from "../lib/plataforma";
import { quando, tamanho } from "../lib/datas";
import { destinoEmPalavras, origensEmPalavras } from "../lib/rotulos";

interface Props {
  execucaoId: string;
  aoFechar: () => void;
  /**
   * Sessão pública: a política aparece em palavras, sem caminho.
   *
   * Quem administra a própria máquina continua vendo o caminho — para essa
   * pessoa ele é o dado. Para quem só olha, ele é a estrutura de pastas de uma
   * empresa que não é a dele.
   */
  somenteLeitura?: boolean;
}

/**
 * Uma execução por inteiro, com o que a sustenta.
 *
 * A lista responde "aconteceu". Esta tela responde a pergunta seguinte, que é
 * a que decide se alguém confia: **como eu sei?**
 *
 * O que a torna evidência, e não um resumo mais longo:
 *
 * - o **SHA-256** do pacote, que é o que distingue um backup de um arquivo com
 *   nome de backup;
 * - para onde a cópia foi e **se foi conferida lá** — o pacote é lido de volta
 *   no destino e a soma recalculada, porque rede que cai e cabo USB ruim
 *   produzem arquivos com o tamanho certo e o conteúdo errado;
 * - a **política** que pediu, porque "12 arquivos copiados" não diz se copiou
 *   o que devia sem o outro lado da conta;
 * - as linhas da **trilha encadeada por hash**, em que alterar uma no meio
 *   quebra a corrente.
 */
export default function DetalheDaExecucao({
  execucaoId,
  aoFechar,
  somenteLeitura = false,
}: Props) {
  const [dados, setDados] = useState<DetalheDeExecucao | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let vivo = true;
    obterDetalheDaExecucao(execucaoId)
      .then((resposta) => {
        if (vivo) setDados(resposta);
      })
      .catch((e: unknown) => {
        if (vivo) setErro(e instanceof Error ? e.message : "não foi possível abrir");
      });
    return () => {
      vivo = false;
    };
  }, [execucaoId]);

  if (erro) {
    return (
      <p className="mt-2 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-[0.8rem] text-danger">
        {erro}
      </p>
    );
  }

  if (dados === null) {
    return <p className="mt-2 text-[0.8rem] text-muted">Abrindo…</p>;
  }

  return (
    <div className="mt-3 flex flex-col gap-4 rounded-lg border border-white/10 bg-ink px-4 py-3 text-[0.8rem]">
      <Bloco titulo="O pacote">
        {dados.artefatos.length === 0 ? (
          <p className="text-muted">
            Esta execução não produziu pacote. O motivo está na linha acima.
          </p>
        ) : (
          dados.artefatos.map((artefato) => (
            <div key={artefato.id} className="flex flex-col gap-1">
              <p className="font-mono text-fg">{artefato.nome}</p>
              <p className="text-muted">{tamanho(artefato.tamanho_bytes)}</p>
              {/* A soma inteira, e nao os oito primeiros caracteres: e ela que
                  alguem usa para conferir por fora. Cortar transformaria a
                  evidencia num enfeite com cara de evidencia. */}
              <p className="break-all font-mono text-[0.72rem] text-muted">
                SHA-256 {artefato.sha256 || "não informado"}
              </p>
              <ul className="mt-1 flex flex-col gap-1">
                <Onde
                  conferido
                  texto="Guardado na própria máquina"
                  detalhe="É a cópia de origem: ela existe desde que o pacote foi gerado."
                />
                {artefato.entregas.map((entrega, indice) => (
                  <Onde
                    key={`${entrega.tipo}-${indice}`}
                    conferido={entrega.conferido_no_destino === true}
                    texto={entrega.destino || entrega.tipo}
                    detalhe={
                      entrega.conferido_no_destino
                        ? "Lido de volta no destino e conferido pela soma."
                        : "A cópia chegou, mas não há confirmação de conferência."
                    }
                  />
                ))}
                {artefato.nuvem_em && (
                  <Onde
                    conferido
                    texto="Na nuvem"
                    detalhe={`${artefato.nuvem_chave} · ${quando(artefato.nuvem_em)}`}
                  />
                )}
                {artefato.nuvem_pendente && (
                  <Onde
                    conferido={false}
                    texto="Aguardando envio para a nuvem"
                    detalhe={
                      artefato.nuvem_erro ||
                      "O pacote está feito e sobe assim que houver conexão."
                    }
                  />
                )}
              </ul>
            </div>
          ))
        )}
      </Bloco>

      {dados.politica && (
        <Bloco titulo="O que a política pediu">
          <p className="text-fg">{dados.politica.nome}</p>
          <ul className="mt-1 flex flex-col gap-0.5 text-muted">
            <li>
              Pastas:{" "}
              <span className={somenteLeitura ? "text-fg" : "font-mono text-fg"}>
                {somenteLeitura
                  ? origensEmPalavras(dados.politica.origens)
                  : dados.politica.origens.join(", ") ||
                    "todas as autorizadas na máquina"}
              </span>
            </li>
            <li>
              Destino: {destinoEmPalavras(dados.politica.destino.tipo)}
              {!somenteLeitura && dados.politica.destino.caminho
                ? ` · ${dados.politica.destino.caminho}`
                : ""}
            </li>
            <li>
              Guardar: {dados.politica.retencao.diarias} diários,{" "}
              {dados.politica.retencao.semanais} semanais,{" "}
              {dados.politica.retencao.mensais} mensais
            </li>
          </ul>
        </Bloco>
      )}

      {dados.trilha.length > 0 && (
        <Bloco titulo="Na trilha de auditoria">
          {/* O encadeamento por hash e o que faz esta lista valer: cada linha
              carrega o hash da anterior, e alterar uma no meio quebra a
              corrente. A conferencia da corrente inteira fica em Atividade. */}
          <ul className="flex flex-col gap-1">
            {dados.trilha.map((linha) => (
              <li key={linha.hash_atual} className="flex flex-wrap gap-2">
                <span className="text-muted">{quando(linha.quando)}</span>
                <span className="text-fg">{linha.acao}</span>
                {linha.alvo && <span className="text-muted">· {linha.alvo}</span>}
              </li>
            ))}
          </ul>
        </Bloco>
      )}

      <button
        type="button"
        onClick={aoFechar}
        className="self-start rounded-lg border border-white/12 px-3 py-1 text-[0.75rem] text-fg hover:border-white/25"
      >
        Fechar
      </button>
    </div>
  );
}

function Bloco({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-1">
      <h4 className="text-[0.75rem] font-semibold uppercase tracking-wide text-muted">
        {titulo}
      </h4>
      {children}
    </section>
  );
}

/**
 * Um lugar onde a cópia está, e se ela foi conferida lá.
 *
 * O ícone distingue as duas coisas de propósito: "chegou" e "chegou e foi
 * conferido" são afirmações diferentes, e tratá-las igual apagaria a única
 * que sustenta a palavra "verificável".
 */
function Onde({
  conferido,
  texto,
  detalhe,
}: {
  conferido: boolean;
  texto: string;
  detalhe: string;
}) {
  return (
    <li className="flex items-start gap-2">
      {conferido ? (
        <Check aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" />
      ) : (
        <X aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal" />
      )}
      <span>
        <span className="text-fg">{texto}</span>
        <span className="text-muted"> — {detalhe}</span>
      </span>
    </li>
  );
}
