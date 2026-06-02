"""
processing_plan.py — Gera um plano de processamento baseado no estado atual e no TOC.

Responsabilidades:
- Analisar quais fragmentos já foram processados
- Identificar capítulos pendentes de consolidação
- Gerar JSON com o plano de execução restante
- Fornecer informações contextuais para o PromptBuilder

O formato de saída segue o padrão:
{
    "table_of_contents": [
        {
            "cap_id": "CAP 01",
            "title": "Prologue: オープニング",
            "files": ["text-000.xhtml"],
            "narrative_position": 1,
            "status": "completed|pending|partial",
            "processed_fragments": ["analise-fragmento-000.md"],
            "consolidated": true
        },
        ...
    ],
    "next_fragment_index": 5,
    "total_fragments": 30,
    "pending_chapters": 8
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from Check_Point import Check_Point
from Consolidator import Consolidator
from scanner import FragmentoInfo


def gerar_plano_processamento(
    fragmentos: list[FragmentoInfo],
    pasta_saida: Path,
    proximo_indice: int,
) -> dict[str, Any]:
    """
    Gera o plano de processamento a partir da lista de fragmentos e estado atual.

    Parâmetros
    ----------
    fragmentos : list[FragmentoInfo]
        Lista de fragmentos ordenados numericamente.
    pasta_saida : Path
        Pasta onde estão os arquivos de análise e consolidados.
    proximo_indice : int
        Índice do próximo fragmento a ser processado (0-based).

    Retorna
    -------
    dict[str, Any]
        Dicionário com o plano de processamento completo.
    """
    if not fragmentos:
        return {
            "table_of_contents": [],
            "next_fragment_index": 0,
            "total_fragments": 0,
            "pending_chapters": 0,
        }

    # Agrupar fragmentos por capítulo
    capitulos_map: dict[str, dict[str, Any]] = {}
    capitulo_atual: dict[str, Any] | None = None
    narrativa_posicao = 0

    for frag in fragmentos:
        if frag.tem_h1:
            # Finaliza o capítulo anterior se existir
            if capitulo_atual is not None:
                capitulos_map[capitulo_atual["cap_id"]] = capitulo_atual

            # Inicia novo capítulo
            narrativa_posicao += 1
            cap_numero = narrativa_posicao
            capitulo_atual = {
                "cap_id": f"CAP {cap_numero:02d}",
                "title": frag.titulo or "(sem título)",
                "files": [frag.nome],
                "narrative_position": narrativa_posicao,
                "fragment_indices": [frag.indice],
            }
        else:
            # Continuação do capítulo atual
            if capitulo_atual is not None:
                capitulo_atual["files"].append(frag.nome)
                capitulo_atual["fragment_indices"].append(frag.indice)

    # Adiciona o último capítulo
    if capitulo_atual is not None:
        capitulos_map[capitulo_atual["cap_id"]] = capitulo_atual

    # Instanciar consolidator para verificar status
    consolidador = Consolidator(pasta_saida)

    # Construir lista final com status
    table_of_contents: list[dict[str, Any]] = []
    pending_chapters = 0

    for cap_id in sorted(capitulos_map.keys()):
        cap_info = capitulos_map[cap_id]
        fragment_indices = cap_info.pop("fragment_indices")

        # Determinar status de processamento
        fragments_processed = []
        all_processed = True
        any_processed = False

        for idx in fragment_indices:
            analise_path = pasta_saida / f"analise-fragmento-{idx:03d}.md"
            if analise_path.exists():
                fragments_processed.append(f"analise-fragmento-{idx:03d}.md")
                any_processed = True
            else:
                all_processed = False

        # Verificar se capítulo está consolidado
        numero_capitulo = int(cap_id.split()[-1])
        consolidated = consolidador.capitulo_existe(numero_capitulo)

        # Determinar status geral
        if all_processed and consolidated:
            status = "completed"
        elif any_processed or consolidated:
            status = "partial"
            pending_chapters += 1
        else:
            status = "pending"
            pending_chapters += 1

        cap_entry = {
            "cap_id": cap_info["cap_id"],
            "title": cap_info["title"],
            "files": cap_info["files"],
            "narrative_position": cap_info["narrative_position"],
            "status": status,
            "processed_fragments": fragments_processed,
            "consolidated": consolidated,
        }

        table_of_contents.append(cap_entry)

    return {
        "table_of_contents": table_of_contents,
        "next_fragment_index": proximo_indice,
        "total_fragments": len(fragmentos),
        "pending_chapters": pending_chapters,
    }


def salvar_plano_json(plano: dict[str, Any], caminho: str | Path) -> None:
    """
    Salva o plano de processamento em um arquivo JSON formatado.

    Parâmetros
    ----------
    plano : dict[str, Any]
        Estrutura do plano gerada por gerar_plano_processamento().
    caminho : str | Path
        Caminho do arquivo JSON de saída.
    """
    caminho = Path(caminho)
    with caminho.open("w", encoding="utf-8") as f:
        json.dump(plano, f, indent=2, ensure_ascii=False)


def gerar_e_salvar_plano(
    fragmentos: list[FragmentoInfo],
    pasta_saida: Path,
    proximo_indice: int,
    caminho_saida: str | Path | None = None,
) -> dict[str, Any]:
    """
    Gera o plano de processamento e opcionalmente salva em arquivo JSON.

    Parâmetros
    ----------
    fragmentos : list[FragmentoInfo]
        Lista de fragmentos ordenados.
    pasta_saida : Path
        Pasta de saída para verificar estado dos arquivos.
    proximo_indice : int
        Índice do próximo fragmento a processar.
    caminho_saida : str | Path | None
        Se fornecido, salva o JSON neste caminho.

    Retorna
    -------
    dict[str, Any]
        Estrutura do plano de processamento.
    """
    plano = gerar_plano_processamento(fragmentos, pasta_saida, proximo_indice)

    if caminho_saida is not None:
        salvar_plano_json(plano, caminho_saida)

    return plano


def extrair_toc_completo(plano: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extrai apenas a lista table_of_contents do plano, sem informações de status.

    Útil para injetar no prompt_builder como contexto da obra.

    Parâmetros
    ----------
    plano : dict[str, Any]
        Plano de processamento completo.

    Retorna
    -------
    list[dict[str, Any]]
        Lista de capítulos no formato TOC padrão.
    """
    toc_completo = []
    for cap in plano.get("table_of_contents", []):
        toc_completo.append({
            "cap_id": cap["cap_id"],
            "title": cap["title"],
            "files": cap["files"],
            "narrative_position": cap["narrative_position"],
        })
    return toc_completo
