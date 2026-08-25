"""O pacote do Agente que o cliente baixa pelo Live.

Sem isto, "instale o Agente" significaria clonar um repositorio — o que exclui
exatamente as empresas para quem este produto existe. A tela precisa oferecer um
arquivo, e o arquivo precisa conter tudo que a maquina vai executar.

O que vai dentro:

- `apps/agente/agente/` — o Agente;
- `autotarefas/` — o nucleo que ele usa (backup, cifra, assinatura, catalogo);
- `requisitos.txt` — so o que o Agente precisa. Nao e a lista do projeto
  inteiro: uma maquina de escritorio que faz backup nao deve instalar navegador
  automatizado nem biblioteca de planilha para copiar uma pasta;
- `instalar.ps1` e `LEIA-ME.txt` — os passos, escritos para quem nao programa.

O que **nao** vai, e a lista importa mais que a de cima: nenhum `.env`, nenhum
banco, nenhuma configuracao de dispositivo, nenhum teste, nenhum `__pycache__`.
Um instalador que carrega segredo do servidor os distribui para todo cliente que
baixar — e nao ha como recolher depois.

O pacote e montado na hora, a partir do codigo que este servidor esta rodando.
Guardar um ZIP pronto criaria a chance de o cliente baixar uma versao mais velha
que o servidor com quem ele vai conversar.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .identidade.dependencias import ContextoAtual

#: Pasta que aparece dentro do ZIP. Uma so, para o arquivo nao explodir na
#: pasta de Downloads de quem extrair sem olhar.
RAIZ = "AutoTarefas-Agente"

#: Nome do arquivo baixado.
NOME_DO_ARQUIVO = "autotarefas-agente.zip"

#: O que o Agente precisa de verdade, medido pelo que ele importa. As faixas
#: acompanham as do `pyproject.toml` do projeto.
REQUISITOS = """\
# Dependencias do Agente do AutoTarefas.
#
# So o que o Agente usa. A lista do projeto inteiro traria pandas, playwright e
# openpyxl — uma maquina que faz backup nao precisa de navegador automatizado
# para copiar uma pasta.
click>=8.4.0,<9.0.0
loguru>=0.7.3,<1.0.0
pydantic>=2.13.0,<3.0.0
pydantic-settings>=2.14.0,<3.0.0
httpx>=0.28.1,<1.0.0
websockets>=13.0,<16.0
cryptography>=48.0.0,<49.0.0
pyzipper>=0.3.6,<1.0.0
keyring>=25.0.0,<26.0.0
rich>=15.0.0,<16.0.0

