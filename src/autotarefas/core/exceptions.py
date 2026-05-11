"""
Exceções customizadas do AutoTarefas.

Uso:
    from autotarefas.core.exceptions import ValidationError

    raise ValidationError(
        "Coluna 'email' tem formato inválido",
        field="email",
        row=42,
    )
"""

from __future__ import annotations

from typing import Any


class AutoTarefasError(Exception):
    """
    Exceção raiz do AutoTarefas.

    Todas as outras exceções customizadas herdam desta. Permite que
    callers façam ``except AutoTarefasError`` para capturar qualquer
    erro do projeto.
    """


class ConfigError(AutoTarefasError):
    """
    Erro em configuração do AutoTarefas.

    Levantado quando:

    - Arquivo ``.env`` tem variável inválida ou faltando
    - YAML de configuração RPA está malformado
    - Valor de configuração não passa na validação

    Attributes:
        config_key: Nome da configuração que falhou (se aplicável).
    """

    def __init__(self, message: str, config_key: str | None = None) -> None:
        """
        Inicializa ConfigError.

        Args:
            message: Mensagem descritiva.
            config_key: Nome da config que falhou (ex: 'EMAIL_USER').
        """
        super().__init__(message)
        self.config_key = config_key


class ValidationError(AutoTarefasError):
    """
    Erro de validação de dados.

    Levantado quando dado de entrada (linha de CSV, célula de Excel,
    valor de configuração) não passa na validação.

    Attributes:
        field: Nome da coluna/campo (se aplicável).
        row: Número da linha (se aplicável, 1-indexed).
        value: Valor que falhou (se seguro logar).
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        row: int | None = None,
        value: Any = None,
    ) -> None:
        """
        Inicializa ValidationError.

        Args:
            message: Mensagem descritiva.
            field: Nome do campo/coluna que falhou.
            row: Número da linha (1-indexed).
            value: Valor que falhou na validação.
        """
        super().__init__(message)
        self.field = field
        self.row = row
        self.value = value


class SecurityError(AutoTarefasError):
    """
    Erro de segurança.

    Levantado quando uma operação é bloqueada por motivos de segurança:

    - Tentativa de path traversal (``../../etc/passwd``)
    - URL HTTP em ambiente de produção
    - Credencial encontrada em local proibido
    - Tentativa de uso de funções perigosas (``eval``, ``exec``)
    """


class AuditError(AutoTarefasError):
    """
    Falha no sistema de audit trail.

    Levantado quando o audit trail não consegue registrar uma operação.
    Geralmente NÃO é fatal — operações continuam mesmo com audit
    falhando, mas um aviso é emitido.
    """


class RPAError(AutoTarefasError):
    """
    Erro genérico de RPA.

    Base para todas as exceções específicas de automação web (Fase 8+).
    """


class LoginError(RPAError):
    """
    Falha no login automático em sistema web.

    Possíveis causas:

    - Credenciais incorretas
    - Captcha apareceu
    - 2FA não suportado
    - Sistema fora do ar
    """


class SelectorNotFoundError(RPAError):
    """
    Seletor CSS/XPath não encontrado na página.

    Geralmente indica que a interface do sistema mudou e a configuração
    YAML precisa ser atualizada.

    Attributes:
        selector: O seletor que não foi encontrado.
        page_url: URL da página onde foi procurado (se disponível).
    """

    def __init__(
        self,
        message: str,
        selector: str | None = None,
        page_url: str | None = None,
    ) -> None:
        """
        Inicializa SelectorNotFoundError.

        Args:
            message: Mensagem descritiva.
            selector: Seletor CSS/XPath que falhou.
            page_url: URL da página onde foi procurado.
        """
        super().__init__(message)
        self.selector = selector
        self.page_url = page_url


class RPATimeoutError(RPAError):
    """
    Operação de RPA excedeu timeout.

    Attributes:
        operation: Descrição da operação que estourou.
        timeout_seconds: Timeout configurado em segundos.
    """

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """
        Inicializa RPATimeoutError.

        Args:
            message: Mensagem descritiva.
            operation: Operação que estourou (ex: 'page.goto').
            timeout_seconds: Timeout configurado.
        """
        super().__init__(message)
        self.operation = operation
        self.timeout_seconds = timeout_seconds
