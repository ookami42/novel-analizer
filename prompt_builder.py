"""
prompt_builder.py — Monta o payload de mensagens para cada chamada ao Qwen.

Responsabilidades:
- Carregar o knowledge-template.json uma única vez
- Separar campos de referência fixos do template
- Combinar referências com o TOC gerado dinamicamente
- Montar a lista de mensagens [system, user] para cada fragmento
- Injetar:
  1. Campos de referência + TOC (apenas consulta, não editar)
  2. JSON base (estado atual, único que deve ser modificado)
  3. Fragmento de história

Estrutura esperada do fragment-analizer.md:
    <instruções do sistema>
    ---
    === 1. JSON base ===
    ```json
    { ... }
    ```
    === 1.1. Campos de referência e TOC ===
    ```json
    { ... }
    ```
    === 2. Fragmento de historia ===
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import (
    PROMPT_ANALISE_PATH,
    KNOWLEDGE_TEMPLATE_PATH,
    MARCADOR_JSON_BASE,
    MARCADOR_REFERENCIAS,
    MARCADOR_FRAGMENTO,
    PASTA_SAIDA,
)
from knowledge_manager import KnowledgeManager


# ---------------------------------------------------------------------------
# Marcadores do fragment-analizer.md
# ---------------------------------------------------------------------------

# Os marcadores agora são importados do config.py para centralizar configurações
# _MARCADOR_JSON_BASE = "=== 1. JSON base ==="
# _MARCADOR_REFERENCIAS = "=== 1.1. Campos de referência e TOC ==="
# _MARCADOR_FRAGMENTO = "=== 2. Fragmento de historia ==="


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class PromptBuilder:
    """
    Gerencia o knowledge-manager e monta payloads para o Qwen.

    Os arquivos são lidos uma única vez no construtor.
    Instanciar uma vez e reutilizar para todos os fragmentos.

    Uso
    ---
        builder = PromptBuilder()
        mensagens = builder.montar(texto_fragmento, json_atual)
        # mensagens → [{"role": "system", ...}, {"role": "user", ...}]
    """

    def __init__(
        self,
        prompt_path: str | Path = PROMPT_ANALISE_PATH,
        template_path: str | Path = KNOWLEDGE_TEMPLATE_PATH,
        pasta_saida: str | Path | None = None,
    ) -> None:
        prompt_path = Path(prompt_path)
        template_path = Path(template_path)

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Arquivo de prompt não encontrado: {prompt_path.resolve()}"
            )

        if not template_path.exists():
            raise FileNotFoundError(
                f"Arquivo de template JSON não encontrado: {template_path.resolve()}"
            )

        # Inicializa o KnowledgeManager para gerenciar JSONs
        self._knowledge_manager = KnowledgeManager(
            template_path=template_path,
            pasta_saida=pasta_saida if pasta_saida else PASTA_SAIDA,
        )

        # Carrega e parseia o prompt para obter o system prompt
        conteudo = prompt_path.read_text(encoding="utf-8")
        self._system = self._parsear_system(conteudo)

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def montar(
        self,
        texto_fragmento: str,
        json_atual: dict | str | None = None,
        toc_data: dict[str, Any] | None = None,
    ) -> list[dict]:
        """
        Monta a lista de mensagens para uma chamada ao Qwen.

        Parâmetros
        ----------
        texto_fragmento : str
            Texto extraído do .xhtml pelo loader.py.
        json_atual : dict | str | None
            JSON do último capítulo consolidado (como dict ou string JSON).
            Se None, usa o template vazio combinado com referências e TOC.
        toc_data : dict[str, Any] | None
            Dados do table_of_contents gerado. Se None, usa o TOC padrão.

        Retorna
        -------
        list[dict]
            Lista no formato esperado pela API OpenAI:
            [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        # Obter JSON base com referências fixas e TOC
        json_base_completo = self._knowledge_manager.obter_json_base(toc_data)

        # Mesclar json_atual se fornecido (sobrescreve campos do base)
        if json_atual is not None:
            if isinstance(json_atual, str):
                json_atual_dict = json.loads(json_atual)
            else:
                json_atual_dict = json_atual
            
            # Merge profundo: json_atual sobrescreve json_base
            json_injetado = self._merge_json(json_base_completo, json_atual_dict)
        else:
            json_injetado = json_base_completo

        # Extrair apenas os campos de referência para exibição separada
        referencias_fixas = self._knowledge_manager.referencias_fixas
        
        # Construir JSON de referências + TOC (apenas para consulta)
        json_referencias_toc = {
            "_stage_reference": referencias_fixas.get("_stage_reference", []),
            "_scale_reference": referencias_fixas.get("_scale_reference", {}),
            "table_of_contents": json_base_completo["volume_metadata"]["table_of_contents"],
            "title": json_base_completo["volume_metadata"].get("title", "")
        }

        # Converte os JSONs para string formatada
        json_base_str = json.dumps(json_injetado, ensure_ascii=False, indent=2)
        json_referencias_str = json.dumps(json_referencias_toc, ensure_ascii=False, indent=2)

        # Monta o conteúdo do usuário com DOIS separadores JSON
        user = (
            f"{MARCADOR_REFERENCIAS}\n\n"
            f"```json\n{json_referencias_str}\n```\n\n"
            f"{MARCADOR_JSON_BASE}\n\n"
            f"```json\n{json_base_str}\n```\n\n"
            f"ATENCIÓN: Los campos en '{MARCADOR_REFERENCIAS}' son sólo para consulta. NO los modifique en la salida.\n\n"
            f"{MARCADOR_FRAGMENTO}\n\n"
            f"{texto_fragmento}"
        )

        return [
            {"role": "system", "content": self._system},
            {"role": "user",   "content": user},
        ]

    @property
    def knowledge_manager(self) -> KnowledgeManager:
        """Retorna o gerenciador de conhecimento."""
        return self._knowledge_manager

    @property
    def system_prompt(self) -> str:
        """Bloco de instruções do sistema extraído do fragment-analizer.md."""
        return self._system

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_json(base: dict, atual: dict) -> dict:
        """
        Faz merge profundo de dois dicionários.
        Campos de 'atual' sobrescrevem 'base'.
        """
        resultado = base.copy()
        
        for chave, valor in atual.items():
            if chave in resultado and isinstance(resultado[chave], dict) and isinstance(valor, dict):
                resultado[chave] = PromptBuilder._merge_json(resultado[chave], valor)
            else:
                resultado[chave] = valor
        
        return resultado

    @staticmethod
    def _parsear_system(conteudo: str) -> str:
        """
        Extrai o system prompt do conteúdo do fragment-analizer.md.
        O system prompt é tudo antes do marcador === 1. JSON base ===

        Levanta
        -------
        ValueError
            Se o marcador não for encontrado.
        """
        idx_json = conteudo.find(MARCADOR_JSON_BASE)
        if idx_json == -1:
            raise ValueError(
                f"Marcador '{MARCADOR_JSON_BASE}' não encontrado no fragment-analizer.md"
            )

        return conteudo[:idx_json].rstrip()
