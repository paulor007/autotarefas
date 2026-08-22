import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Nome da área protegida, usado no log técnico. */
  area: string;
  /** Ação de recuperação oferecida à pessoa. */
  onReset?: () => void;
}

interface State {
  failed: boolean;
}

/**
 * Barreira contra tela em branco.
 *
 * Uma excecao de render nao capturada desmonta a arvore INTEIRA do React — foi
 * assim que um campo com formato inesperado apagou a aplicacao completa. Esta
 * barreira contem o dano na area protegida: o resto da pagina (navegacao,
 * estrutura) continua de pe.
 *
 * Isto e protecao SECUNDARIA, nao conserto: a causa raiz continua sendo
 * validar a resposta na fronteira. Por isso o erro tecnico vai INTEIRO para o
 * console — nada e engolido em silencio —, enquanto a tela mostra apenas o que
 * a pessoa pode fazer a respeito.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(
      `[AutoTarefas] falha ao renderizar "${this.props.area}"`,
      error,
      info.componentStack,
    );
  }

  private readonly retry = (): void => {
    this.setState({ failed: false });
    this.props.onReset?.();
  };

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;

    return (
      <div
        role="alert"
        className="rounded-lg border border-danger/40 bg-danger/5 px-4 py-4"
      >
        <p className="text-sm font-semibold text-danger">
          Algo deu errado ao exibir esta etapa
        </p>
        <p className="mt-1 text-[0.85rem] text-muted">
          O restante da página continua funcionando. Reinicie a análise para
          tentar de novo — os detalhes técnicos estão no console do navegador.
        </p>
        <button
          type="button"
          onClick={this.retry}
          className="mt-3 rounded-lg border border-white/12 px-4 py-2 text-sm font-semibold text-fg hover:border-white/25"
        >
          Reiniciar análise
        </button>
      </div>
    );
  }
}
