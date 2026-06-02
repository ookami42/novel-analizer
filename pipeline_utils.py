"""
pipeline_utils.py — Funções utilitárias de alto nível para o pipeline.

Este módulo agrupa operações compostas (como gerar TOC + Plano) e lógica
de finalização para manter o main.py limpo e modular.
"""

from __future__ import annotations

import json
from pathlib import Path

from config import (
    PASTA_SAIDA,
    TOC_FILENAME_DEFAULT,
    PROCESSING_PLAN_FILENAME,
)
from scanner import FragmentoInfo, descobrir_fragmentos
from Check_Point import Check_Point
from toc_generator import gerar_e_salvar_toc
from processing_plan import gerar_e_salvar_plano, extrair_toc_completo
from Consolidator import Consolidator, ErroConsolidacao
from main import _log, _log_erro, _agrupar_ultimo_capitulo, _numero_capitulo, _consolidar_capitulo


def gerar_toc_e_plano(pasta_entrada: Path) -> None:
    """
    Orquestra a geração conjunta do Table of Contents (toc.json)
    e do Processing Plan (processing_plan.json).

    1. Varre os fragmentos na pasta de entrada.
    2. Gera e salva o toc.json.
    3. Verifica o checkpoint atual para determinar o próximo índice.
    4. Gera e salva o processing_plan.json com o status atualizado.
    """
    # 1. Descoberta
    fragmentos = descobrir_fragmentos(pasta_entrada)
    if not fragmentos:
        raise ValueError("Nenhum fragmento encontrado na pasta especificada.")

    # 2. Gerar TOC
    toc = gerar_e_salvar_toc(fragmentos, TOC_FILENAME_DEFAULT)
    print(f"\nTable of Contents gerado com {len(toc['table_of_contents'])} capítulo(s).")
    print(f"Salvo em: {TOC_FILENAME_DEFAULT.resolve()}")

    # 3. Determinar estado atual (próximo índice)
    checkpoint = Check_Point(PASTA_SAIDA)
    try:
        estado = checkpoint.carregar()
        proximo_indice = estado.proximo_indice
    except Exception:
        # Se não houver checkpoint válido, começa do 0
        proximo_indice = 0

    # 4. Gerar Plano de Processamento
    plano = gerar_e_salvar_plano(
        fragmentos,
        PASTA_SAIDA,
        proximo_indice,
        caminho_saida=PROCESSING_PLAN_FILENAME,
    )
    
    # Extrair contagem de pendentes para log
    pending_count = len(plano.get('pending_chapters', []))
    print(f"Processing Plan gerado com {len(plano['table_of_contents'])} capítulo(s) no total.")
    print(f"Capítulos pendentes: {pending_count}")
    print(f"Salvo em: {PROCESSING_PLAN_FILENAME.resolve()}")


def finalizar_capitulos_pendentes(
    fragmentos: list[FragmentoInfo], 
    consolidador: Consolidator, 
    toc_info: dict
) -> None:
    """
    Identifica e consolida o último capítulo da obra, caso ainda não tenha sido consolidado.
    
    Esta função deve ser chamada ao final do loop principal de processamento
    para garantir que o último bloco de fragmentos (após o último H1) seja transformado
    em um arquivo de capítulo consolidado.
    """
    indices_ultimo_cap = _agrupar_ultimo_capitulo(fragmentos)
    
    if not indices_ultimo_cap:
        return

    num_ultimo = _numero_capitulo(fragmentos, indices_ultimo_cap[0])

    if num_ultimo is None:
        _log_erro("Não foi possível determinar o número do último capítulo.")
        return

    if consolidador.capitulo_existe(num_ultimo):
        _log(f"  → Capítulo {num_ultimo:03d} já consolidado — pulando finalização.")
        return

    _log(f"Finalizando capítulo {num_ultimo:03d} ({len(indices_ultimo_cap)} fragmentos)...")
    
    json_final = _consolidar_capitulo(
        consolidador, 
        num_ultimo, 
        indices_ultimo_cap, 
        toc_info
    )
    
    if json_final is None:
        _log_erro(f"Consolidação do último capítulo ({num_ultimo:03d}) falhou.")
    else:
        _log(f"Capítulo {num_ultimo:03d} finalizado com sucesso.")