# Só para destino em nuvem compativel com S3. Pode remover se o backup vai para
# disco local, disco externo ou pasta de rede.
boto3>=1.35.0,<2.0.0
"""

#: Nunca entram no pacote. Segredo distribuido nao se recolhe.
PROIBIDOS = (".env", ".db", ".sqlite", ".key", ".pem", ".pfx")

#: Pastas que nao interessam a quem vai apenas rodar o Agente.
DESCARTAVEIS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "tests")


def raiz_do_projeto() -> Path:
    """Pasta do repositorio, a partir deste arquivo."""
    return Path(__file__).resolve().parents[3]


def _interessa(caminho: Path) -> bool:
    """
    Este arquivo entra no pacote?

    Falha fechada quanto a segredo: extensao suspeita fica de fora mesmo que
    esteja numa pasta que, em tese, so tem codigo.
    """
    if caminho.suffix in {".pyc", ".pyo"}:
        return False
    if caminho.suffix in PROIBIDOS or caminho.name.startswith(".env"):
        return False
    return all(parte not in DESCARTAVEIS for parte in caminho.parts)


def _acrescentar(pacote: zipfile.ZipFile, origem: Path, destino: str) -> int:
    """Copia uma arvore para dentro do ZIP. Devolve quantos arquivos entraram."""
    quantos = 0
    for arquivo in sorted(origem.rglob("*")):
        if not arquivo.is_file():
            continue
        relativo = arquivo.relative_to(origem)
        if not _interessa(relativo) or not _interessa(arquivo):
            continue
        pacote.write(arquivo, f"{RAIZ}/{destino}/{relativo.as_posix()}")
        quantos += 1
    return quantos


def montar(servidor: str = "") -> bytes:
    """
    Monta o ZIP do Agente, agora, a partir do codigo deste servidor.

    `servidor` entra no LEIA-ME para a pessoa nao precisar digitar o endereco de
    cabeca. E texto de instrucao, e nao configuracao: o pareamento continua
    exigindo o codigo temporario, que e a autorizacao de verdade.
    """
    raiz = raiz_do_projeto()
    memoria = io.BytesIO()

    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as pacote:
        _acrescentar(pacote, raiz / "apps" / "agente" / "agente", "apps/agente/agente")
        _acrescentar(pacote, raiz / "src" / "autotarefas", "autotarefas")

        # Os `__init__.py` que fazem `apps.agente.agente` ser importavel. Sem
        # eles o comando registrado no Agendador nao acha o modulo.
        pacote.writestr(f"{RAIZ}/apps/__init__.py", '"""Pacote do Agente."""\n')
        pacote.writestr(f"{RAIZ}/apps/agente/__init__.py", '"""Pacote do Agente."""\n')

        pacote.writestr(f"{RAIZ}/requisitos.txt", REQUISITOS)
        pacote.writestr(f"{RAIZ}/instalar.ps1", _script(servidor))
        pacote.writestr(f"{RAIZ}/LEIA-ME.txt", _leia_me(servidor))

    return memoria.getvalue()


def _script(servidor: str) -> str:
    """
    O script que faz a instalacao, com um passo por linha visivel.

    Nao pede elevacao e nao instala Python: um instalador que se eleva sozinho
    ensina o cliente a clicar "sim" em janelas que ele nao leu, e um que instala
    Python por conta propria mexe no que nao e dele.
    """
    endereco = servidor or "https://SEU-LIVE"
    return f"""\
# Instalador do Agente do AutoTarefas.
#
# Nao pede elevacao e nao instala Python. Se faltar Python, o script para e diz
# — e melhor do que mexer no sistema de alguem sem avisar.
#
# Uso:
#   .\\instalar.ps1 -Codigo ABC123
#   .\\instalar.ps1 -Codigo ABC123 -Servidor {endereco} -Pasta C:\\AutoTarefas

param(
    [Parameter(Mandatory=$true)][string]$Codigo,
    [string]$Servidor = "{endereco}",
    [string]$Pasta = "$env:LOCALAPPDATA\\AutoTarefas\\Agente",
    [string]$Nome = $env:COMPUTERNAME
)

$ErrorActionPreference = "Stop"
$origem = $PSScriptRoot

Write-Host "1/5  Conferindo o Python..."
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {{
    Write-Host "Nao encontrei o Python nesta maquina." -ForegroundColor Red
    Write-Host "Instale a versao 3.13 em https://www.python.org/downloads/ e rode de novo."
    exit 1
}}

Write-Host "2/5  Copiando o Agente para $Pasta..."
New-Item -ItemType Directory -Force -Path $Pasta | Out-Null
Copy-Item -Path (Join-Path $origem "apps") -Destination $Pasta -Recurse -Force
Copy-Item -Path (Join-Path $origem "autotarefas") -Destination $Pasta -Recurse -Force
Copy-Item -Path (Join-Path $origem "requisitos.txt") -Destination $Pasta -Force

Write-Host "3/5  Preparando o ambiente (isso demora um pouco na primeira vez)..."
& python -m venv (Join-Path $Pasta "venv")
$venvPython = Join-Path $Pasta "venv\\Scripts\\python.exe"
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r (Join-Path $Pasta "requisitos.txt") --quiet

Write-Host "4/5  Pareando esta maquina..."
Push-Location $Pasta
& $venvPython -m apps.agente.agente parear --servidor $Servidor --codigo $Codigo --nome $Nome
if ($LASTEXITCODE -ne 0) {{ Pop-Location; exit $LASTEXITCODE }}

Write-Host "5/5  Registrando para subir sozinho..."
& $venvPython -m apps.agente.agente instalar-servico
Pop-Location

