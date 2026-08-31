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
import os
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import click

RAIZ = Path(__file__).resolve().parents[1]

#: Onde a vitrine mora. Pasta de runtime, coberta pelo `.gitignore`.
#:
#: `VITRINE_CASA` existe por duas razoes praticas: publicar num servidor em que
#: o dado nao deve morar dentro do repositorio, e permitir que a homologacao de
#: ponta a ponta monte uma vitrine descartavel numa pasta temporaria — usando
#: esta mesma ferramenta, e nao uma copia dela que poderia divergir.
CASA = Path(os.environ.get("VITRINE_CASA") or (RAIZ / ".autotarefas" / "vitrine"))

BANCO = CASA / "vitrine.db"
CONFIG_DO_AGENTE = CASA / "agente"
#: A pasta protegida. O nome e escolhido para ser LIDO: a tela publica mostra
#: o ultimo trecho do caminho, e "dados" nao diz nada.
#:
#: Neutro de proposito. "Dados administrativos" ou "Financeiro" sugeririam que
#: este ambiente pertence a um setor — e ele nao pertence a nenhum: e o
#: ambiente do projeto, e o produto serve a qualquer pasta.
DADOS = CASA / "Dados do ambiente"
DESTINO = CASA / "destino"

#: Variaveis de ambiente que carregam o balde da vitrine para o cofre.
#:
#: Ficam no ambiente de quem publica, e nunca no repositorio: sao a chave de
#: uma conta de verdade. Daqui elas vao para o cofre da organizacao, cifradas,
#: e saem so para viajar pelo canal autenticado ate a maquina no momento do
#: envio. Nao passam pelo navegador e nao sao gravadas no disco do Agente.
OBRIGATORIOS_DE_NUVEM = ("VITRINE_S3_BALDE", "VITRINE_S3_CHAVE", "VITRINE_S3_SEGREDO")

#: Os opcionais. Endpoint vazio = Amazon S3; prefixo vazio = raiz do balde.
OPCIONAIS_DE_NUVEM = ("VITRINE_S3_ENDPOINT", "VITRINE_S3_REGIAO", "VITRINE_S3_PREFIXO")

ORGANIZACAO = "AutoTarefas Demonstracao"
EMAIL_DO_DONO = "operacao@demonstracao.autotarefas"
MAQUINA = "SERVIDOR-01"

#: Quatro politicas diarias, em horarios diferentes.
#:
#: Nao e enfeite: com uma so, um visitante estaria em media doze horas depois
#: da ultima execucao, e o painel mostraria evidencia velha. Com quatro, ele
#: raramente esta a mais de seis horas — e cada uma e uma politica diaria de
#: verdade, com retencao que faz sentido, sem inventar frequencia que o motor
#: nao tem.
HORARIOS = ("03:00", "09:00", "15:00", "21:00")

#: Marca que todo arquivo de exemplo carrega na primeira linha.
#:
#: Um arquivo restaurado sai do pacote sozinho, longe daqui. Numeros plausiveis
#: sem nenhuma marca seriam confundidos com dado de alguem — e a pessoa que
#: encontrasse a planilha teria de perguntar a alguem de onde ela veio.
MARCA = "Arquivo sintetico do ambiente publico do AutoTarefas. Nao contem dado real."

#: Quantas linhas cada conjunto gerado tem.
#:
#: O tamanho e uma decisao de apresentacao, e nao de teste: um historico de
#: pacotes de 2 KB passa a impressao de brinquedo, e o produto e sobre proteger
#: o trabalho de alguem. O alvo aqui e um pacote de algumas centenas de KB —
#: representativo o bastante para ser levado a serio, pequeno o bastante para
#: nao ocupar disco a toa (a retencao guarda ate dez pacotes por politica, dos
#: dois lados).
LINHAS_POR_MES = 6000
LINHAS_DO_INVENTARIO = 10000
LINHAS_DO_REGISTRO = 8000

#: Meses cobertos pelas planilhas mensais.
MESES = 12


def _valor(indice: int, teto: int) -> int:
    """
    Numero variado e **deterministico**, sem `random`.

    Deterministico importa por dois motivos: reprovisionar produz exatamente o
    mesmo conteudo (entao o incremental nao acusa mudanca que nao houve), e o
    tamanho do pacote nao oscila entre uma execucao e outra.

    Variado importa porque o pacote e um ZIP: mil linhas iguais comprimem a
    quase nada, e o historico voltaria a mostrar um numero que nao representa
    o trabalho de comprimir nada.
    """
    return (indice * 7919 + 104_729) % teto


