"""
toc_generator.py — Gera o índice estruturado (table_of_contents) a partir dos fragmentos.

Responsabilidades:
- Agrupar fragmentos por capítulo com base nos <h1>
- Gerar estrutura JSON no formato table_of_contents
- Exportar para arquivo JSON ou retornar como dict

O formato de saída segue o padrão:
{
    "table_of_contents": [
        {
            "cap_id": "CAP 01",
            "title": "Prologue: オープニング",
            "files": ["text-000.xhtml"],
            "narrative_position": 1
        },
        ...
    ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scanner import FragmentoInfo


def gerar_table_of_contents(fragmentos: list[FragmentoInfo]) -> dict[str, list[dict[str, Any]]]:
    """
    Gera o índice estruturado (table_of_contents) a partir da lista de fragmentos.

    Parâmetros
    ----------
    fragmentos : list[FragmentoInfo]
        Lista de fragmentos ordenados numericamente.

    Retorna
    -------
    dict[str, list[dict[str, Any]]]
        Dicionário com chave "table_of_contents" contendo a lista de capítulos.
    """
    if not fragmentos:
        return {"table_of_contents": []}

    capitulos: list[dict[str, Any]] = []
    capitulo_atual: dict[str, Any] | None = None
    narrativa_posicao = 0

    for frag in fragmentos:
        if frag.tem_h1:
            # Finaliza o capítulo anterior se existir
            if capitulo_atual is not None:
                capitulos.append(capitulo_atual)

            # Inicia novo capítulo
            narrativa_posicao += 1
            cap_numero = narrativa_posicao
            capitulo_atual = {
                "cap_id": f"CAP {cap_numero:02d}",
                "title": frag.titulo or "(sem título)",
                "files": [frag.nome],
                "narrative_position": narrativa_posicao,
            }
        else:
            # Continuação do capítulo atual
            if capitulo_atual is not None:
                capitulo_atual["files"].append(frag.nome)
            else:
                # Caso edge: fragmento sem h1 antes de qualquer h1
                # Trata como parte de um "capítulo" inicial não nomeado
                if not capitulos:
                    narrativa_posicao += 1
                    capitulo_atual = {
                        "cap_id": f"CAP {narrativa_posicao:02d}",
                        "title": "(início sem título)",
                        "files": [frag.nome],
                        "narrative_position": narrativa_posicao,
                    }

    # Adiciona o último capítulo
    if capitulo_atual is not None:
        capitulos.append(capitulo_atual)

    return {"table_of_contents": capitulos}


def salvar_toc_json(toc: dict[str, list[dict[str, Any]]], caminho: str | Path) -> None:
    """
    Salva o table_of_contents em um arquivo JSON formatado.

    Parâmetros
    ----------
    toc : dict[str, list[dict[str, Any]]]
        Estrutura do table_of_contents gerada por gerar_table_of_contents().
    caminho : str | Path
        Caminho do arquivo JSON de saída.
    """
    caminho = Path(caminho)
    with caminho.open("w", encoding="utf-8") as f:
        json.dump(toc, f, indent=2, ensure_ascii=False)


def gerar_e_salvar_toc(
    fragmentos: list[FragmentoInfo],
    caminho_saida: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Gera o table_of_contents e opcionalmente salva em arquivo JSON.

    Parâmetros
    ----------
    fragmentos : list[FragmentoInfo]
        Lista de fragmentos ordenados.
    caminho_saida : str | Path | None
        Se fornecido, salva o JSON neste caminho.

    Retorna
    -------
    dict[str, list[dict[str, Any]]]
        Estrutura do table_of_contents.
    """
    toc = gerar_table_of_contents(fragmentos)

    if caminho_saida is not None:
        salvar_toc_json(toc, caminho_saida)

    return toc
