"""
Gerador das fixtures de COMPARACAO (RF-REC-001).

Diferente das fixtures de `planilhas/`, que isolam um problema de leitura
cada uma, aqui o que importa e o PAR: `base_a` e `base_b` sao duas versoes
da mesma base, com um caso plantado por chave.

Casos plantados (a chave e `codigo`, texto com zeros a esquerda):

    00123  identico
    00124  divergente em UMA coluna (valor)
    00125  existe so em A (registro removido)
    00126  repetido em B -> conflito de chave, nunca pareado em silencio
    00127  divergente so por espacos/caixa (some com --normalizar)
    00128  existe so em B (registro novo)

`base_b.csv` tem exatamente o mesmo conteudo de `base_b.xlsx`: serve para
provar que a comparacao atravessa formatos (XLSX x CSV).

Rodar:  python tests/fixtures/comparacao/build_fixtures.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook

AQUI = Path(__file__).parent

CABECALHO = ["codigo", "nome", "cidade", "valor"]

LINHAS_A: list[list[str]] = [
    CABECALHO,
    ["00123", "Ana Lima", "Sao Paulo", "1000,00"],
    ["00124", "Bruno Sa", "Recife", "250,00"],
    ["00125", "Carla Nunes", "Curitiba", "90,00"],
    ["00126", "Diego Rocha", "Salvador", "75,50"],
    ["00127", "Elis Prado", "Belem", "300,00"],
]

LINHAS_B: list[list[str]] = [
    CABECALHO,
    ["00123", "Ana Lima", "Sao Paulo", "1000,00"],
    ["00124", "Bruno Sa", "Recife", "275,00"],
    ["00126", "Diego Rocha", "Salvador", "75,50"],
    ["00126", "Diego Rocha", "Salvador", "75,50"],
    ["00127", "  ELIS   PRADO ", "Belem", "300,00"],
    ["00128", "Fabio Reis", "Natal", "120,00"],
]


def _xlsx(nome: str, linhas: list[list[str]], aba: str = "Plan1") -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = aba
    for linha in linhas:
        ws.append(linha)
    wb.save(AQUI / nome)


def _csv(nome: str, linhas: list[list[str]]) -> None:
    # lineterminator explicito: o default do csv (\r\n) deixaria a fixture com
    # final de linha misto depois dos hooks do repositorio, e o arquivo
    # versionado deixaria de ser identico ao que este gerador produz.
    with (AQUI / nome).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(linhas)


def main() -> None:
    _xlsx("base_a.xlsx", LINHAS_A)
    _xlsx("base_b.xlsx", LINHAS_B)
    _csv("base_b.csv", LINHAS_B)
    print(f"OK: 3 fixtures de comparacao em {AQUI}")


if __name__ == "__main__":
    main()
