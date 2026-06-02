"""
main.py — Orquestração do pipeline de análise de light novel.
Versão refatorada com maior modularidade e legibilidade.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from Check_Point import Check_Point
from config import (
    LOG_VERBOSO,
    PASTA_ENTRADA_PADRAO,
    PASTA_SAIDA,
    PARAR_NO_ERRO,
)
from logger import log, log_erro
from orchestrator import PipelineOrchestrator
from pipeline_utils import finalizar_capitulos_pendentes, gerar_toc_e_plano
from processing_plan import extrair_toc_completo, gerar_e_salvar_plano
from prompt_builder import PromptBuilder
from scanner import FragmentoInfo, descobrir_fragmentos


def _log(mensagem: str, modulo: str = "main", verboso: bool = True) -> None:
    """Loga mensagem com timestamp e módulo se verbose estiver habilitado."""
    log(mensagem, modulo=modulo, verboso=verboso)


def _log_erro(mensagem: str, modulo: str = "main") -> None:
    """Loga mensagem de erro com timestamp e módulo em stderr."""
    log_erro(mensagem, modulo=modulo)


# ---------------------------------------------------------------------------
# Lógica de capítulos
# ---------------------------------------------------------------------------

def _encontrar_inicio_capitulo_anterior(
    fragmentos: list[FragmentoInfo],
    indice_atual: int,
) -> int | None:
    """Encontra o índice do fragmento com h1 imediatamente anterior ao atual."""
    for f in fragmentos[:indice_atual]:
        if f.tem_h1:
            return f.indice
    return None


def _agrupar_capitulo_anterior(
    fragmentos: list[FragmentoInfo],
    indice_atual: int,
) -> list[int]:
    """
    Retorna os índices dos fragmentos que pertencem ao capítulo
    imediatamente anterior ao fragmento com h1 em indice_atual.

    Um capítulo começa no fragmento com h1 e termina no fragmento
    imediatamente antes do próximo h1.
    """
    inicio_cap = _encontrar_inicio_capitulo_anterior(fragmentos, indice_atual)
    if inicio_cap is None:
        return []

    return [f.indice for f in fragmentos if inicio_cap <= f.indice < indice_atual]


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


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def _dry_run(fragmentos: list[FragmentoInfo], proximo_indice: int) -> None:
    """Exibe os fragmentos pendentes sem chamar a API."""
    pendentes = [f for f in fragmentos if f.indice >= proximo_indice]

    log(f"\nDry-run — {len(pendentes)} fragmento(s) pendente(s):\n", modulo="main")
    capitulo_atual = 0
    for f in pendentes:
        if f.tem_h1:
            capitulo_atual += 1
            marcador = f"[CAP {capitulo_atual:02d}] {f.titulo or '(sem título)'}"
        else:
            marcador = "        (continuação)"
        log(f"  {f.indice:03d}  {f.nome}  {marcador}", modulo="main")

    if not pendentes:
        log("  Nenhum fragmento pendente — pipeline completo.", modulo="main")


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def executar(pasta_entrada: Path) -> None:
    """Executa o pipeline completo de análise."""

    # --- Descoberta ---
    _log("Varrendo fragmentos...")
    try:
        fragmentos = descobrir_fragmentos(pasta_entrada)
    except (FileNotFoundError, ValueError) as e:
        _log_erro(str(e))
        sys.exit(1)

    _log(f"Encontrados {len(fragmentos)} fragmento(s).")

    # --- Estado atual ---
    checkpoint = Check_Point(PASTA_SAIDA)
    estado = checkpoint.carregar()
    checkpoint.reportar()
    log("", modulo="main")  # Linha em branco

    if estado.proximo_indice >= len(fragmentos):
        _log("Todos os fragmentos já foram processados.")
        return

    # --- Inicialização dos módulos ---
    try:
        builder = PromptBuilder()
    except FileNotFoundError as e:
        _log_erro(str(e))
        sys.exit(1)

    # Inicializa o orquestrador do pipeline
    orchestrator = PipelineOrchestrator(PASTA_SAIDA)

    # Carrega contexto (TOC e Plano)
    _log("Preparando contexto de processamento...", modulo="main")
    
    if PROCESSING_PLAN_FILENAME.exists():
        import json
        with open(PROCESSING_PLAN_FILENAME, 'r', encoding='utf-8') as f:
            plano = json.load(f)
        toc_info = {"table_of_contents": plano.get('table_of_contents', [])}
        _log(f"Plano de processamento carregado: {len(toc_info['table_of_contents'])} capítulos.", modulo="main")
    else:
        # Gera o plano on-the-fly se não existir
        plano = gerar_e_salvar_plano(
            fragmentos,
            PASTA_SAIDA,
            estado.proximo_indice,
            caminho_saida=PROCESSING_PLAN_FILENAME,
        )
        toc_info = {"table_of_contents": extrair_toc_completo(plano)}
        _log(f"Plano gerado on-the-fly: {plano['pending_chapters']} capítulos pendentes.", modulo="main")

    # JSON base: último capítulo consolidado ou None (template vazio)
    json_atual = estado.json_base()

    # Fragmentos pendentes
    pendentes = [f for f in fragmentos if f.indice >= estado.proximo_indice]
    total = len(pendentes)

    # --- Loop principal ---
    for posicao, fragmento in enumerate(pendentes, start=1):
        # --- Consolidação do capítulo anterior ---
        # Dispara quando encontra um h1 que não seja o primeiro fragmento
        if fragmento.tem_h1 and fragmento.indice > 0:
            indices_cap = _agrupar_capitulo_anterior(fragmentos, fragmento.indice)
            num_cap = _numero_capitulo(fragmentos, indices_cap[0]) if indices_cap else None

            if indices_cap and num_cap is not None:
                # Só consolida se ainda não foi consolidado
                if not orchestrator.consolidador.capitulo_existe(num_cap):
                    json_consolidado = orchestrator.consolidar_capitulo(
                        num_cap, indices_cap, toc_info
                    )
                    if json_consolidado is not None:
                        json_atual = json_consolidado
                    elif PARAR_NO_ERRO:
                        sys.exit(1)
                else:
                    _log(f"  → Capítulo {num_cap:03d} já consolidado — pulando.")
                    # Carrega JSON do capítulo consolidado
                    path_cap = orchestrator.consolidador.path_capitulo(num_cap)
                    json_atual = path_cap.read_text(encoding="utf-8")

        # --- Processamento do fragmento ---
        json_atual, sucesso = orchestrator.processar_fragmento(
            fragmento, builder, json_atual, posicao, total
        )

        if not sucesso:
            orchestrator.adicionar_erro(fragmento.indice, "Erro no processamento")
            if PARAR_NO_ERRO:
                sys.exit(1)

    # --- Consolidação do último capítulo ---
    if pendentes:
        finalizar_capitulos_pendentes(fragmentos, orchestrator.consolidador, toc_info)

    # --- Relatório final ---
    log("", modulo="main")  # Linha em branco
    erros = orchestrator.get_erros()
    sucessos = sum(1 for f in pendentes if f.indice not in [e[0] for e in erros])
    _log(f"Pipeline concluído. Processados: {sucessos}/{total}")

    if erros:
        _log_erro(f"{len(erros)} fragmento(s) com erro:")
        for indice, msg in erros:
            _log_erro(f"  fragmento {indice:03d}: {msg}")
        log_erro("\nExecute novamente para reprocessar os fragmentos com erro.", modulo="main")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline de análise de light novel japonesa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python main.py\n"
            "  python main.py --pasta /caminho/para/xhtml\n"
            "  python main.py --dry-run\n"
            "  python main.py --gerar-toc\n"
        ),
    )
    parser.add_argument(
        "--pasta",
        type=Path,
        default=PASTA_ENTRADA_PADRAO,
        help=f"Pasta com os arquivos .xhtml (padrão: {PASTA_ENTRADA_PADRAO})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista fragmentos pendentes sem chamar a API",
    )
    parser.add_argument(
        "--gerar-toc",
        action="store_true",
        help="Gera o table_of_contents e o processing_plan.json",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _parse_args()

    if args.gerar_toc:
        _log("Gerando TOC e Plano de Processamento...")
        try:
            gerar_toc_e_plano(args.pasta)
            _log("Arquivos gerados com sucesso.")
        except Exception as e:
            _log_erro(f"Falha ao gerar arquivos: {e}")
            sys.exit(1)
        
    elif args.dry_run:
        try:
            fragmentos = descobrir_fragmentos(args.pasta)
        except (FileNotFoundError, ValueError) as e:
            _log_erro(str(e))
            sys.exit(1)

        resumo = Check_Point(PASTA_SAIDA)
        estado = resumo.carregar()
        resumo.reportar()

        _dry_run(fragmentos, estado.proximo_indice)
    else:
        executar(args.pasta)