import { useCallback, useEffect, useState } from "react";

import {
  ErroDaPlataforma,
  consultarDispositivo,
  listarConteudoDoPacote,
  listarPacotes,
  restaurarNoDispositivo,
  type ItemDoPacote,
  type PacoteNaMaquina,
  type RelatorioDeRestauracao,
} from "../lib/plataforma";

interface Props {
  dispositivoId: string;
  nomeDoDispositivo: string;
  aoFechar: () => void;
}

/** Quantos itens do pacote listar antes de resumir. */
const PREVIA = 15;

/**
 * Restauração guiada: escolher o pacote, ver o que há dentro, recuperar.
 *
 * Três decisões desta tela existem para ela não virar um jeito bonito de perder
 * arquivo:
 *
 * 1. **Ver antes de mexer.** O conteúdo do pacote é mostrado antes de qualquer
 *    escrita. Restaurar às cegas é como abrir uma caixa com os olhos fechados.
 * 2. **Preservar é o padrão.** Arquivos que já existem no destino não são
 *    tocados, a menos que alguém peça — e, se pedir, a substituição passa pela
 *    guarda de ação destrutiva.
 * 3. **A tela não conhece caminho nenhum da máquina.** O pacote vai pelo nome;
 *    o destino é escolhido entre as pastas que foram autorizadas no próprio
 *    computador. Digitar caminho livre aqui seria pedir ao cliente que fizesse
 *    o trabalho da CLI dentro do navegador.
 *
 * Uma restauração incompleta **não** é anunciada como sucesso: o que faltou, o
 * que foi recusado e o que saiu corrompido aparecem com o mesmo destaque do
 * que deu certo.
 */
