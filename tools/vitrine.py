"""Vitrine: o ambiente do AutoTarefas que fica de pe para quem vem olhar.

Quem chega pelo portfolio nao instala nada, nao abre terminal e nao configura
coisa nenhuma. Do lado dele, e clicar e navegar. Do lado de ca, alguem precisa
ter montado um ambiente de verdade - e e isto aqui.

Nada e simulado. A organizacao existe no banco, o Agente e o mesmo executavel
que um cliente instalaria, o pareamento passa pelo mesmo codigo temporario, as
pastas sao autorizadas na maquina pelo mesmo caminho de sempre e as politicas
sao politicas. O que muda e so quem monta: o projeto, e nao o visitante.

    python tools/vitrine.py preparar   # cria o que faltar, e nada mais
    python tools/vitrine.py estado     # o que existe hoje
    python tools/vitrine.py agente     # sobe o Agente da vitrine

`preparar` e idempotente de proposito: um deploy roda de novo a cada subida, e
provisionamento que duplica organizacao a cada partida seria pior do que nao
ter provisionamento.

## Sobre o destino, e uma verdade incomoda

Num servidor unico, o destino do backup fica no mesmo disco de origem. O
produto detecta isso e mostra "Protecao parcial", com o motivo - e esta certo:
copia ao lado do original nao sobrevive ao disco morrer.

Para o painel publico dizer "Protegido", o destino precisa ser mesmo externo:
um bucket S3, ou uma pasta de rede noutra maquina. Isso e decisao de
implantacao, e nao tem atalho - declarar "disco externo" para uma pasta local
seria exatamente a mentira que o produto inteiro foi feito para nao contar.
"""

from __future__ import annotations

import json

# `subprocess` para rodar o Agente — o mesmo modulo que um cliente roda.
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import click

RAIZ = Path(__file__).resolve().parents[1]

#: Onde a vitrine mora. Pasta de runtime, coberta pelo `.gitignore`.
CASA = RAIZ / ".autotarefas" / "vitrine"

BANCO = CASA / "vitrine.db"
CONFIG_DO_AGENTE = CASA / "agente"
DADOS = CASA / "dados"
DESTINO = CASA / "destino"

ORGANIZACAO = "AutoTarefas Demonstracao"
EMAIL_DO_DONO = "operacao@demonstracao.autotarefas"
MAQUINA = "SERVIDOR-DEMONSTRACAO"

#: Quatro politicas diarias, em horarios diferentes.
#:
#: Nao e enfeite: com uma so, um visitante estaria em media doze horas depois
#: da ultima execucao, e o painel mostraria evidencia velha. Com quatro, ele
#: raramente esta a mais de seis horas — e cada uma e uma politica diaria de
#: verdade, com retencao que faz sentido, sem inventar frequencia que o motor
#: nao tem.
HORARIOS = ("03:00", "09:00", "15:00", "21:00")

#: Arquivos de exemplo. Sinteticos, e obviamente sinteticos: nenhum dado real
#: de ninguem entra num ambiente publico.
#:
#: Cada um se declara no proprio conteudo, inclusive os CSV. Um arquivo
#: restaurado sai do pacote sozinho, longe daqui: numeros plausiveis sem
#: nenhuma marca seriam confundidos com dado de alguem.
EXEMPLOS: dict[str, str] = {
    "contratos/locacao-2026.txt": (
        "CONTRATO DE LOCACAO (exemplo)\n"
        "Arquivo sintetico do ambiente de demonstracao do AutoTarefas.\n"
    ),
    "contratos/prestacao-servicos.txt": (
        "CONTRATO DE PRESTACAO DE SERVICOS (exemplo)\n"
        "Arquivo sintetico do ambiente de demonstracao do AutoTarefas.\n"
    ),
    "financeiro/fluxo-de-caixa.csv": (
        "# exemplo sintetico - ambiente de demonstracao do AutoTarefas\n"
        "data,descricao,valor\n"
        "2026-08-01,Recebimento,1250.00\n"
        "2026-08-03,Fornecedor,-380.50\n"
        "2026-08-07,Recebimento,940.00\n"
    ),
    "financeiro/notas-emitidas.csv": (
        "# exemplo sintetico - ambiente de demonstracao do AutoTarefas\n"
        "numero,cliente,valor\n001,Cliente A,1250.00\n002,Cliente B,340.00\n"
    ),
    "documentos/procedimentos.txt": (
        "PROCEDIMENTOS INTERNOS (exemplo)\n"
        "Arquivo sintetico do ambiente de demonstracao do AutoTarefas.\n"
    ),
}


