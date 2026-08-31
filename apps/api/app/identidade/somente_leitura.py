"""A tranca da demonstração pública.

O produto já tem papéis — `leitor`, `operador`, `dono` — e as rotas que mudam
alguma coisa exigem o papel certo. Isso basta para gente de dentro de uma
empresa, que se conhece e responde por errar.

A demonstração pública é outra coisa: ela põe uma sessão na mão da internet.
Ali "leitor" não pode ser a única defesa, por um motivo simples de prever — a
próxima rota escrita neste repositório vai nascer com o portão que o autor
lembrar de pôr. Uma que esqueça vira porta aberta, e ninguém percebe, porque
esquecer não quebra teste nenhum.

Então a marca não mora na rota: mora na **sessão**, viaja assinada no cookie, e
é conferida num ponto só, antes de qualquer rota rodar. Uma rota nova nasce
trancada, e destrancá-la exige escrever `somente_leitura=False` — que é
justamente o tipo de linha que aparece numa revisão.

## O que passa

Só método seguro: `GET`, `HEAD`, `OPTIONS`. Mais `POST /api/auth/sair`, porque
sair é sempre direito de quem entrou, e só apaga o próprio cookie.

## O que não passa, mesmo sendo GET

`GET /api/agente/instalador` entrega um binário de 29 MB carimbado. Não muda
dado nenhum — e é exatamente o tipo de coisa que não se deixa aberta para a
internet inteira baixar em laço.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from .sessao_web import COOKIE_SESSAO, ler_sessao

#: Métodos que não mudam nada, por definição do HTTP.
SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})

#: Exceções pelo caminho: mudam algo, e ainda assim são permitidas.
LIBERADOS = frozenset({"/api/auth/sair"})

#: Leituras que não são inofensivas o bastante para uma sessão pública.
RECUSADOS_MESMO_LENDO = ("/api/agente/instalador",)

RECADO = (
    "Este é o ambiente público do AutoTarefas: os dados exibidos são "
    "produzidos pelo ambiente real, e esta sessão não altera a configuração "
    "dele."
)


def _pode(request: Request) -> bool:
    if request.method in SEGUROS:
        return not request.url.path.startswith(RECUSADOS_MESMO_LENDO)
    return request.url.path in LIBERADOS


async def barrar_escrita(
    request: Request,
    seguir: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    Recusa qualquer alteração vinda de uma sessão de demonstração.

    Roda antes das rotas, e não dentro delas: é o que faz a garantia valer para
    a rota que ainda não foi escrita.
    """
    sessao = ler_sessao(request.cookies.get(COOKIE_SESSAO))
    if sessao is not None and sessao.somente_leitura and not _pode(request):
        return JSONResponse(
            {"detail": RECADO},
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return await seguir(request)


__all__ = [
    "LIBERADOS",
    "RECADO",
    "RECUSADOS_MESMO_LENDO",
    "SEGUROS",
    "barrar_escrita",
]
