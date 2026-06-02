"""
main.py — Orquestração do pipeline de análise de light novel.

Uso
---
    # Processa fragmentos da pasta padrão "raw/"
    python main.py

    # Especifica pasta de entrada
    python main.py --pasta /caminho/para/xhtml

    # Lista fragmentos pendentes sem chamar a API
    python main.py --dry-run

    # Lista fragmentos pendentes de uma pasta específica
    python main.py --pasta /caminho/para/xhtml --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from api_client import ErroAPI, ErroConexao, chamar_qwen
from config import (
    PASTA_ENTRADA_PADRAO,
    PASTA_SAIDA,
    LOG_VERBOSO,
    PARAR_NO_ERRO,
    DELAY_API_CHAMADA,
    MAX_TENTATIVAS_RETRY,
    ESPERA_RETRY,
    TOC_FILENAME_DEFAULT,
    PROCESSING_PLAN_FILENAME,
)
from Consolidator import Consolidator, ErroConsolidacao
from loader import carregar_fragmento
from prompt_builder import PromptBuilder
from Check_Point import Check_Point
from scanner import FragmentoInfo, descobrir_fragmentos
from writer import ErroJSON, salvar_analise
from toc_generator import gerar_e_salvar_toc
from processing_plan import gerar_e_salvar_plano, extrair_toc_completo


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(mensagem: str, verboso: bool = True) -> None:
    """Loga mensagem com timestamp se verbose estiver habilitado."""
    if verboso or LOG_VERBOSO:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {mensagem}", flush=True)


def _log_erro(mensagem: str) -> None:
    """Loga mensagem de erro com timestamp em stderr."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] ❌ {mensagem}", file=sys.stderr, flush=True)


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


def _carregar_json_capitulo(consolidador: Consolidator, num_cap: int) -> str:
    """Carrega o JSON de um capítulo já consolidado."""
    return consolidador.path_capitulo(num_cap).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def _dry_run(fragmentos: list[FragmentoInfo], proximo_indice: int) -> None:
    """Exibe os fragmentos pendentes sem chamar a API."""
    pendentes = [f for f in fragmentos if f.indice >= proximo_indice]

    print(f"\nDry-run — {len(pendentes)} fragmento(s) pendente(s):\n")
    capitulo_atual = 0
    for f in pendentes:
        if f.tem_h1:
            capitulo_atual += 1
            marcador = f"[CAP {capitulo_atual:02d}] {f.titulo or '(sem título)'}"
        else:
            marcador = "        (continuação)"
        print(f"  {f.indice:03d}  {f.nome}  {marcador}")

    if not pendentes:
        print("  Nenhum fragmento pendente — pipeline completo.")


# ---------------------------------------------------------------------------
# Retry simples para chamadas de API
# ---------------------------------------------------------------------------