def _planilha_mensal(mes: int) -> str:
    """Uma planilha de movimentacoes do mes, com cabecalho que se declara."""
    linhas = [
        f"# {MARCA}",
        "identificador,data,categoria,quantidade,valor,referencia",
    ]
    for i in range(LINHAS_POR_MES):
        dia = 1 + _valor(i + mes, 28)
        categoria = "ABCDEF"[_valor(i, 6)]
        quantidade = 1 + _valor(i * 3, 400)
        valor = _valor(i * 11, 900_000) / 100
        referencia = f"REF-{mes:02d}{_valor(i * 5, 100_000):05d}"
        linhas.append(
            f"{i:06d},2026-{mes:02d}-{dia:02d},Categoria {categoria},"
            f"{quantidade},{valor:.2f},{referencia}"
        )
    return "\n".join(linhas) + "\n"


def _inventario() -> str:
    linhas = [f"# {MARCA}", "codigo,descricao,unidade,saldo,posicao"]
    for i in range(LINHAS_DO_INVENTARIO):
        linhas.append(
            f"ITEM-{i:06d},Item sintetico {i},"
            f"{'UN' if i % 2 else 'CX'},{_valor(i * 13, 5000)},"
            f"P{_valor(i, 40):02d}-{_valor(i * 3, 20):02d}"
        )
    return "\n".join(linhas) + "\n"


def _registro_de_operacoes() -> str:
    linhas = [f"# {MARCA}"]
    for i in range(LINHAS_DO_REGISTRO):
        hora = _valor(i, 24)
        minuto = _valor(i * 7, 60)
        linhas.append(
            f"2026-08-{1 + _valor(i, 28):02d} {hora:02d}:{minuto:02d}:00 "
            f"operacao={_valor(i * 17, 9999):04d} "
            f"estado={'concluida' if i % 3 else 'reprocessada'} "
            f"duracao_ms={_valor(i * 29, 4000)}"
        )
    return "\n".join(linhas) + "\n"


def _documento(titulo: str, paragrafos: int) -> str:
    # A marca vem ANTES do titulo, como nos CSV: quem abre o arquivo restaurado
    # le a primeira linha, e a primeira linha precisa dizer o que ele e.
    corpo = [MARCA, "", f"{titulo.upper()} (exemplo)", ""]
    for i in range(paragrafos):
        corpo.append(
            f"Secao {i + 1}. Texto sintetico gerado para dar volume ao "
            "ambiente publico do AutoTarefas. Nao descreve procedimento real "
            "de nenhuma organizacao, e nao substitui documento algum."
        )
        corpo.append("")
    return "\n".join(corpo)


@lru_cache(maxsize=1)
def exemplos() -> dict[str, str]:
    """
    Os arquivos de exemplo do ambiente publico.

    Sinteticos, e obviamente sinteticos: nenhum dado real de ninguem entra num
    ambiente publico. Cada arquivo se declara na primeira linha, inclusive os
    CSV.

    Os nomes sao neutros de proposito. Uma pasta chamada "financeiro" ou
    "administrativo" sugeriria que este ambiente pertence a um setor, quando
    ele nao pertence a nenhum: e o ambiente do projeto, e o produto serve a
    qualquer pasta.

    Gerado sob demanda e guardado em cache: sao alguns megabytes de texto, e
    monta-los no import faria toda importacao do modulo — inclusive nos testes
    — pagar por isso.
    """
    arquivos: dict[str, str] = {
        "planilhas/inventario.csv": _inventario(),
        "registros/operacoes.log": _registro_de_operacoes(),
        "documentos/procedimentos.txt": _documento("Procedimentos internos", 40),
        "documentos/politica-de-guarda.txt": _documento("Politica de guarda", 30),
        "documentos/manual-de-uso.txt": _documento("Manual de uso", 35),
    }
    for mes in range(1, MESES + 1):
        arquivos[f"planilhas/movimentacoes-2026-{mes:02d}.csv"] = _planilha_mensal(mes)
    return arquivos


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
    if tipo == "nuvem":
        # `nuvem` nao usa caminho em disco: o balde vem do cofre da
        # organizacao. Recusar aqui, com a razao, evita o provisionamento
        # morrer com um 400 no meio das quatro politicas.
        faltando = [nome for nome in OBRIGATORIOS_DE_NUVEM if not os.environ.get(nome)]
        if faltando:
            msg = (
                "VITRINE_DESTINO_TIPO=nuvem exige as credenciais do balde no "
                f"ambiente. Falta: {', '.join(faltando)}. Sem elas o pacote "
                "seria feito e nao teria para onde ir — e o painel contaria a "
                "politica como protecao."
            )
            raise SystemExit(msg)
        return {"tipo": "nuvem", "caminho": ""}
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
    for relativo, conteudo in exemplos().items():
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
    _guardar_balde(sessao, contexto)
    return organizacao, contexto


