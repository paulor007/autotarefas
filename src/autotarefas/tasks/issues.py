"""
Sistema de issues (problemas) de validacao.

Quando uma planilha e validada, varios problemas podem ser encontrados:
- CPF invalido na linha 7
- Valor obrigatorio faltando na linha 3
- Tipo errado na linha 12 (esperava int, veio str)

Em vez de levantar excecoes (que param na primeira), o validador
**acumula** todos os problemas e retorna a lista completa. Permite ao
usuario corrigir varios erros de uma vez.

Este modulo nao depende de nada do projeto — e a base que outros
modulos (validators_br, validators, validate) vao usar.

Uso tipico:
    collector = IssueCollector()

    if not is_valid_cpf(valor):
        collector.add(line=7, column="cpf", message="CPF invalido")

    if collector.errors:
        print(f"Foram encontrados {len(collector.errors)} erros")
        for issue in collector.errors:
            print(f"  Linha {issue.line}, coluna {issue.column}: {issue.message}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class IssueSeverity(StrEnum):
    """
    Severidade de um issue de validacao.

    - ``ERROR``: problema que impede aceitacao do arquivo (validacao falha).
    - ``WARNING``: problema suspeito mas tolerado (validacao passa).

    Usar StrEnum (Python 3.11+) permite comparar direto com string:
        if issue.severity == "error":  # funciona
            ...
    """

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """
    Representa um problema encontrado durante a validacao.

    Imutavel (``frozen=True``) — uma vez criado, nao pode ser modificado.
    Isso garante que o historico de issues nao seja alterado acidentalmente.

    Usa ``slots=True`` pra otimizar memoria (sem ``__dict__``). Importante
    porque uma planilha grande pode gerar milhares de issues.

    Attributes:
        line: Numero da linha onde o problema ocorreu.
            - 1, 2, 3... = linhas de dados (1-based, como Excel).
            - 0 = problema no cabecalho ou global.
        column: Nome da coluna afetada. ``None`` se for problema global
            (ex: arquivo vazio, cabecalho ausente).
        message: Descricao humana do problema (em portugues, claro e curto).
        severity: ERROR (default) ou WARNING.
        value: Valor original que causou o problema (opcional, ajuda no debug).
            Ex: se o CPF "123" e invalido, value="123".
    """

    line: int
    column: str | None
    message: str
    severity: IssueSeverity = IssueSeverity.ERROR
    value: str | None = None

    @property
    def is_error(self) -> bool:
        """True se for severidade ERROR."""
        return self.severity == IssueSeverity.ERROR

    @property
    def is_warning(self) -> bool:
        """True se for severidade WARNING."""
        return self.severity == IssueSeverity.WARNING


@dataclass(slots=True)
class IssueCollector:
    """
    Acumula issues durante a execucao da validacao.

    NAO e ``frozen=True`` — precisa ser mutavel pra adicionar issues
    durante a execucao. Mas tem ``slots=True`` pra otimizar memoria.

    Suporta protocolos Python:
        - ``len(collector)``  → total de issues
        - ``bool(collector)`` → True se tem qualquer issue (truthy)
        - iteravel via ``.issues``

    Attributes:
        issues: Lista de ValidationIssue acumulados (em ordem de adicao).
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        *,
        line: int,
        column: str | None,
        message: str,
        severity: IssueSeverity = IssueSeverity.ERROR,
        value: str | None = None,
    ) -> None:
        """
        Adiciona um issue a colecao.

        Usa ``*,`` pra forcar argumentos nomeados — torna o codigo do
        chamador mais legivel:
            collector.add(line=7, column="cpf", message="...")  # claro
            collector.add(7, "cpf", "...")                      # nao permitido
        """
        self.issues.append(
            ValidationIssue(
                line=line,
                column=column,
                message=message,
                severity=severity,
                value=value,
            )
        )

    @property
    def errors(self) -> list[ValidationIssue]:
        """Apenas issues de severidade ERROR."""
        return [i for i in self.issues if i.is_error]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Apenas issues de severidade WARNING."""
        return [i for i in self.issues if i.is_warning]

    @property
    def is_valid(self) -> bool:
        """True se NAO ha errors (warnings sao permitidos)."""
        return not self.errors

    @property
    def total(self) -> int:
        """Total de issues acumulados."""
        return len(self.issues)

    def __len__(self) -> int:
        """Permite ``len(collector)``."""
        return self.total

    def __bool__(self) -> bool:
        """Permite ``if collector:`` (truthy se tem qualquer issue)."""
        return bool(self.issues)


__all__ = [
    "IssueCollector",
    "IssueSeverity",
    "ValidationIssue",
]
