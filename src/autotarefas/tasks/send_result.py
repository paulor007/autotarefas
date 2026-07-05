"""
Resultado estruturado do Cadastro automatico via planilha (send_api).

Ate aqui, o envio devolvia por linha apenas (sucesso: bool, mensagem: str)
— insuficiente para responder as perguntas de produto: o que entrou (com
qual ID no sistema), o que falhou, POR QUE, e o que pode ser reenviado
sem duplicar. Este modulo define:

- `ItemEnvio`: o resultado estruturado de UMA linha enviada;
- `classify_status`: a politica oficial de classificacao HTTP do produto;
- `extract_external_id`: captura o ID criado pelo sistema (corpo do 2xx);
- agregadores para o resumo (falhas por categoria, reenviaveis).

Politica HTTP (aprovada no plano do produto):
    2xx        -> sucesso
    400 / 422  -> validacao   (dado errado; reenviar igual NAO resolve)
    409        -> duplicado   (registro ja existe; nao e erro generico)
    429        -> rate_limit  (temporario; PODE reenviar — retry na fase 3)
    5xx        -> temporario  (instabilidade do servidor; pode reenviar)
    outros 4xx -> outro       (401/403/404: configuracao, nao o dado)
    sem status -> conexao     (timeout / rede; pode reenviar)

Funcoes puras, sem I/O e sem httpx — testaveis isoladamente e reusaveis
pelos artefatos (fase 4) e pelo Live.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

#: Categorias de resultado de um envio (a de sucesso + as de falha).
CategoriaEnvio = Literal[
    "sucesso",
    "validacao",
    "duplicado",
    "rate_limit",
    "temporario",
    "conexao",
    "outro",
]

# Limites de faixa HTTP usados na classificacao.
_HTTP_OK_MIN = 200
_HTTP_OK_MAX = 299
_HTTP_BAD_REQUEST = 400
_HTTP_CONFLICT = 409
_HTTP_UNPROCESSABLE = 422
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_SERVER_ERROR = 500


@dataclass(frozen=True, slots=True)
class ItemEnvio:
    """
    Resultado estruturado do envio de UMA linha da planilha.

    Attributes:
        linha: Linha fisica na planilha (cabecalho = 1; 1a de dados = 2),
            mesma convencao da Auditoria de planilha — o numero "bate"
            com a planilha aberta no Excel.
        status_http: Status HTTP da resposta final (None em erro de
            conexao, quando nao houve resposta).
        categoria: Classificacao do resultado (ver `classify_status`).
        sucesso: True se o registro entrou no sistema (2xx).
        mensagem: Descricao legivel do resultado.
        id_externo: ID criado pelo sistema de destino (quando o corpo
            do 2xx o informa). E a prova de cadastro do registro.
        tentativas: Quantas tentativas foram feitas (1 = de primeira).
        pode_reenviar: True quando reenviar o MESMO dado pode dar certo
            (falha temporaria/conexao/rate limit). False quando nao
            adianta (dado invalido, duplicado, erro de configuracao).
    """

    linha: int
    status_http: int | None
    categoria: CategoriaEnvio
    sucesso: bool
    mensagem: str
    id_externo: str | None
    tentativas: int
    pode_reenviar: bool

    def to_dict(self) -> dict[str, Any]:
        """Serializa para o TaskResult/relatorios."""
        return {
            "linha": self.linha,
            "status_http": self.status_http,
            "categoria": self.categoria,
            "sucesso": self.sucesso,
            "mensagem": self.mensagem,
            "id_externo": self.id_externo,
            "tentativas": self.tentativas,
            "pode_reenviar": self.pode_reenviar,
        }


def classify_status(status_code: int) -> tuple[CategoriaEnvio, bool]:
    """
    Classifica um status HTTP em (categoria, pode_reenviar).

    E a politica oficial do produto — a mesma tabela do docstring do
    modulo. Nao decide retry (isso e da task); decide o SIGNIFICADO do
    resultado para o relatorio e para o operador.
    """
    if _HTTP_OK_MIN <= status_code <= _HTTP_OK_MAX:
        return "sucesso", False
    if status_code in (_HTTP_BAD_REQUEST, _HTTP_UNPROCESSABLE):
        return "validacao", False
    if status_code == _HTTP_CONFLICT:
        return "duplicado", False
    if status_code == _HTTP_TOO_MANY_REQUESTS:
        return "rate_limit", True
    if status_code >= _HTTP_SERVER_ERROR:
        return "temporario", True
    return "outro", False


def extract_external_id(body: Any) -> str | None:
    """
    Extrai o ID criado pelo sistema a partir do corpo JSON do 2xx.

    Cobre os formatos mais comuns de APIs de cadastro:
    - ``{"id": 42}``
    - ``{"data": {"id": 42}}``  (formato do sistema de demonstracao)
    - ``{"record_id": 42}``

    Retorna o ID como string, ou None quando o corpo nao informa.
    """
    if not isinstance(body, dict):
        return None

    for key in ("id", "record_id"):
        value = body.get(key)
        if isinstance(value, (int, str)) and str(value).strip():
            return str(value)

    data = body.get("data")
    if isinstance(data, dict):
        value = data.get("id")
        if isinstance(value, (int, str)) and str(value).strip():
            return str(value)

    return None


def falhas_por_categoria(items: list[ItemEnvio]) -> dict[str, int]:
    """Conta as FALHAS por categoria (sucessos ficam de fora)."""
    counts: dict[str, int] = {}
    for item in items:
        if item.sucesso:
            continue
        counts[item.categoria] = counts.get(item.categoria, 0) + 1
    return counts


def total_reenviaveis(items: list[ItemEnvio]) -> int:
    """Quantos itens falharam mas podem ser reenviados."""
    return sum(1 for item in items if not item.sucesso and item.pode_reenviar)


__all__ = [
    "CategoriaEnvio",
    "ItemEnvio",
    "classify_status",
    "extract_external_id",
    "falhas_por_categoria",
    "total_reenviaveis",
]
