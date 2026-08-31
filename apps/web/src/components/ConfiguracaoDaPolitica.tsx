import type { Politica } from "../lib/plataforma";
import {
  agendamentoEmPalavras,
  destinoEmPalavras,
  ligadoOuNao,
  notificacaoEmPalavras,
  origensEmPalavras,
  retencaoEmPalavras,
} from "../lib/rotulos";

interface Props {
  politica: Politica;
  maquina: string;
  /** Motivos do veredito de proteção para esta política, quando houver. */
  motivos?: string[];
  /**
   * Sessão pública: o caminho das pastas não aparece.
   *
   * Quem administra a própria máquina continua vendo o caminho — para essa
   * pessoa ele é o dado, e escondê-lo seria esconder o que ela configurou.
   */
  somenteLeitura?: boolean;
}

/**
 * Como este backup está configurado, em português.
 *
 * Não é um formulário: é a leitura de uma automação que já existe e está
 * rodando. A diferença importa — o assistente de configuração aparecia aberto
 * e vazio no ambiente público, com valores padrão, e quem olhava via a tela de
 * criar uma política nova em vez da configuração da política real que estava
 * logo acima.
 *
 * A verificação de integridade aparece como fato, e não como opção: todo
 * pacote é conferido no destino, sempre, e não há como desligar isso. É o que
 * a palavra "verificável" significa.
 */
export default function ConfiguracaoDaPolitica({
  politica,
  maquina,
  motivos = [],
  somenteLeitura = false,
}: Props) {
  const config = politica.configuracao;

  return (
    <div className="mt-3 flex flex-col gap-4 rounded-lg border border-white/10 bg-ink px-4 py-4 text-[0.85rem]">
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <Campo rotulo="Máquina" valor={maquina || "—"} />
        <Campo
          rotulo="Origem"
          valor={
            somenteLeitura
              ? origensEmPalavras(config.origens)
              : config.origens.join(" · ") ||
                "Todas as pastas autorizadas na máquina"
          }
        />
        <Campo
          rotulo="Destino"
          valor={destinoEmPalavras(config.destino.tipo)}
          detalhe={somenteLeitura ? "" : config.destino.caminho}
        />
        <Campo rotulo="Agendamento" valor={agendamentoEmPalavras(config.agendamento)} />
        <div>
          <dt className="text-[0.72rem] uppercase tracking-wide text-muted">
            Retenção
          </dt>
          <dd className="mt-0.5 flex flex-col text-fg">
            {retencaoEmPalavras(config.retencao).map((linha) => (
              <span key={linha}>{linha}</span>
            ))}
          </dd>
        </div>
        <div className="flex flex-col gap-3">
          <Campo rotulo="Incremental" valor={ligadoOuNao(config.incremental)} />
          {/* Fato, e não opção. A conferência no destino é incondicional: o
              pacote é lido de volta e a soma recalculada, e não há como
              desligar. Já houve uma caixa marcável aqui que não ligava em
              nada — um controle que não controla nada é a mentira mais fácil
              de cometer numa interface. */}
          <Campo rotulo="Verificação de integridade" valor="Ativa, sempre" />
        </div>
        <Campo
          rotulo="Notificação"
          valor={notificacaoEmPalavras(config.notificacao.quando)}
        />
      </dl>

      {motivos.length > 0 && (
        <section className="rounded-lg border border-signal/25 bg-signal/[0.06] px-3 py-2">
          <h5 className="text-[0.72rem] font-semibold uppercase tracking-wide text-signal">
            O que falta para a proteção ficar inteira
          </h5>
          <ul className="mt-1 flex flex-col gap-1 text-[0.8rem] text-fg">
            {motivos.map((motivo) => (
              <li key={motivo}>{motivo}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Campo({
  rotulo,
  valor,
  detalhe = "",
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
}) {
  return (
    <div>
      <dt className="text-[0.72rem] uppercase tracking-wide text-muted">
        {rotulo}
      </dt>
      <dd className="mt-0.5 text-fg">
        {valor}
        {detalhe && (
          <span className="ml-1 font-mono text-[0.75rem] text-muted">
            {detalhe}
          </span>
        )}
      </dd>
    </div>
  );
}