Write-Host ""
Write-Host "Pronto. Agora autorize as pastas que o Agente pode ler:" -ForegroundColor Green
Write-Host "  cd $Pasta"
Write-Host "  .\\venv\\Scripts\\python.exe -m apps.agente.agente autorizar C:\\caminho\\da\\pasta"
Write-Host ""
Write-Host "A autorizacao e dada AQUI, nesta maquina. Nenhuma tela na nuvem"
Write-Host "concede acesso ao disco de ninguem."
"""


def _leia_me(servidor: str) -> str:
    endereco = servidor or "o endereco do seu Live"
    return f"""\
AGENTE DO AUTOTAREFAS
=====================

Este pacote instala o programa que faz o backup NA SUA MAQUINA. Ele existe
porque o navegador nao alcanca o disco de ninguem: proteger uma pasta local,
com horario e destino externo, exige um programa instalado aqui.

O QUE VOCE PRECISA ANTES
------------------------
1. Python 3.13 instalado (https://www.python.org/downloads/).
   Marque "Add Python to PATH" na instalacao.
2. O codigo de pareamento, gerado no Live em "Sua empresa" > "Parear nova
   maquina". Ele vale poucos minutos e serve uma vez so.

COMO INSTALAR
-------------
1. Extraia esta pasta em algum lugar (a area de trabalho serve).
2. Clique com o botao direito na pasta e escolha "Abrir no Terminal".
3. Rode:

       .\\instalar.ps1 -Codigo SEU-CODIGO -Servidor {endereco}

Se o Windows recusar por politica de execucao, rode antes:

       Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

DEPOIS DE INSTALAR
------------------
Autorize as pastas que o Agente pode ler. Isso e feito AQUI, nesta maquina:

       cd "$env:LOCALAPPDATA\\AutoTarefas\\Agente"
       .\\venv\\Scripts\\python.exe -m apps.agente.agente autorizar C:\\caminho\\da\\pasta

Nenhuma tela na nuvem concede acesso ao disco. O Live pede; esta maquina
autoriza. Se o servidor for comprometido, ele continua sem alcancar arquivo
nenhum que voce nao tenha liberado aqui.

PARA CONFERIR
-------------
       .\\venv\\Scripts\\python.exe -m apps.agente.agente estado

Mostra o servidor, a impressao digital desta maquina (confira se e a mesma que
aparece no Live), as pastas autorizadas e se o Agente sobe sozinho.

O QUE ESTE PACOTE NAO FAZ
-------------------------
- Nao instala Python.
- Nao pede elevacao. O modo padrao dispara quando voce ENTRA no Windows.
  Para rodar com a maquina ligada e ninguem logado, use
  'instalar-servico --ao-ligar' num terminal de administrador.
- Nao contem segredo nenhum: nem chave, nem senha, nem configuracao de outro
  cliente. A identidade desta maquina e criada aqui, no pareamento.
"""


# ============================================================
# Rotas
# ============================================================

roteador = APIRouter(prefix="/api/agente", tags=["agente"])


@roteador.get("/instalador")
def baixar_instalador(contexto: ContextoAtual) -> StreamingResponse:
    """
    Entrega o pacote do Agente.

    Exige sessao: o pacote nao carrega segredo, mas tambem nao precisa ficar
    disponivel para a internet inteira.
    """
    del contexto
    dados = montar()
    return StreamingResponse(
        io.BytesIO(dados),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{NOME_DO_ARQUIVO}"',
            "Content-Length": str(len(dados)),
        },
    )


@roteador.get("/instalador/ficha")
def ficha_do_instalador(contexto: ContextoAtual) -> dict[str, Any]:
    """
    Tamanho e conteudo do pacote, para a tela dizer o que vai ser baixado.

    Um botao de download que nao diz o tamanho nem o que vem dentro pede um ato
    de fe que ninguem deveria ter que dar.
    """
    del contexto
    dados = montar()
    with zipfile.ZipFile(io.BytesIO(dados)) as pacote:
        arquivos = len(pacote.namelist())
    return {
        "nome": NOME_DO_ARQUIVO,
        "tamanho_bytes": len(dados),
        "arquivos": arquivos,
        "precisa_de_python": "3.13",
    }


__all__ = ["NOME_DO_ARQUIVO", "RAIZ", "REQUISITOS", "montar", "roteador"]
