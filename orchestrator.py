"""
orchestrator.py — Orquestra o pipeline de processamento de fragmentos.

Responsabilidades:
- Gerenciar o estado do pipeline (checkpoint)
- Coordenar a consolidação de capítulos
- Orquestrar o processamento de fragmentos individuais
- Tratar erros e retry de API
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from Consolidator import Consolidator, ErroConsolidacao
from Check_Point import Check_Point
from api_client import ErroAPI, ErroConexao, chamar_qwen
from config import (
    DELAY_API_CHAMADA,
    ESPERA_RETRY,
    MAX_TENTATIVAS_RETRY,
    PARAR_NO_ERRO,
    PASTA_SAIDA,
    PROCESSING_PLAN_FILENAME,
)
from loader import carregar_fragmento
from logger import log, log_erro
from prompt_builder import PromptBuilder
from scanner import FragmentoInfo
from writer import ErroJSON, salvar_analise


def _log(mensagem: str, modulo: str = "orchestrator", verboso: bool = True) -> None:
    """Loga mensagem com timestamp e módulo se verbose estiver habilitado."""
    log(mensagem, modulo=modulo, verboso=verboso)


def _log_erro(mensagem: str, modulo: str = "orchestrator") -> None:
    """Loga mensagem de erro com timestamp e módulo em stderr."""
    log_erro(mensagem, modulo=modulo)


class PipelineOrchestrator:
    """
    Orquestra o pipeline completo de processamento de fragmentos.
    
    Responsável por:
    - Gerenciar estado e checkpoint
    - Coordenar consolidação de capítulos
    - Processar fragmentos individuais
    - Tratar erros e retry
    """

    def __init__(self, pasta_saida: Path = PASTA_SAIDA) -> None:
        self.pasta_saida = pasta_saida
        self.checkpoint = Check_Point(pasta_saida)
        self.consolidador = Consolidator(pasta_saida)
        self.erros: list[tuple[int, str]] = []

    def carregar_estado(self) -> Any:
        """Carrega o estado atual do checkpoint."""
        return self.checkpoint.carregar()

    def obter_json_base(self) -> str | None:
        """Retorna o JSON base do último capítulo consolidado."""
        return self.checkpoint.json_base()

    def carregar_contexto(self) -> dict[str, Any]:
        """
        Carrega ou gera o contexto de processamento (TOC e Plano).
        
        Retorna um dicionário com as informações do table_of_contents.
        """
        from pipeline_utils import gerar_e_salvar_plano
        from processing_plan import extrair_toc_completo

        if PROCESSING_PLAN_FILENAME.exists():
            with open(PROCESSING_PLAN_FILENAME, 'r', encoding='utf-8') as f:
                plano = json.load(f)
            toc_info = {"table_of_contents": plano.get('table_of_contents', [])}
            _log(f"Plano de processamento carregado: {len(toc_info['table_of_contents'])} capítulos.")
        else:
            # Nota: fragmentos precisam ser passados externamente
            # Esta lógica será tratada no main
            toc_info = {"table_of_contents": []}
            _log("Plano de processamento não encontrado. Será gerado on-the-fly.")
        
        return toc_info

    def _chamar_com_retry(self, mensagens: list[dict]) -> str:
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

    def processar_fragmento(
        self,
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
        titulo_extra = f" — {fragmento.titulo}" if fragmento.tem_h1 else ""
        _log(f"[{posicao}/{total}] Processando {fragmento.nome}{titulo_extra}")

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
            resposta = self._chamar_com_retry(mensagens)
        except ErroAPI as e:
            _log_erro(f"API falhou para {fragmento.nome}: {e}")
            return json_atual, False

        duracao = time.monotonic() - inicio
        _log(f"  → Resposta recebida em {duracao:.1f}s")

        # Salvamento
        try:
            path_salvo = salvar_analise(fragmento.indice, resposta, self.pasta_saida)
            _log(f"  → Salvo em {path_salvo.name}")
        except ErroJSON as e:
            _log_erro(f"JSON inválido para {fragmento.nome}: {e}")
            return json_atual, False

        return path_salvo.read_text(encoding="utf-8"), True

    def consolidar_capitulo(
        self,
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
            path_analise = self.pasta_saida / f"analise-fragmento-{indices_cap[0]:03d}.md"
            path_cap = self.consolidador.path_capitulo(num_cap)
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
            path_cap = self.consolidador.consolidar(
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

    def adicionar_erro(self, indice: int, mensagem: str) -> None:
        """Registra um erro no processamento."""
        self.erros.append((indice, mensagem))

    def get_erros(self) -> list[tuple[int, str]]:
        """Retorna a lista de erros registrados."""
        return self.erros

    def tem_erros(self) -> bool:
        """Verifica se houve erros no processamento."""
        return len(self.erros) > 0