def _chamar_com_retry(mensagens: list[dict]) -> str:
    """
    Tenta chamar o Qwen até MAX_TENTATIVAS_RETRY vezes em caso de ErroConexao.
    Levanta ErroAPI se todas as tentativas falharem.
    """
    ultima_excecao: Exception | None = None

    for tentativa in range(1, MAX_TENTATIVAS_RETRY + 1):
        try:
            return chamar_qwen(mensagens)
        except ErroConexao as e:
            ultima_excecao = e
            if tentativa < MAX_TENTATIVAS_RETRY:
                _log(f"  → Tentativa {tentativa}/{MAX_TENTATIVAS_RETRY} falhou. "
                     f"Aguardando {ESPERA_RETRY}s...")
                time.sleep(ESPERA_RETRY)
        except ErroAPI:
            raise  # Erros não relacionados a conexão não fazem retry

    raise ultima_excecao  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def _processar_fragmento(
    fragmento: FragmentoInfo,
    builder: PromptBuilder,
    json_atual: str,
    posicao: int,
    total: int,
) -> tuple[str, bool]:
    """
    Processa um único fragmento: carrega, monta prompt, chama API e salva.
    Retorna (json_atualizado, sucesso).
    """
    _log(f"[{posicao}/{total}] Processando {fragmento.nome}"
         + (f" — {fragmento.titulo}" if fragmento.tem_h1 else ""))

    # Extração do texto
    try:
        texto = carregar_fragmento(fragmento.path)
    except (FileNotFoundError, ValueError) as e:
        _log_erro(f"Falha ao carregar {fragmento.nome}: {e}")
        return json_atual, False

    # Montagem do prompt
    _log('--- Montagem do prompt ---')
    mensagens = builder.montar(texto, json_atual)

    # Chamada à API
    _log('--- Chamada à API: Em 10 segundos ---')
    time.sleep(DELAY_API_CHAMADA)
    _log('Vai demorar MUITOS minutos!!! Aguarde...')

    inicio = time.monotonic()
    try:
        resposta = _chamar_com_retry(mensagens)
    except ErroAPI as e:
        _log_erro(f"API falhou para {fragmento.nome}: {e}")
        return json_atual, False

    duracao = time.monotonic() - inicio
    _log(f"  → Resposta recebida em {duracao:.1f}s")

    # Salvamento
    try:
        path_salvo = salvar_analise(fragmento.indice, resposta, PASTA_SAIDA)
        _log(f"  → Salvo em {path_salvo.name}")
    except ErroJSON as e:
        _log_erro(f"JSON inválido para {fragmento.nome}: {e}")
        return json_atual, False

    return path_salvo.read_text(encoding="utf-8"), True


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
    resumo = Check_Point(PASTA_SAIDA)
    estado = resumo.carregar()
    resumo.reportar()
    print()

    if estado.proximo_indice >= len(fragmentos):
        _log("Todos os fragmentos já foram processados.")
        return

    # --- Inicialização dos módulos ---
    try:
        builder = PromptBuilder()
    except FileNotFoundError as e:
        _log_erro(str(e))
        sys.exit(1)

    consolidador = Consolidator(PASTA_SAIDA)

    # Gerar plano de processamento com TOC
    _log("Gerando plano de processamento...")
    plano = gerar_e_salvar_plano(
        fragmentos,
        PASTA_SAIDA,
        estado.proximo_indice,
        caminho_saida=PROCESSING_PLAN_FILENAME,
    )
    toc_info = {"table_of_contents": extrair_toc_completo(plano)}
    _log(f"Plano gerado: {plano['pending_chapters']} capítulos pendentes.")

    # JSON base: último capítulo consolidado ou None (template vazio)
    json_atual = resumo.json_base()

    # Fragmentos pendentes
    pendentes = [f for f in fragmentos if f.indice >= estado.proximo_indice]
    total = len(pendentes)

    erros: list[tuple[int, str]] = []

    # --- Loop principal ---
    for posicao, fragmento in enumerate(pendentes, start=1):
        # --- Consolidação do capítulo anterior ---
        # Dispara quando encontra um h1 que não seja o primeiro fragmento
        if fragmento.tem_h1 and fragmento.indice > 0:
            indices_cap = _agrupar_capitulo_anterior(fragmentos, fragmento.indice)
            num_cap = _numero_capitulo(fragmentos, indices_cap[0]) if indices_cap else None

            if indices_cap and num_cap is not None:
                # Só consolida se ainda não foi consolidado
                if not consolidador.capitulo_existe(num_cap):
                    json_consolidado = _consolidar_capitulo(
                        consolidador, num_cap, indices_cap, toc_info
                    )
                    if json_consolidado is not None:
                        json_atual = json_consolidado
                    elif PARAR_NO_ERRO:
                        sys.exit(1)
                else:
                    _log(f"  → Capítulo {num_cap:03d} já consolidado — pulando.")
                    json_atual = _carregar_json_capitulo(consolidador, num_cap)

        # --- Processamento do fragmento ---
        json_atual, sucesso = _processar_fragmento(
            fragmento, builder, json_atual, posicao, total
        )

        if not sucesso:
            erros.append((fragmento.indice, "Erro no processamento"))
            if PARAR_NO_ERRO:
                sys.exit(1)

    # --- Consolidação do último capítulo ---
    if pendentes:
        indices_ultimo_cap = _agrupar_ultimo_capitulo(fragmentos)
        num_ultimo = (
            _numero_capitulo(fragmentos, indices_ultimo_cap[0])
            if indices_ultimo_cap else None
        )

        if indices_ultimo_cap and num_ultimo and not consolidador.capitulo_existe(num_ultimo):
            json_final = _consolidar_capitulo(
                consolidador, num_ultimo, indices_ultimo_cap, toc_info
            )
            if json_final is None:
                _log_erro("Consolidação do último capítulo falhou.")

    # --- Relatório final ---
    print()
    sucessos = sum(1 for f in pendentes if f.indice not in [e[0] for e in erros])
    _log(f"Pipeline concluído. Processados: {sucessos}/{total}")

    if erros:
        _log_erro(f"{len(erros)} fragmento(s) com erro:")
        for indice, msg in erros:
            _log_erro(f"  fragmento {indice:03d}: {msg}")
        print("\nExecute novamente para reprocessar os fragmentos com erro.", file=sys.stderr)


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
            "  python main.py --pasta /caminho/para/xhtml --dry-run\n"
            "  python main.py --gerar-toc\n"
            "  python main.py --pasta /caminho/para/xhtml --gerar-toc --toc-saida {TOC_FILENAME_DEFAULT}"
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
        help="Gera o table_of_contents em JSON a partir dos fragmentos",
    )
    parser.add_argument(
        "--toc-saida",
        type=Path,
        default=None,
        help=f"Caminho do arquivo JSON de saída para o table_of_contents (padrão: {TOC_FILENAME_DEFAULT})",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = _parse_args()

    if args.gerar_toc:
        try:
            fragmentos = descobrir_fragmentos(args.pasta)
        except (FileNotFoundError, ValueError) as e:
            _log_erro(str(e))
            sys.exit(1)

        caminho_saida = args.toc_saida or TOC_FILENAME_DEFAULT
        toc = gerar_e_salvar_toc(fragmentos, caminho_saida)
        print(f"\nTable of Contents gerado com {len(toc['table_of_contents'])} capítulo(s).")
        print(f"Salvo em: {caminho_saida.resolve()}")
        
        # Gerar também o processing_plan.json
        checkpoint = Check_Point(args.pasta_saida or PASTA_SAIDA)
        proximo_indice = checkpoint.carregar_proximo_indice()
        plano = gerar_e_salvar_plano(
            fragmentos,
            args.pasta_saida or PASTA_SAIDA,
            proximo_indice,
            caminho_saida=PROCESSING_PLAN_FILENAME,
        )
        print(f"Processing Plan gerado com {len(plano['table_of_contents'])} capítulo(s).")
        print(f"Salvo em: {PROCESSING_PLAN_FILENAME.resolve()}")
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
