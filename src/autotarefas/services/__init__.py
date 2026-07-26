"""
Servicos de aplicacao: orquestracao reutilizavel do nucleo.

Um servico aqui NAO implementa regra nenhuma — ele apenas encadeia as pecas
que ja existem (reader, profiling, schema sugerido) e devolve um resultado
estruturado. A razao de existir: a CLI e o Live precisam da MESMA sequencia
de passos, e sem um lugar comum cada um reimplementaria a orquestracao (e
divergiria com o tempo).

Nao depende de FastAPI, de Click nem de nada de interface. Recebe caminho de
arquivo e devolve dados.
"""

from autotarefas.services.analysis import (
    Ambiguity,
    AnalysisOutcome,
    SheetOption,
    analyze_spreadsheet,
)

__all__ = ["Ambiguity", "AnalysisOutcome", "SheetOption", "analyze_spreadsheet"]
