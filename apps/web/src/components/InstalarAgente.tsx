import { useEffect, useState } from "react";

import {
  enderecoDoInstalador,
  fichaDoInstalador,
  type CodigoDePareamento,
  type FichaDoInstalador,
} from "../lib/plataforma";

interface Props {
  /** O código já emitido. É ele que autoriza o pareamento. */
  codigo: CodigoDePareamento;
}

/**
 * Instalação do Agente: dois roteiros, e a tela mostra o que este servidor tem.
 *
 * O backup de uma pasta local não acontece pelo navegador — ele não alcança o
 * disco de ninguém. Alguém precisa instalar um programa na máquina, e esta tela
 * é o caminho para isso não virar "clone o repositório".
 *
 * **Com o executável** (`formato: "exe"`): um arquivo, duplo clique, e o
 * assistente pergunta só a pasta a proteger. O endereço e o código já vêm
 * colados no arquivo — a pessoa não digita nada.
 *
 * **Sem o executável** (`formato: "zip"`): o servidor ainda não gerou o
 * executável, e a tela **diz isso**, com o roteiro que exige Python e terminal.
 * Prometer duplo clique aqui seria a mentira mais cara desta tela: a pessoa
 * baixaria, clicaria, e nada aconteceria.
 */
export default function InstalarAgente({ codigo }: Props) {
  const [ficha, setFicha] = useState<FichaDoInstalador | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    fichaDoInstalador()
      .then(setFicha)
      .catch((e: unknown) =>
        setErro(e instanceof Error ? e.message : "não foi possível ler o pacote"),
      );
  }, []);

  const endereco = enderecoDoInstalador(codigo.codigo);
  const umClique = ficha?.formato === "exe";

  return (
    <div className="mt-3 rounded-lg border border-signal/40 bg-signal/5 px-4 py-3">
      <h3 className="text-sm font-semibold text-fg">
        Instalar o Agente nesta máquina
      </h3>

      <a
        href={endereco}
        className="mt-3 inline-block rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] font-semibold text-fg hover:border-white/25"
      >
        Baixar o Agente
      </a>

      {ficha && (
        <p className="mt-1 text-[0.75rem] text-muted">
          {ficha.nome} · {emMB(ficha.tamanho_bytes)}
          {ficha.precisa_de_python
            ? ` · precisa de Python ${ficha.precisa_de_python} instalado`
            : " · não precisa instalar mais nada"}
        </p>
      )}
      {erro && <p className="mt-1 text-[0.75rem] text-danger">{erro}</p>}

      {umClique ? (
        <RoteiroDeUmClique codigo={codigo} />
      ) : (
        ficha && <RoteiroComPython codigo={codigo} ficha={ficha} />
      )}
    </div>
  );
}

/** O caminho bom: baixar, clicar duas vezes, escolher a pasta. */
function RoteiroDeUmClique({ codigo }: { codigo: CodigoDePareamento }) {
  return (
    <>
      <ol className="mt-3 flex flex-col gap-2 text-[0.85rem] text-muted">
        <li>
          <span className="font-semibold text-fg">1.</span> Dê dois cliques no
          arquivo baixado.
        </li>
        <li>
          <span className="font-semibold text-fg">2.</span> Confira se a
          impressão digital que aparecer é a mesma que vai surgir aqui na lista
          de dispositivos.
        </li>
        <li>
          <span className="font-semibold text-fg">3.</span> Escolha a pasta a
          proteger. A autorização é dada <strong>na própria máquina</strong> —
          nenhuma tela na nuvem concede acesso ao seu disco.
        </li>
      </ol>
      <p className="mt-3 text-[0.75rem] text-muted">
        O endereço deste Live e o código de pareamento vão dentro do arquivo —
        você pode copiá-lo para outro computador por pen drive, e ele continua
        sabendo para onde ligar.
      </p>
      <p className="mt-1 text-[0.75rem] text-muted">
        O código vale {codigo.validade_minutos} minutos e serve{" "}
        <strong>uma vez só</strong>: este arquivo protege um computador. Para o
        próximo, gere outro código e baixe de novo.
      </p>
    </>
  );
}

/**
 * O caminho que ainda existe: pacote com Python.
 *
 * Aparece quando o servidor não gerou o executável. A frase diz isso em vez de
 * esconder, porque quem administra o servidor precisa saber o que fazer:
 * `python tools/construir_agente.py`.
 */
function RoteiroComPython({
  codigo,
  ficha,
}: {
  codigo: CodigoDePareamento;
  ficha: FichaDoInstalador;
}) {
  const pasta = ficha.pasta_do_pacote ?? "AutoTarefas-Agente";
  const comando = `.\\instalar.ps1 -Codigo ${codigo.codigo} -Servidor ${origem()}`;

  return (
    <>
      <p className="mt-3 text-[0.8rem] text-signal">
        Este servidor ainda não gerou o instalador de um clique. Por enquanto o
        download é o pacote que exige Python. Quem administra o servidor gera o
        executável com <code>python tools/construir_agente.py</code>.
      </p>

      <ol className="mt-3 flex flex-col gap-3 text-[0.85rem] text-muted">
        <li>
          <p className="font-semibold text-fg">1. Extraia o arquivo</p>
          <p className="mt-1">
            Dentro dele há a pasta <code>{pasta}</code>. É <strong>nela</strong>{" "}
            que o terminal precisa abrir — o extrator do Windows costuma criar
            outra pasta em volta.
          </p>
        </li>
        <li>
          <p className="font-semibold text-fg">2. Abra o terminal nessa pasta e rode</p>
          <code className="mt-1 block overflow-x-auto rounded-lg border border-white/10 bg-bg/60 px-3 py-2 font-mono text-[0.75rem] text-fg">
            {comando}
          </code>
          <p className="mt-1 text-[0.75rem]">
            Se o Windows recusar por política de execução, rode antes:{" "}
            <code>Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass</code>
          </p>
          <p className="mt-1 text-[0.75rem]">
            O código vale {codigo.validade_minutos} minutos e serve uma vez só.
          </p>
        </li>
        <li>
          <p className="font-semibold text-fg">3. Autorize as pastas</p>
          <p className="mt-1">
            A autorização é dada <strong>na própria máquina</strong>. O
            instalador mostra o comando no final.
          </p>
        </li>
      </ol>
    </>
  );
}

/** Endereço deste Live, para a pessoa não precisar digitá-lo. */
function origem(): string {
  if (typeof window === "undefined") return "https://SEU-LIVE";
  return window.location.origin;
}

function emMB(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