def _guardar_balde(sessao: object, contexto: object) -> None:
    """
    Leva o balde do ambiente para o cofre da organizacao, cifrado.

    Roda sempre que o provisionamento roda, e nao so na primeira vez: girar a
    chave da conta de nuvem passa a ser trocar a variavel e reprovisionar.

    Nada e ecoado. Um `click.echo` com o valor colocaria a chave da conta no
    terminal de quem publica e no historico do shell — que e onde segredo mais
    vaza sem ninguem querer.
    """
    import os

    from apps.api.app import cofre

    if not all(os.environ.get(nome) for nome in OBRIGATORIOS_DE_NUVEM):
        return

    for variavel in (*OBRIGATORIOS_DE_NUVEM, *OPCIONAIS_DE_NUVEM):
        valor = os.environ.get(variavel, "").strip()
        if not valor:
            continue
        nome = "s3." + variavel.removeprefix("VITRINE_S3_").lower()
        cofre.guardar(sessao, contexto, nome=nome, valor=valor)  # type: ignore[arg-type]
    click.echo("Credencial de nuvem guardada no cofre da organizacao.", flush=True)


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


@vitrine.command(help="Imprime um link para entrar na vitrine como DONO.")
@click.option(
    "--servidor",
    default="http://127.0.0.1:7860",
    show_default=True,
    help="Endereco do Live, que precisa estar no ar.",
)
def entrar(servidor: str) -> None:
    """
    O link de quem ADMINISTRA a vitrine, e nao o de quem a visita.

    Sao duas portas diferentes, e a confusao entre elas custa tempo: abrir
    `/app` no navegador entra como **visitante**, em sessao somente leitura —
    e ai nao ha o que testar, porque nada muda. Para criar politica, executar
    backup ou restaurar, e preciso ser o dono.

    A prova exigida e ler um arquivo dentro da pasta do servico, que e a mesma
    do console. Quem consegue isso ja podia abrir o banco, que tem muito mais.

    O link vale uma vez e vence rapido. Perdeu, rode de novo.
    """
    _preparar_ambiente()

    chave = _chave_de_reentrada(servidor)
    click.echo("")
    click.echo("  Abra este endereco no navegador para entrar como DONO:")
    click.echo("")
    click.echo(f"    {servidor}/api/auth/reentrar?{chave}")
    click.echo("")
    click.echo("  Vale uma vez. Para ver o que um visitante ve, abra /app numa")
    click.echo("  janela anonima — la a sessao e somente leitura.")
    click.echo("", nl=True)


def _chave_de_reentrada(servidor: str) -> str:
    """
    Troca a prova do console por uma chave de reentrada.

    Devolve so a QUERY, e nao a URL montada pelo servidor: aquela vem com
    `PUBLIC_BASE_URL`, que pode estar em `localhost` enquanto quem chama fala
    com `127.0.0.1`. Cookie gravado num host e pedido seguinte no outro faz a
    sessao "sumir" sem nenhum erro visivel.
    """
    import httpx

    from apps.api.app.identidade import console

    token = console.ler()
    if not token:
        click.echo(
            "Nao encontrei a prova do console. Ela e escrita quando o Live sobe.\n"
            "O servidor da vitrine esta rodando? (python tools/servir_vitrine.py)",
            err=True,
        )
        raise SystemExit(1)

    try:
        resposta = httpx.post(
            f"{servidor}/api/auth/reentrar/emitir",
            headers={"X-AutoTarefas-Console": token},
            timeout=30.0,
        )
    except httpx.HTTPError as erro:
        click.echo(f"Nao foi possivel falar com o Live em {servidor}: {erro}", err=True)
        raise SystemExit(1) from erro

    if resposta.status_code != 200:  # noqa: PLR2004 — o unico caso de sucesso
        detalhe = resposta.json().get("detail", resposta.text)
        click.echo(f"O Live recusou emitir a chave: {detalhe}", err=True)
        raise SystemExit(1)

    return urlsplit(resposta.json()["url"]).query


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
