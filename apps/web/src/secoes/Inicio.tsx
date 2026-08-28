import { useCallback, useEffect, useState } from "react";

import CartaoDeAutomacao from "../components/CartaoDeAutomacao";
import SeloDeProtecao from "../components/SeloDeProtecao";
import { quando } from "../lib/datas";
import {
  listarDispositivos,
  listarHistorico,
  listarPoliticas,
  listarPresenca,
  obterProtecao,
  type Dispositivo,
  type EstadoDeProtecao,
  type Execucao,
  type Politica,
} from "../lib/plataforma";

interface Retrato {
  dispositivos: Dispositivo[];
  conectados: Set<string>;
  politicas: Politica[];
  execucoes: Execucao[];
  protecao: EstadoDeProtecao;
}

const VAZIO: Retrato = {
  dispositivos: [],
  conectados: new Set(),
  politicas: [],
  execucoes: [],
  protecao: {
    nivel: "sem_configuracao",
    titulo: "",
    resumo: "",
    backups: [],
  },
};

/**
 * A primeira tela de quem ja e cliente.
 *
 * Uma automacao, um cartao, e o estado dela. Nao ha cartao informativo aqui:
 * o que aparece corresponde a alguma coisa que existe e leva direto ao lugar
 * onde ela se opera.
 */
export default function Inicio() {
  const [retrato, setRetrato] = useState<Retrato | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const [maquinas, presenca, politicas, historico, protecao] =
        await Promise.all([
          listarDispositivos(),
          listarPresenca(),
          listarPoliticas(),
          listarHistorico(),
          obterProtecao(),
        ]);
      setRetrato({
        dispositivos: maquinas.dispositivos,
        conectados: new Set(
          presenca.conectados
            .filter((p) => p.conectado)
            .map((p) => p.dispositivo_id),
        ),
        politicas: politicas.politicas,
        execucoes: historico.execucoes,
        protecao,
      });
      setErro(null);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "não foi possível carregar");
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (erro) {
    return (
      <div className="rounded-2xl border border-danger/30 bg-danger/5 p-6">
        <p className="text-sm text-danger">{erro}</p>
      </div>
    );
  }

  const { dispositivos, conectados, politicas, execucoes } = retrato ?? VAZIO;
  const emServico = dispositivos.filter((d) => d.estado !== "revogado");
  const ativas = politicas.filter((p) => p.ativa);
  const ultima = execucoes[0];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">Suas automações</h1>
        <p className="mt-1 text-[0.85rem] text-muted">
          Configure uma vez. O AutoTarefas trabalha sozinho depois.
        </p>
      </header>

      {/* A resposta antes do detalhe. Quem abre o produto quer saber se esta
          protegido, e nao quantas politicas existem. */}
      <SeloDeProtecao estado={retrato?.protecao ?? null} />

      <CartaoDeAutomacao
        carregando={retrato === null}
        maquinas={emServico.length}
        conectadas={emServico.filter((d) => conectados.has(d.id)).length}
        backupsAtivos={ativas.length}
        ultimoBackup={
          ultima
            ? { resultado: ultima.resultado, em: quando(ultima.terminada_em || ultima.iniciada_em) }
            : null
        }
      />
    </div>
  );
}