@dataclass(frozen=True)
class Situacao:
    """O que ja existe da vitrine, para `preparar` saber o que pular."""

    organizacao: bool = False
    maquina: bool = False
    pastas: int = 0
    politicas: int = 0

    @property
    def completa(self) -> bool:
        return (
            self.organizacao
            and self.maquina
            and self.pastas > 0
            and self.politicas == len(HORARIOS)
        )


def destino_configurado() -> dict[str, str]:
    """
    Para onde as copias vao, e de que tipo.

    Sem `VITRINE_DESTINO_TIPO`, cai em `local` — honesto num servidor unico, e
    o painel vai dizer "Protecao parcial" por causa disso. Ver o cabecalho.
    """
    import os

    tipo = os.environ.get("VITRINE_DESTINO_TIPO", "local").strip() or "local"
    caminho = os.environ.get("VITRINE_DESTINO_CAMINHO", "").strip()
    return {"tipo": tipo, "caminho": caminho or str(DESTINO)}


def configuracao_da_politica(hora: str, origens: list[str]) -> dict[str, object]:
    """
    A politica de uma das janelas do dia.

    Retencao curta de proposito: o ambiente roda para sempre, e guardar doze
    mensais de um backup sintetico seria acumular disco por nada. Sete diarias
    dao uma semana visivel de historico, que e o que alguem olhando quer ver.
    """
    return {
        "origens": origens,
        "destino": destino_configurado(),
        "agendamento": {
            "tipo": "diario",
            "hora": hora,
            "dia_da_semana": 0,
            "dia_do_mes": 1,
        },
        "retencao": {"diarias": 7, "semanais": 2, "mensais": 1},
        "retry": {"tentativas": 3, "espera_inicial_min": 5},
        "notificacao": {"quando": "problema", "emails": []},
        "usar_vss": False,
        "cifrar": False,
        "assinar": True,
        "incremental": False,
    }


def nome_da_politica(hora: str) -> str:
    return f"Backup diario {hora}"


def semear_dados(pasta: Path = DADOS) -> int:
    """Escreve os arquivos de exemplo que ainda nao existem."""
    escritos = 0
    for relativo, conteudo in EXEMPLOS.items():
        alvo = pasta / relativo
        if alvo.exists():
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
        escritos += 1
    return escritos


def _preparar_ambiente() -> None:
    """Banco e endereco da vitrine, antes de qualquer import da aplicacao."""
    import os

    CASA.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{BANCO.as_posix()}")
    os.environ.setdefault("DEMONSTRACAO_PUBLICA", "1")
    os.environ.setdefault("DEMONSTRACAO_ORG", ORGANIZACAO)


def _todos_os_modelos() -> None:
    """
    Importa quem declara tabela, antes de o banco ser tocado.

    `banco()` cria o esquema na primeira chamada, a partir do que estiver
    registrado no metadata NAQUELE instante. Nem todo modelo mora em
    `db/models.py`: `CodigoDePareamento`, por exemplo, e declarado dentro de
    `dispositivos.py`. Sem este import, o esquema nasce sem a tabela dele e o
    erro aparece la na frente, no meio do pareamento, dizendo "no such table" —
    que nao se parece nem um pouco com "faltou um import".

    O servidor nao sofre disso porque `main.py` importa tudo na subida. Quem
    sofre e ferramenta como esta, que fala com o banco direto.
    """
    from apps.api.app import dispositivos, historico, politicas  # noqa: F401


def _agente(*argumentos: str) -> subprocess.CompletedProcess[str]:
    """Roda o Agente pela linha de comando, como um cliente rodaria."""
    # Justificativa do B603 abaixo: a lista de argumentos e montada aqui, com
    # arquivo e o interpretador em uso. Nada vindo de rede ou de usuario
    # entra nesta linha.
    return subprocess.run(  # noqa: S603  # nosec B603
        [sys.executable, "-m", "agente", *argumentos],
        cwd=RAIZ / "apps" / "agente",
        capture_output=True,
        text=True,
        check=False,
        env=_ambiente_do_agente(),
    )


