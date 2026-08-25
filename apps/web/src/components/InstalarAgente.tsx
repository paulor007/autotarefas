import { useEffect, useState } from "react";

import {
  ENDERECO_DO_INSTALADOR,
  fichaDoInstalador,
  type CodigoDePareamento,
  type FichaDoInstalador,
} from "../lib/plataforma";

interface Props {
  /** O código já emitido. É ele que autoriza o pareamento. */
  codigo: CodigoDePareamento;
}

/**
 * Instalação guiada do Agente: baixar, rodar, parear.
 *
 * O backup de uma pasta local não acontece pelo navegador — ele não alcança o
 * disco de ninguém. Alguém precisa instalar um programa na máquina, e esta tela
 * é o caminho para isso não virar "clone o repositório".
 *
 * Duas honestidades que a tela mantém:
 *
 * 1. **O download é real.** O link aponta para um pacote montado pelo servidor
 *    a partir do código que ele está rodando, e a tela diz o tamanho e quantos
 *    arquivos vêm dentro antes de a pessoa clicar.
 * 2. **O que o produto exige aparece antes, não depois.** Python é necessário
 *    nesta versão, e esconder isso até a terceira tela transformaria um
 *    requisito em armadilha.
 *
 * O comando aparece escrito porque é a instalação — não a operação. Depois de
 * instalado e pareado, tudo acontece pelo Live.
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

  const comando = `.\\instalar.ps1 -Codigo ${codigo.codigo} -Servidor ${origem()}`;

  return (
    <div className="mt-3 rounded-lg border border-signal/40 bg-signal/5 px-4 py-3">
      <h3 className="text-sm font-semibold text-fg">
        Instalar o Agente nesta máquina
      </h3>

      <ol className="mt-3 flex flex-col gap-3 text-[0.85rem] text-muted">
        <li>
          <p className="font-semibold text-fg">1. Baixe o pacote</p>
          <a
            href={ENDERECO_DO_INSTALADOR}
            className="mt-1 inline-block rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] font-semibold text-fg hover:border-white/25"
          >
            Baixar o Agente
          </a>
          {ficha && (
            <p className="mt-1 text-[0.75rem]">
              {ficha.nome} · {emKB(ficha.tamanho_bytes)} · {ficha.arquivos}{" "}
              arquivos · precisa de Python {ficha.precisa_de_python} instalado
            </p>
          )}
          {erro && <p className="mt-1 text-[0.75rem] text-danger">{erro}</p>}
        </li>

        <li>
          <p className="font-semibold text-fg">2. Extraia e rode o instalador</p>
          <p className="mt-1">
            Clique com o botão direito na pasta extraída, escolha "Abrir no
            Terminal" e rode:
          </p>
          <code className="mt-1 block overflow-x-auto rounded-lg border border-white/10 bg-bg/60 px-3 py-2 font-mono text-[0.75rem] text-fg">
            {comando}
          </code>
          <p className="mt-1 text-[0.75rem]">
            O código vale {codigo.validade_minutos} minutos e serve uma vez só.
          </p>
        </li>

        <li>
          <p className="font-semibold text-fg">3. Autorize as pastas</p>
          <p className="mt-1">
            A autorização é dada <strong>na própria máquina</strong>, e não aqui:
            nenhuma tela na nuvem concede acesso ao disco de ninguém. O
            instalador mostra o comando no final.
          </p>
        </li>
      </ol>

      <p className="mt-3 text-[0.75rem] text-muted">
        Assim que o Agente parear, a máquina aparece na lista acima. Confira se a
        impressão digital mostrada aqui é a mesma que o instalador imprimiu.
      </p>
    </div>
  );
}

/** Endereço deste Live, para a pessoa não precisar digitá-lo. */
function origem(): string {
  if (typeof window === "undefined") return "https://SEU-LIVE";
  return window.location.origin;
}

function emKB(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
