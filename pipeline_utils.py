"""
pipeline_utils.py — Funções utilitárias de alto nível para o pipeline.

Este módulo agrupa operações compostas (como gerar TOC + Plano) e lógica
de finalização para manter o main.py limpo e modular.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from Check_Point import Check_Point
from Consolidator import Consolidator, ErroConsolidacao
from config import (
    LOG_VERBOSO,
    PARAR_NO_ERRO,
    PASTA_SAIDA,
    PROCESSING_PLAN_FILENAME,
    TOC_FILENAME_DEFAULT,
)
from logger import log, log_erro
from processing_plan import extrair_toc_completo, gerar_e_salvar_plano
from scanner import FragmentoInfo, descobrir_fragmentos
from toc_generator import gerar_e_salvar_toc


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
    log(f"\nTable of Contents gerado com {len(toc['table_of_contents'])} capítulo(s).", modulo="pipeline_utils")
    log(f"Salvo em: {TOC_FILENAME_DEFAULT.resolve()}", modulo="pipeline_utils")

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
    log(f"Processing Plan gerado com {len(plano['table_of_contents'])} capítulo(s) no total.", modulo="pipeline_utils")
    log(f"Capítulos pendentes: {pending_count}", modulo="pipeline_utils")
    log(f"Salvo em: {PROCESSING_PLAN_FILENAME.resolve()}", modulo="pipeline_utils")


def _log(mensagem: str, verboso: bool = True) -> None:
    """Loga mensagem com timestamp se verbose estiver habilitado."""
    log(mensagem, modulo="pipeline_utils", verboso=verboso)


def _log_erro(mensagem: str) -> None:
    """Loga mensagem de erro com timestamp em stderr."""
    log_erro(mensagem, modulo="pipeline_utils")


def _agrupar_ultimo_capitulo(fragmentos: list[FragmentoInfo]) -> list[int]:
    """Retorna os índices do último capítulo (do último h1 até o fim)."""
    ultimo_h1: int | None = None
    for f in fragmentos:
        if f.tem_h1:
            ultimo_h1 = f.indice

    if ultimo_h1 is None:
        return []

    return [f.indice for f in fragmentos if f.indice >= ultimo_h1]


def _numero_capitulo(
    fragmentos: list[FragmentoInfo],
    indice_inicio: int,
) -> int:
    """
    Retorna o número sequencial do capítulo que começa em indice_inicio.
    Conta quantos h1 aparecem até esse índice (inclusive).
    """
    return sum(1 for f in fragmentos if f.tem_h1 and f.indice <= indice_inicio)


def _consolidar_capitulo(
    consolidador: Consolidator,
    num_cap: int,
    indices_cap: list[int],
    toc_info: dict,
) -> str | None:
    """
    Consolida um capítulo e retorna o JSON consolidado.
    Retorna None se falhar.
    """
    if len(indices_cap) == 1:
        # Capítulo de fragmento único
        from writer import salvar_analise
        path_analise = PASTA_SAIDA / f"analise-fragmento-{indices_cap[0]:03d}.md"
        path_cap = consolidador.path_capitulo(num_cap)
        path_cap.write_text(
            path_analise.read_text(encoding="utf-8"), encoding="utf-8"
        )
        _log(f"  → Capítulo {num_cap:03d} tem 1 fragmento — "
             f"copiado diretamente para {path_cap.name}")
        return path_cap.read_text(encoding="utf-8")

    # Múltiplos fragmentos
    _log(f"  → Consolidando capítulo {num_cap:03d} "
         f"({len(indices_cap)} fragmento(s))...")
    try:
        path_cap = consolidador.consolidar(
            numero_capitulo=num_cap,
            indices_fragmentos=indices_cap,
            toc_info=toc_info,
        )
        _log(f"  → Capítulo {num_cap:03d} salvo em {path_cap.name}")
        return path_cap.read_text(encoding="utf-8")
    except ErroConsolidacao as e:
        _log_erro(f"Consolidação do capítulo {num_cap:03d} falhou: {e}")
        _log_erro(
            "  → json_atual mantido do capítulo anterior — "
            "contexto dos próximos fragmentos pode estar defasado."
        )
        return None


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