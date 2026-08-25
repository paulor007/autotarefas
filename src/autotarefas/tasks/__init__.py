"""
Módulo de Tasks do AutoTarefas.

Cada task herda de ``BaseTask`` e implementa um caso de uso específico:
validação de planilha, extração de API, envio de e-mail, backup.

**Importação preguiçosa, e por um motivo concreto.** Este pacote reúne tarefas
que não têm nada a ver umas com as outras: validar planilha usa `pandas`,
extrair da web usa `playwright` e `beautifulsoup4`, fazer backup não usa nenhum
dos três.

Enquanto todas eram importadas aqui em cima, `import autotarefas.tasks.backup`
arrastava o conjunto inteiro. Isso não é um detalhe de desempenho: é o que
decidia o tamanho do instalador do Agente. Uma máquina de escritório que só faz
backup não deve precisar instalar um navegador automatizado para copiar uma
pasta.

Com ``__getattr__`` (PEP 562) os nomes públicos continuam existindo — quem
escreve ``from autotarefas.tasks import ValidateTask`` não percebe diferença —,
mas cada um só puxa suas dependências quando é realmente usado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — só para o verificador de tipos
    from autotarefas.tasks.extract_api import ExtractApiTask
    from autotarefas.tasks.extract_web import ExtractWebTask
    from autotarefas.tasks.send_api import SendApiTask
    from autotarefas.tasks.send_email import SendEmailTask, SmtpConfig
    from autotarefas.tasks.send_telegram import SendTelegramTask
    from autotarefas.tasks.sync_api import SyncApiTask
    from autotarefas.tasks.validate import (
        ColumnSchema,
        ColumnType,
        Schema,
        ValidateTask,
        load_schema,
    )

#: De qual módulo vem cada nome público. É a tabela que ``__getattr__`` usa —
#: e é também a lista de tudo que este pacote promete oferecer.
_ONDE_MORA: dict[str, str] = {
    "ColumnSchema": "autotarefas.tasks.validate",
    "ColumnType": "autotarefas.tasks.validate",
    "ExtractApiTask": "autotarefas.tasks.extract_api",
    "ExtractWebTask": "autotarefas.tasks.extract_web",
    "Schema": "autotarefas.tasks.validate",
    "SendApiTask": "autotarefas.tasks.send_api",
    "SendEmailTask": "autotarefas.tasks.send_email",
    "SendTelegramTask": "autotarefas.tasks.send_telegram",
    "SmtpConfig": "autotarefas.tasks.send_email",
    "SyncApiTask": "autotarefas.tasks.sync_api",
    "ValidateTask": "autotarefas.tasks.validate",
    "load_schema": "autotarefas.tasks.validate",
}


def __getattr__(nome: str) -> Any:
    """
    Importa o módulo certo na primeira vez que o nome é pedido.

    Nome desconhecido levanta `AttributeError` com a mesma frase que o Python
    usaria. Devolver `None`, ou deixar vazar um `ImportError`, transformaria um
    erro de digitação num problema difícil de entender.
    """
    modulo = _ONDE_MORA.get(nome)
    if modulo is None:
        msg = f"module {__name__!r} has no attribute {nome!r}"
        raise AttributeError(msg)

    from importlib import import_module

    valor = getattr(import_module(modulo), nome)
    # Guarda no próprio módulo: da segunda vez em diante, o Python resolve o
    # atributo direto, sem passar por aqui.
    globals()[nome] = valor
    return valor


def __dir__() -> list[str]:
    """Faz `dir()` e o autocompletar continuarem enxergando tudo."""
    return sorted(set(globals()) | set(_ONDE_MORA))


__all__ = [
    "ColumnSchema",
    "ColumnType",
    "ExtractApiTask",
    "ExtractWebTask",
    "Schema",
    "SendApiTask",
    "SendEmailTask",
    "SendTelegramTask",
    "SmtpConfig",
    "SyncApiTask",
    "ValidateTask",
    "load_schema",
]