export default function Restauracao({
  dispositivoId,
  nomeDoDispositivo,
  aoFechar,
}: Props) {
  const [pacotes, setPacotes] = useState<PacoteNaMaquina[] | null>(null);
  const [temPastaAutorizada, setTemPastaAutorizada] = useState(true);
  const [raizes, setRaizes] = useState<string[]>([]);
  const [escolhido, setEscolhido] = useState("");
  const [conteudo, setConteudo] = useState<ItemDoPacote[] | null>(null);
  const [destino, setDestino] = useState("");
  const [subpasta, setSubpasta] = useState("recuperado");
  const [sobrescrever, setSobrescrever] = useState(false);
  const [relatorio, setRelatorio] = useState<RelatorioDeRestauracao | null>(null);
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    setAviso("");
    try {
      const [lista, estado] = await Promise.all([
        listarPacotes(dispositivoId),
        consultarDispositivo(dispositivoId),
      ]);
      setPacotes(lista.pacotes ?? []);
      setTemPastaAutorizada(lista.tem_pasta_autorizada !== false);
      const autorizadas = estado.estado.raizes ?? [];
      setRaizes(autorizadas);
      setDestino((atual) => atual || autorizadas[0] || "");
    } catch (e: unknown) {
      setPacotes([]);
      setAviso(mensagemDe(e));
    }
  }, [dispositivoId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const escolher = async (nome: string) => {
    setEscolhido(nome);
    setConteudo(null);
    setRelatorio(null);
    setAviso("");
    try {
      const resposta = await listarConteudoDoPacote(dispositivoId, nome);
      setConteudo(resposta.conteudo ?? []);
      if (resposta.ok === false)
        setAviso(emPortugues(resposta.erro) || "não foi possível ler o pacote");
    } catch (e: unknown) {
      setAviso(mensagemDe(e));
    }
  };

  const restaurar = async () => {
    setOcupado(true);
    setAviso("");
    setRelatorio(null);
    try {
      const resposta = await restaurarNoDispositivo(dispositivoId, {
        pacote: escolhido,
        destino: juntar(destino, subpasta),
        sobrescrever,
        // A tela não conhece pasta nenhuma da máquina: pede a conferência, e o
        // Agente resolve onde estão os pacotes que provam o backup.
        conferir_backup: sobrescrever,
      });
      setRelatorio(resposta.ok === false ? null : resposta);
      if (resposta.ok === false)
        setAviso(emPortugues(resposta.erro) || "a restauração não aconteceu");
    } catch (e: unknown) {
      setAviso(mensagemDe(e));
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-white/12 bg-bg/40 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-fg">
          Restaurar arquivos · {nomeDoDispositivo}
        </h3>
        <button
          type="button"
          onClick={aoFechar}
          className="rounded-lg border border-white/12 px-2 py-1 text-[0.75rem] text-muted hover:border-white/25"
        >
          Fechar
        </button>
      </div>

      {!temPastaAutorizada && (
        <p className="mt-2 text-[0.85rem] text-danger">
          Esta máquina não tem pasta autorizada, então não há pacotes. A
          autorização é dada no próprio computador, pelo Agente.
        </p>
      )}

      {pacotes !== null && pacotes.length === 0 && temPastaAutorizada && (
        <p className="mt-2 text-[0.85rem] text-muted">
          Nenhum pacote nesta máquina ainda. Execute um backup antes de tentar
          restaurar.
        </p>
      )}

      {pacotes !== null && pacotes.length > 0 && (
        <>
          <p className="mt-3 text-[0.8rem] text-muted">1. Escolha o pacote</p>
          <ul className="mt-1 flex flex-col gap-1">
            {pacotes.map((item) => (
              <li key={item.nome}>
                <button
                  type="button"
                  onClick={() => void escolher(item.nome)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-[0.8rem] hover:border-white/25 ${
                    escolhido === item.nome
                      ? "border-signal/50 bg-signal/5 text-fg"
                      : "border-white/10 text-muted"
                  }`}
                >
                  <span className="font-mono text-fg">{item.nome}</span>
                  <span className="ml-2">{emMB(item.tamanho_bytes)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {conteudo !== null && (
        <div className="mt-3">
          <p className="text-[0.8rem] text-muted">
            2. Confira o que há dentro — {conteudo.length} arquivo(s) declarados
          </p>
          <ul className="mt-1 max-h-40 overflow-y-auto font-mono text-[0.75rem] text-muted">
            {conteudo.slice(0, PREVIA).map((item) => (
              <li key={item.arquivo}>
                {item.arquivo}
                {item.neste_pacote !== "sim" && (
                  <span className="ml-2 not-italic text-signal">
                    (está em {item.onde})
                  </span>
                )}
              </li>
            ))}
          </ul>
          {conteudo.length > PREVIA && (
            <p className="text-[0.75rem] text-muted">
              … e mais {conteudo.length - PREVIA}.
            </p>
          )}
        </div>
      )}

      {escolhido && (
        <div className="mt-3">
          <p className="text-[0.8rem] text-muted">3. Escolha onde recuperar</p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <select
              aria-label="Pasta autorizada de destino"
              value={destino}
              onChange={(evento) => setDestino(evento.target.value)}
              className="rounded-lg border border-white/12 bg-surface px-2 py-1 text-[0.8rem] text-fg"
            >
              {raizes.map((raiz) => (
                <option key={raiz} value={raiz}>
                  {raiz}
                </option>
              ))}
            </select>
            <span className="text-muted">/</span>
            <input
              aria-label="Subpasta de destino"
              value={subpasta}
              onChange={(evento) => setSubpasta(evento.target.value)}
              className="w-40 rounded-lg border border-white/12 bg-surface px-2 py-1 text-[0.8rem] text-fg"
            />
          </div>
          <p className="mt-1 text-[0.75rem] text-muted">
            Só aparecem aqui as pastas autorizadas no próprio computador. O
            Agente recusa qualquer outro lugar.
          </p>

          <label className="mt-2 flex items-start gap-2 text-[0.8rem] text-muted">
            <input
              type="checkbox"
              checked={sobrescrever}
              onChange={(evento) => setSobrescrever(evento.target.checked)}
              className="mt-1"
            />
            <span>
              Substituir arquivos que já existirem no destino. Só acontece se
              houver backup recente e conferido daquela máquina — sem isso, o
              Agente bloqueia e nada é alterado.
            </span>
          </label>

          <button
            type="button"
            onClick={() => void restaurar()}
            disabled={ocupado || !destino}
            className="mt-3 rounded-lg border border-white/12 px-3 py-1.5 text-[0.8rem] font-semibold text-fg hover:border-white/25 disabled:opacity-50"
          >
            {ocupado ? "Restaurando…" : "Restaurar"}
          </button>
        </div>
      )}

      {aviso && (
        <p className="mt-3 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-[0.85rem] text-danger">
          {aviso}
        </p>
      )}

      {relatorio && <Relatorio dados={relatorio} />}
    </div>
  );
}

/**
 * O que a restauração fez, sem arredondar.
 *
 * Uma restauração parcial anunciada como sucesso é pior do que uma que falha:
 * a pessoa vai embora achando que recuperou tudo.
 */
function Relatorio({ dados }: { dados: RelatorioDeRestauracao }) {
  const restaurados = dados.restaurados ?? 0;
  const jaExistiam = dados.ja_existiam ?? [];
  const recusados = dados.recusados ?? [];
  const faltando = dados.faltando ?? [];
  const corrompidos = dados.corrompidos ?? [];
  // Quem decide é o núcleo, que abriu o pacote e conferiu cada arquivo.
  // Recalcular aqui foi exatamente o que fez uma restauração completa
  // aparecer como INCOMPLETA — e o erro inverso teria sido pior.
  const completa = dados.completa === true;

  return (
    <div className="mt-3 rounded-lg border border-white/10 bg-surface px-3 py-2 text-[0.85rem]">
      <p className={completa ? "font-semibold text-ok" : "font-semibold text-signal"}>
        {completa
          ? `Restauração concluída: ${restaurados} arquivo(s) conferem com o manifesto.`
          : "Restauração INCOMPLETA — veja abaixo o que ficou de fora."}
      </p>

      {dados.protecao && (
        <p className="mt-1 text-muted">Proteção: {dados.protecao}</p>
      )}

      {jaExistiam.length > 0 && (
        <p className="mt-1 text-muted">
          {jaExistiam.length} arquivo(s) já existiam e foram preservados. Marque
          "substituir" se quiser trocá-los.
        </p>
      )}
      {faltando.length > 0 && (
        <p className="mt-1 text-danger">
          {faltando.length} arquivo(s) estão em pacotes anteriores que não foram
          informados.
        </p>
      )}
      {recusados.length > 0 && (
        <p className="mt-1 text-danger">
          {recusados.length} caminho(s) tentaram sair da pasta de destino e
          foram recusados.
        </p>
      )}
      {corrompidos.length > 0 && (
        <p className="mt-1 text-danger">
          {corrompidos.length} arquivo(s) saíram diferentes do que o manifesto
          declarou e foram descartados.
        </p>
      )}
    </div>
  );
}

/**
 * Tira o nome da exceção que o Agente usa para diagnóstico.
 *
 * `ProtecaoBloqueou: sobrescrever exige backup...` é útil no log da máquina e
 * inútil para quem está olhando a tela — o nome da classe não diz a ninguém o
 * que fazer a seguir, e a frase depois dele diz.
 */
function emPortugues(erro: string | undefined): string {
  if (!erro) return "";
  return erro.replace(/^[A-Za-z_][A-Za-z0-9_]*:\s*/, "");
}

/** Junta a pasta autorizada com a subpasta, sem inventar separador. */
function juntar(raiz: string, subpasta: string): string {
  const limpa = subpasta.trim().replace(/^[\\/]+/, "");
  if (!limpa) return raiz;
  const separador = raiz.includes("\\") ? "\\" : "/";
  return `${raiz.replace(/[\\/]+$/, "")}${separador}${limpa}`;
}

function emMB(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Traduz o erro sem apagar a diferença entre "não dá" e "quebrou".
 *
 * 409 é a máquina desligada — situação normal, e não falha da restauração.
 */
function mensagemDe(erro: unknown): string {
  if (erro instanceof ErroDaPlataforma) {
    if (erro.status === 409) {
      return "A máquina está desligada ou sem conexão com o Live. Nada foi alterado.";
    }
    if (erro.status === 504) {
      return "A máquina está conectada mas não respondeu a tempo. Nada foi alterado.";
    }
    return erro.message;
  }
  return erro instanceof Error ? erro.message : "não foi possível";
}
