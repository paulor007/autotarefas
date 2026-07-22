"""
Interpretacao UNICA de datas escritas em texto.

Existia uma contradicao no projeto: o leitor entendia `10/01/2026`, e o
validador recusava a mesma data — porque cada um tinha a sua propria ideia
do que e uma data. Este modulo passa a ser a unica fonte:

    reader/normalize.py  ->  parse_date_text  <-  tasks/validators.py

REGRA DE AMBIGUIDADE (documentada, nunca heuristica silenciosa):

    A ordem e SEMPRE DIA PRIMEIRO. `01/02/2026` e 1 de fevereiro de 2026.

    Nao existe `%m/%d/%Y` na lista de formatos. Uma data no padrao
    americano como `12/25/2026` e RECUSADA — nao reinterpretada. Isso e
    deliberado: tentar os dois e escolher "o que der certo" faria
    `03/04/2026` virar marco ou abril dependendo do resto da planilha,
    e um sistema que muda de opiniao conforme os vizinhos e pior do que
    um que recusa.

O QUE ESTE MODULO NAO FAZ, DE PROPOSITO: serial do Excel.

    Um numero so e uma data quando a CELULA declara que e (o
    `number_format` do XLSX), e essa informacao existe apenas no leitor.
    Fora desse contexto, aceitar numeros transformaria qualquer
    quantidade, codigo ou preco de um CSV numa data valida — `100`
    viraria 09/04/1900. O leitor trata o serial no lugar dele, onde o
    contexto existe.
"""

from __future__ import annotations

from datetime import datetime

#: Data e hora. Testados ANTES dos formatos de data pura — senao
#: "01/12/2019 14:30" casaria com "%d/%m/%Y" na parte da data e a hora
#: seria PERDIDA em silencio.
DATETIME_FORMATS: tuple[str, ...] = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)

#: Data pura. Dia primeiro nos separadores comuns; ano primeiro no ISO.
DATE_FORMATS: tuple[str, ...] = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
)


def parse_date_text(text: str) -> datetime | None:
    """
    Interpreta uma data escrita em texto.

    Args:
        text: o texto da celula. Vazio ou so espacos devolve None.

    Returns:
        O `datetime` correspondente, ou None se o texto nao for uma data.

    A ordem de tentativa e fixa e deterministica:

      1. formatos com hora (`DATETIME_FORMATS`);
      2. formatos de data pura (`DATE_FORMATS`), descartando o que vier
         depois do primeiro espaco;
      3. `datetime.fromisoformat`, para o restante do ISO-8601 (com `T`,
         com microssegundos, com fuso). Isto e um COMPLEMENTO do ISO, nao
         uma segunda interpretacao: nenhum formato acima e ambiguo com
         ISO-8601, entao a ordem nao muda resultado nenhum. Esta etapa
         existe para nao recusar nada que o projeto ja aceitava.

    A validade da data e do proprio calendario: `strptime` recusa
    31/02/2026 e aceita 29/02/2024 (bissexto).
    """
    limpo = text.strip()
    if not limpo:
        return None

    for formato in DATETIME_FORMATS:
        try:
            return datetime.strptime(limpo, formato)
        except ValueError:
            continue

    primeiro_pedaco = limpo.split(" ")[0]
    for formato in DATE_FORMATS:
        try:
            return datetime.strptime(primeiro_pedaco, formato)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(limpo)
    except ValueError:
        return None


def is_date_text(text: str) -> bool:
    """True se o texto for uma data reconhecida. Atalho legivel para quem so pergunta."""
    return parse_date_text(text) is not None


__all__ = ["DATETIME_FORMATS", "DATE_FORMATS", "is_date_text", "parse_date_text"]
