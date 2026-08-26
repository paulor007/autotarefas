"""Gera o executavel do Agente: um arquivo, duplo clique, sem Python instalado.

Este script roda **na maquina que publica**, e nao na do cliente. Ele produz a
base que o Live carimba e serve: mesmo executavel para todo mundo, com o
endereco e o codigo colados no fim na hora do download (ver `carimbo.py`).

Rodar:
    pip install -e ".[instalador]"
    python tools/construir_agente.py

O resultado sai em `dist-agente/AutoTarefas-Agente.exe`. Essa pasta nao e
versionada: um executavel de dezenas de megabytes no repositorio incharia o
historico para sempre, e ele se refaz a partir do codigo em um comando.

Por que `--onefile` e nao uma pasta com DLLs soltas: o cliente recebe **um**
arquivo. Uma pasta com trezentos arquivos convida a mover metade dela para o
lugar errado, e o programa quebra sem dizer por que.

Por que `--windowed` e nao console: duplo clique num programa de console abre um
retangulo preto que, para quem nao programa, parece erro. O modo servico do
proprio executavel nao precisa de console — ele nao imprime para ninguem.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 — chama o PyInstaller, com argumentos fixos
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "dist-agente"
NOME = "AutoTarefas-Agente"

#: Modulos que o PyInstaller nao enxerga sozinho. Ele segue `import` escrito no
#: codigo; o que e importado por nome, dentro de funcao, passa despercebido — e a
#: falta so aparece na maquina do cliente, no meio da instalacao.
ESCONDIDOS = (
    "apps.agente.agente.servico",
    "apps.agente.agente.janela",
    "apps.agente.agente.backup",
    "apps.agente.agente.destinos",
    "apps.agente.agente.s3",
    "apps.agente.agente.vss",
    "apps.agente.agente.retencao",
    "apps.agente.agente.agendador",
    "apps.agente.agente.artefatos",
    "apps.agente.agente.diario",
    "apps.agente.agente.instalacao",
    "autotarefas.tasks.backup",
    "autotarefas.tasks.restauracao",
    "autotarefas.tasks.cifra",
    "autotarefas.tasks.assinatura",
    "autotarefas.tasks.catalogo",
    "autotarefas.tasks.politica",
    "autotarefas.tasks.hooks",
    # `keyring` escolhe o cofre do sistema em tempo de execucao, por nome.
    "keyring.backends.Windows",
)

#: O que NAO precisa ir junto. Sao as dependencias das outras tarefas do
#: projeto: uma maquina que faz backup nao precisa de navegador automatizado nem
#: de biblioteca de planilha, e cada uma dessas somaria dezenas de megabytes ao
#: download.
DESCARTADOS = (
    "playwright",
    "pandas",
    "openpyxl",
    "bs4",
    "matplotlib",
    "numpy",
    "PIL",
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "authlib",
    "moto",
    "boto3",
    "botocore",
)


def _entrada() -> Path:
    """
    O script que o executavel roda ao subir.

    Um arquivo de tres linhas, gerado aqui: o PyInstaller precisa de um ponto de
    entrada que seja um script, e `-m pacote` nao serve. Manter isso gerado, e
    nao versionado, evita um arquivo no repositorio que so existe para o build.
    """
    alvo = SAIDA / "_entrada.py"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(
        '"""Ponto de entrada do executavel do Agente."""\n\n'
        "from apps.agente.agente.__main__ import main\n\n"
        'if __name__ == "__main__":\n'
        "    main()\n",
        encoding="utf-8",
    )
    return alvo


def construir() -> Path:
    """Constroi o executavel e devolve o caminho dele."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:  # pragma: no cover - depende do ambiente
        print('PyInstaller nao esta instalado. Rode: pip install -e ".[instalador]"')
        raise SystemExit(1) from None

    argumentos = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        NOME,
        "--distpath",
        str(SAIDA),
        "--workpath",
        str(SAIDA / "_trabalho"),
        "--specpath",
        str(SAIDA),
        "--paths",
        str(RAIZ),
        "--paths",
        str(RAIZ / "src"),
    ]
    for modulo in ESCONDIDOS:
        argumentos += ["--hidden-import", modulo]
    for modulo in DESCARTADOS:
        argumentos += ["--exclude-module", modulo]
    argumentos.append(str(_entrada()))

    print(f"Construindo {NOME}... (leva alguns minutos na primeira vez)")
    resultado = subprocess.run(argumentos, cwd=RAIZ, check=False)  # noqa: S603  # nosec B603
    if resultado.returncode != 0:
        raise SystemExit(resultado.returncode)

    executavel = SAIDA / f"{NOME}.exe"
    if not executavel.is_file():
        # Fora do Windows o PyInstaller nao poe extensao. Vale para quem estiver
        # experimentando o build em outro sistema.
        alternativo = SAIDA / NOME
        if alternativo.is_file():
            executavel = alternativo

    shutil.rmtree(SAIDA / "_trabalho", ignore_errors=True)
    return executavel


def main() -> None:
    executavel = construir()
    if not executavel.is_file():  # pragma: no cover - falha de build
        print("O executavel nao foi gerado.")
        raise SystemExit(1)

    tamanho = executavel.stat().st_size / (1024 * 1024)
    print(f"\nPronto: {executavel}  ({tamanho:.0f} MB)")
    print("O Live serve este arquivo carimbado com o endereco e o codigo de cada download.")


if __name__ == "__main__":
    main()
