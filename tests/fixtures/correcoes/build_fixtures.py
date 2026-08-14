"""
Gerador da fixture de CORRECOES CONFIRMADAS (RF-PLA-010).

`base_para_corrigir.xlsx` tem, de proposito, os tres casos que as regras
sabem tratar e um que elas NAO sabem:

    UF escrita por extenso        -> de_para
    situacao com caixa trocada    -> padronizar
    coluna origem vazia           -> preencher
    UF desconhecida ("Sao Jorge") -> item para revisao

`regras.yaml` e o arquivo de regras confirmadas correspondente.

Rodar:  python tests/fixtures/correcoes/build_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

AQUI = Path(__file__).parent

LINHAS: list[list[str]] = [
    ["codigo", "cliente", "uf", "situacao", "origem"],
    ["00123", "Ana Lima", "Sao Paulo", "ATIVO", ""],
    ["00124", "Bruno Sa", "rio de janeiro", "inativo", ""],
    ["00125", "Carla Nunes", "SP", "Ativo", "sistema"],
    ["00126", "Diego Rocha", "Sao Jorge", "Ativo", ""],
]

REGRAS = """\
# Regras CONFIRMADAS de correcao (RF-PLA-010).
# Nada e corrigido fora do que esta declarado aqui.
correcoes:
  - coluna: uf
    tipo: de_para
    mapa:
      "sao paulo": SP
      "rio de janeiro": RJ
    fora_da_regra: revisao

  - coluna: situacao
    tipo: padronizar
    valores: [Ativo, Inativo]
    fora_da_regra: revisao

  - coluna: origem
    tipo: preencher
    valor: planilha
"""


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"
    for linha in LINHAS:
        ws.append(linha)
    wb.save(AQUI / "base_para_corrigir.xlsx")

    (AQUI / "regras.yaml").write_text(REGRAS, encoding="utf-8", newline="\n")
    print(f"OK: fixtures de correcoes em {AQUI}")


if __name__ == "__main__":
    main()