def _ambiente_do_agente() -> dict[str, str]:
    import os

    return {
        **os.environ,
        "PYTHONPATH": str(RAIZ / "apps" / "agente") + os.pathsep + str(RAIZ / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }


def _config_do_agente() -> object:
    from agente.config import Local

    return Local(pasta=CONFIG_DO_AGENTE)


def situacao() -> Situacao:
    """O que a vitrine ja tem, lido do banco e do disco."""
    _preparar_ambiente()
    _todos_os_modelos()
    from sqlalchemy import select

    from apps.api.app.db.atual import banco
    from apps.api.app.db.models import Dispositivo, Organizacao, Politica

    local = _config_do_agente()
    configuracao = local.carregar()  # type: ignore[attr-defined]

    with banco().sessao() as sessao:
        organizacao = sessao.execute(
            select(Organizacao).where(Organizacao.nome == ORGANIZACAO)
        ).scalar_one_or_none()
        if organizacao is None:
            return Situacao()
        maquinas = (
            sessao.execute(select(Dispositivo).where(Dispositivo.organizacao_id == organizacao.id))
            .scalars()
            .all()
        )
        politicas = (
            sessao.execute(select(Politica).where(Politica.organizacao_id == organizacao.id))
            .scalars()
            .all()
        )

    return Situacao(
        organizacao=True,
        maquina=bool(maquinas) and configuracao.pareado,
        pastas=len(configuracao.raizes),
        politicas=len(politicas),
    )


@click.group(help=__doc__)
def vitrine() -> None:
    """Ambiente publico do AutoTarefas."""


def _garantir_organizacao(sessao: object) -> tuple[object, object]:
    """A organizacao da vitrine e o dono dela. Devolve (organizacao, contexto)."""
    from sqlalchemy import select

    from apps.api.app.db import repositorio as repo
    from apps.api.app.db.models import Organizacao, Papel, Usuario

    organizacao = sessao.execute(  # type: ignore[attr-defined]
        select(Organizacao).where(Organizacao.nome == ORGANIZACAO)
    ).scalar_one_or_none()
    if organizacao is None:
        organizacao = repo.criar_organizacao(
            sessao, nome=ORGANIZACAO, dominio="demonstracao.autotarefas"
        )
        click.echo(f"Organizacao criada: {ORGANIZACAO}")

    dono = sessao.execute(  # type: ignore[attr-defined]
        select(Usuario).where(Usuario.email == EMAIL_DO_DONO)
    ).scalar_one_or_none()
    if dono is None:
        dono = repo.criar_usuario(
            sessao,
            email=EMAIL_DO_DONO,
            nome="Operacao AutoTarefas",
            emissor="vitrine",
            assunto=ORGANIZACAO,
        )
        repo.vincular(sessao, organizacao=organizacao, usuario=dono, papel=Papel.DONO)
        click.echo("Dono da vitrine criado.")

    contexto = repo.abrir_contexto(sessao, usuario_id=dono.id, organizacao_id=organizacao.id)
    return organizacao, contexto


def _garantir_maquina(sessao: object, contexto: object, servidor: str) -> object:
    """
    Pareia o Agente da vitrine, se ele ainda nao estiver pareado.

    Pelo mesmo caminho de um cliente: codigo temporario emitido pelo Live e
    consumido pela linha de comando do Agente. Um atalho que gravasse o
    dispositivo direto no banco provaria menos e esconderia a metade do fluxo
    que costuma quebrar.
    """
    from apps.api.app import dispositivos as rotas_dispositivos

    local = _config_do_agente()
    configuracao = local.carregar()  # type: ignore[attr-defined]
    if configuracao.pareado:
        return configuracao

    codigo = rotas_dispositivos.emitir(sessao, contexto)  # type: ignore[arg-type]
    sessao.commit()  # type: ignore[attr-defined]
    saida = _agente(
        "parear",
        "--servidor",
        servidor,
        "--codigo",
        codigo.codigo,
        "--nome",
        MAQUINA,
        "--pasta-de-configuracao",
        str(CONFIG_DO_AGENTE),
    )
    if saida.returncode != 0:
        click.echo(f"[ERRO] o pareamento falhou:\n{saida.stderr}", err=True)
        raise SystemExit(1)
    click.echo(f"Maquina pareada: {MAQUINA}")
    return local.carregar()  # type: ignore[attr-defined]


def _garantir_pastas(configuracao: object) -> object:
    """Escreve os exemplos e autoriza a pasta, na maquina, pelo Agente."""
    novos = semear_dados()
    if novos:
        click.echo(f"Arquivos de exemplo escritos: {novos}")
    DESTINO.mkdir(parents=True, exist_ok=True)

    if configuracao.raizes:  # type: ignore[attr-defined]
        return configuracao

    saida = _agente("autorizar", str(DADOS), "--pasta-de-configuracao", str(CONFIG_DO_AGENTE))
    if saida.returncode != 0:
        click.echo(f"[ERRO] a autorizacao falhou:\n{saida.stderr}", err=True)
        raise SystemExit(1)
    click.echo(f"Pasta autorizada: {DADOS}")
    return _config_do_agente().carregar()  # type: ignore[attr-defined]


def _garantir_politicas(
    sessao: object, contexto: object, organizacao: object, configuracao: object
) -> None:
    """Uma politica por horario, criada so se ainda nao houver."""
    from sqlalchemy import select

    from apps.api.app import politicas as rotas_politicas
    from apps.api.app.db.models import Dispositivo

    maquina = sessao.execute(  # type: ignore[attr-defined]
        select(Dispositivo).where(
            Dispositivo.organizacao_id == organizacao.id,  # type: ignore[attr-defined]
            Dispositivo.id == configuracao.dispositivo_id,  # type: ignore[attr-defined]
        )
    ).scalar_one_or_none()
    if maquina is None:
        click.echo(
            "[ERRO] o Agente diz estar pareado, mas a maquina nao esta neste\n"
            "       banco. Apague a pasta da vitrine e prepare de novo.",
            err=True,
        )
        raise SystemExit(1)

    existentes = {
        registro.nome
        for registro in sessao.execute(  # type: ignore[attr-defined]
            select(rotas_politicas.Politica).where(
                rotas_politicas.Politica.organizacao_id == organizacao.id  # type: ignore[attr-defined]
            )
        ).scalars()
    }
    for hora in HORARIOS:
        nome = nome_da_politica(hora)
        if nome in existentes:
            continue
        rotas_politicas.criar(
            sessao,  # type: ignore[arg-type]
            contexto,  # type: ignore[arg-type]
            rotas_politicas.PedidoDePolitica(
                nome=nome,
                dispositivo_id=maquina.id,
                configuracao=configuracao_da_politica(
                    hora,
                    list(configuracao.raizes),  # type: ignore[attr-defined]
                ),
            ),
        )
        click.echo(f"Politica criada: {nome}")


@vitrine.command(help="Cria o que faltar da vitrine. Seguro de repetir.")
@click.option(
    "--servidor",
    default="http://127.0.0.1:7860",
    show_default=True,
    help="Endereco do Live, que precisa estar no ar.",
)
def preparar(servidor: str) -> None:
    _preparar_ambiente()
    _todos_os_modelos()

    from apps.api.app.db.atual import banco

    with banco().sessao() as sessao:
        organizacao, contexto = _garantir_organizacao(sessao)
        configuracao = _garantir_maquina(sessao, contexto, servidor)
        configuracao = _garantir_pastas(configuracao)
        _garantir_politicas(sessao, contexto, organizacao, configuracao)

    click.echo(_resumo())


def _sessao_de_operacao(servidor: str) -> object:
    """
    Uma sessao de dono, obtida pelas portas do proprio produto.

    Nao ha atalho aqui de proposito. O caminho e o mesmo que um operador
    usaria: a prova do console (ler um arquivo na pasta do servico) troca por
    uma chave de reentrada, e a chave troca por sessao. Forjar um cookie
    exigiria o segredo de assinatura do servidor, que este processo nao tem —
    e se tivesse, o teste que valida a porta deixaria de valer alguma coisa.
    """
    import httpx

    from apps.api.app.identidade import console

    token = console.ler()
    if not token:
        click.echo(
            "Nao encontrei a prova do console. Ela e escrita quando o Live sobe.\n"
            "O servidor da vitrine esta rodando?",
            err=True,
        )
        raise SystemExit(1)

    cliente = httpx.Client(base_url=servidor, timeout=30.0, follow_redirects=True)
    resposta = cliente.post(
        "/api/auth/reentrar/emitir",
        headers={"X-AutoTarefas-Console": token},
    )
    if resposta.status_code != 200:  # noqa: PLR2004 — o unico caso de sucesso
        detalhe = resposta.json().get("detail", resposta.text)
        click.echo(f"O Live recusou emitir a chave: {detalhe}", err=True)
        raise SystemExit(1)

    # So a CHAVE, e nao a URL inteira. O endereco devolvido e montado com
    # `PUBLIC_BASE_URL` (`localhost`), e este cliente pode estar falando com
    # `127.0.0.1`: seguir a URL como veio grava o cookie num host e faz o
    # pedido seguinte no outro, e a sessao "some" sem nenhum erro visivel.
    chave = urlsplit(resposta.json()["url"]).query
    cliente.get(f"/api/auth/reentrar?{chave}")
    return cliente


def _esperar_maquina(cliente: object, limite_s: float) -> bool:
    """
    Espera o Agente abrir o canal.

    Backup nao e coisa que o servidor faca sozinho: sem canal aberto, o pedido
    seria recusado com "a maquina esta desligada" — que estaria certo, e nao
    ajudaria ninguem que acabou de subir os dois processos.
    """
    import time

    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        resposta = cliente.get("/api/agente/conectados")  # type: ignore[attr-defined]
        if resposta.status_code == 200 and any(  # noqa: PLR2004
            item["conectado"] for item in resposta.json()["conectados"]
        ):
            return True
        time.sleep(1.0)
    return False


def politicas_sem_sucesso(
    politicas: list[dict[str, object]], execucoes: list[dict[str, object]]
) -> list[dict[str, object]]:
    """
    Quais politicas ainda nao concluiram nenhuma execucao.

    E o que torna a semeadura segura de repetir: rodar de novo depois de um
    deploy nao executa backup a toa, e um ambiente que ja tem historico e
    deixado em paz.
    """
    concluidas = {
        str(item.get("politica_id"))
        for item in execucoes
        if item.get("resultado") in {"sucesso", "com_ressalva"}
    }
    return [item for item in politicas if str(item["id"]) not in concluidas]


@vitrine.command(
    name="primeira-execucao",
    help="Executa uma vez cada politica que nunca rodou.",
)
@click.option(
    "--servidor",
    default="http://127.0.0.1:7860",
    show_default=True,
    help="Endereco do Live da vitrine.",
)
@click.option(
    "--espera",
    default=60.0,
    show_default=True,
    help="Segundos para o Agente aparecer conectado.",
)
def primeira_execucao(servidor: str, espera: float) -> None:
    """
    Da ao ambiente publico um historico real desde o primeiro minuto.

    Sem isto, um ambiente recem-publicado mostra "Protecao em risco - este
    backup nunca concluiu uma execucao" ate a primeira janela do agendamento.
    E verdade, e e uma verdade inutil para quem chegou agora.

    O que roda aqui e backup de verdade: o mesmo comando, pelo mesmo canal,
    com as escolhas da propria politica. Fica registrado como MANUAL no
    historico, porque foi manual — a tela nao vai chamar isto de agendado.
    """
    _preparar_ambiente()
    _todos_os_modelos()

    cliente = _sessao_de_operacao(servidor)
    if not _esperar_maquina(cliente, espera):
        click.echo(
            "A maquina da vitrine nao apareceu conectada. Suba o Agente antes:\n"
            "  python tools/vitrine.py agente",
            err=True,
        )
        raise SystemExit(1)

    politicas = cliente.get("/api/politicas").json()["politicas"]  # type: ignore[attr-defined]
    execucoes = cliente.get("/api/historico").json()["execucoes"]  # type: ignore[attr-defined]
    pendentes = politicas_sem_sucesso(politicas, execucoes)

    if not pendentes:
        click.echo("Todas as politicas ja tem execucao concluida. Nada a fazer.")
        return

    for politica in pendentes:
        configuracao = politica["configuracao"]
        click.echo(f"Executando: {politica['nome']} ...")
        resposta = cliente.post(  # type: ignore[attr-defined]
            f"/api/dispositivos/{politica['dispositivo_id']}/backup",
            json={
                "origens": configuracao["origens"],
                "destino_externo": configuracao["destino"]["caminho"],
                "tipo_do_destino": configuracao["destino"]["tipo"],
                "usar_vss": configuracao["usar_vss"],
                "incremental": configuracao["incremental"],
                # Sem isto a execucao nasce orfa, e a proxima chamada deste
                # comando executaria tudo de novo achando que nada rodou.
                "politica_id": politica["id"],
            },
            timeout=300.0,
        )
        corpo = resposta.json()
        if resposta.status_code != 200 or not corpo.get("ok"):  # noqa: PLR2004
            click.echo(
                f"  [ERRO] {corpo.get('erro') or corpo.get('detail') or resposta.text}",
                err=True,
            )
            continue
        click.echo(f"  Concluido: {corpo.get('pacote', 'pacote gerado')}")

    click.echo(_resumo())


def _resumo() -> str:
    atual = situacao()
    destino = destino_configurado()
    aviso = ""
    if destino["tipo"] == "local":
        aviso = (
            "  |\n"
            "  |  ATENCAO: o destino e uma pasta desta maquina. O painel vai\n"
            "  |  dizer 'Protecao parcial', e esta certo: copia ao lado do\n"
            "  |  original nao sobrevive ao disco morrer. Para o painel dizer\n"
            "  |  'Protegido', aponte VITRINE_DESTINO_TIPO/CAMINHO para um\n"
            "  |  destino de verdade externo.\n"
        )
    return (
        "\n"
        "  +-- Vitrine do AutoTarefas ------------------------------------\n"
        f"  |  Organizacao: {ORGANIZACAO}\n"
        f"  |  Maquina:     {MAQUINA} ({'pareada' if atual.maquina else 'NAO pareada'})\n"
        f"  |  Pastas:      {atual.pastas}\n"
        f"  |  Politicas:   {atual.politicas} de {len(HORARIOS)}\n"
        f"  |  Destino:     {destino['tipo']} -> {destino['caminho']}\n"
        f"{aviso}"
        "  |\n"
        "  |  Falta subir o Agente, noutro terminal:\n"
        "  |    python tools/vitrine.py agente\n"
        "  +--------------------------------------------------------------\n"
    )


@vitrine.command(help="Mostra o que a vitrine ja tem.")
def estado() -> None:
    atual = situacao()
    click.echo(json.dumps(atual.__dict__ | {"completa": atual.completa}, indent=2))


@vitrine.command(help="Sobe o Agente da vitrine, em primeiro plano.")
def agente() -> None:
    """
    O Agente da vitrine, rodando como o Agente de um cliente roda.

    Em primeiro plano de proposito: quem publica poe isto sob um supervisor
    (systemd, Docker, o que for), e um processo que se desgarra do supervisor e
    um processo que ninguem reinicia quando cai.

    `subprocess`, e nao `os.execve`: no Windows o `execve` nao substitui o
    processo — ele cria outro e deixa o original terminar. O supervisor veria o
    lancador "concluir com sucesso" com o Agente ainda no ar, e depois nao
    veria mais nada. Como pai, este processo vive enquanto o Agente viver e
    devolve o codigo de saida dele.

    O endereco do Live nao e parametro: ele ja foi gravado na configuracao no
    momento do pareamento. Aceitar um aqui abriria a porta para o Agente da
    vitrine apontar para um servidor e o provisionamento para outro.
    """
    _preparar_ambiente()

    # Justificativa do B603 abaixo: ver `_agente`. Argumentos constantes.
    concluido = subprocess.run(  # noqa: S603  # nosec B603
        [
            sys.executable,
            "-m",
            "agente",
            "servico",
            "--pasta-de-configuracao",
            str(CONFIG_DO_AGENTE),
        ],
        cwd=RAIZ / "apps" / "agente",
        env=_ambiente_do_agente(),
        check=False,
    )
    raise SystemExit(concluido.returncode)


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    sys.path.insert(0, str(RAIZ / "apps" / "agente"))
    vitrine()
