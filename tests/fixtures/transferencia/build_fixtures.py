"""
Gerador das fixtures de TRANSFERENCIA (RF-REC-003).

O par simula o caso real: um cadastro com buracos (`destino_cadastro.xlsx`)
e uma base de contatos que tem os dados (`fonte_contatos.xlsx`).

Casos plantados (chave `codigo`):

    00123  e-mail vazio no destino          -> preenchido pela fonte
    00124  e-mail antigo + telefone vazio   -> atualizado e preenchido
    00125  ja igual ao da fonte             -> mantido
    00129  nao existe na fonte              -> nao encontrado
    00130  existe so na fonte               -> sem destino para receber

A coluna `nome` existe nos dois lados com valores DIFERENTES e nunca e
autorizada nos testes: e ela que prova o criterio de aceite "campo nao
autorizado jamais alterado".

Rodar:  python tests/fixtures/transferencia/build_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

AQUI = Path(__file__).parent

DESTINO: list[list[str]] = [
    ["codigo", "nome", "email", "telefone"],
    ["00123", "Ana Lima", "", "(11) 90000-0001"],
    ["00124", "Bruno Sa", "bruno@antigo.com", ""],
    ["00125", "Carla Nunes", "carla@x.com", "(11) 90000-0003"],
    ["00129", "Zeca Sozinho", "", ""],
]

FONTE: list[list[str]] = [
    ["codigo", "nome", "email", "telefone"],
    ["00123", "Ana L.", "ana@empresa.com", "(11) 90000-0001"],
    ["00124", "Bruno S.", "bruno@empresa.com", "(21) 3344-5566"],
    ["00125", "Carla N.", "carla@x.com", "(11) 90000-0003"],
    ["00130", "Novo Contato", "novo@empresa.com", "(31) 4000-0000"],
]


def _xlsx(nome: str, linhas: list[list[str]], aba: str = "Plan1") -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = aba
    for linha in linhas:
        ws.append(linha)
    wb.save(AQUI / nome)


def main() -> None:
    _xlsx("destino_cadastro.xlsx", DESTINO)
    _xlsx("fonte_contatos.xlsx", FONTE)
    print(f"OK: 2 fixtures de transferencia em {AQUI}")


if __name__ == "__main__":
    main()
