"""
knowledge_manager.py — Gerencia o JSON base combinando campos de referência fixos com o TOC dinâmico.

Responsabilidades:
- Separar campos de referência (não editáveis) do knowledge-template.json
- Combinar referências com o table_of_contents gerado
- Fornecer o JSON base atualizado para o PromptBuilder
- Carregar/salvar JSONs na pasta knowledge/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import (
    PASTA_SAIDA,
    KNOWLEDGE_TEMPLATE_PATH,
    TOC_FILENAME_DEFAULT,
    PROCESSING_PLAN_FILENAME,
)


# ---------------------------------------------------------------------------
# Campos de referência (não editáveis pela IA)
# ---------------------------------------------------------------------------

CAMPOS_REFERENCIA = [
    "_stage_reference",      # Em relationships
    "_scale_reference",      # Em romantic_subtext
]


class KnowledgeManager:
    """
    Gerencia o JSON base da obra, separando campos de referência fixos
    e combinando com o TOC dinâmico gerado.

    Uso
    ---
        manager = KnowledgeManager()
        json_base = manager.obter_json_base(toc_gerado)
    """

    def __init__(self, template_path: str | Path = KNOWLEDGE_TEMPLATE_PATH, pasta_saida: str | Path = PASTA_SAIDA) -> None:
        self._template_path = template_path
        self._pasta_saida = pasta_saida
        self._template_original = self._carregar_template()
        self._referencias_fixas = self._extrair_referencias()

    def _carregar_template(self) -> dict[str, Any]:
        """Carrega o knowledge-template.json."""
        if not self._template_path.exists():
            raise FileNotFoundError(
                f"Template JSON não encontrado: {self._template_path.resolve()}"
            )
        
        with open(self._template_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _extrair_referencias(self) -> dict[str, Any]:
        """
        Extrai apenas os campos de referência fixos do template.
        Estes campos servem como guia para a IA e não devem ser modificados.
        """
        referencias = {}

        # Extrair _stage_reference de relationships
        if "relationships" in self._template_original:
            stage_ref = self._template_original["relationships"].get("_stage_reference")
            if stage_ref:
                referencias["_stage_reference"] = stage_ref

        # Extrair _scale_reference de romantic_subtext
        if "romantic_subtext" in self._template_original:
            scale_ref = self._template_original["romantic_subtext"].get("_scale_reference")
            if scale_ref:
                referencias["_scale_reference"] = scale_ref

        return referencias

    def obter_json_base(self, toc_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Monta o JSON base combinando:
        1. Estrutura vazia do template (sem dados de história)
        2. Campos de referência fixos
        3. TOC gerado dinamicamente (se fornecido)

        Parâmetros
        ----------
        toc_data : dict[str, Any] | None
            Dados do table_of_contents gerado pelo toc_generator.py.
            Se None, usa o TOC padrão do template.

        Retorna
        -------
        dict[str, Any]
            JSON base pronto para ser injetado no prompt.
        """
        # Criar uma cópia profunda da estrutura base
        json_base = self._criar_estrutura_vazia()

        # Inserir campos de referência
        if "_stage_reference" in self._referencias_fixas:
            json_base["relationships"]["_stage_reference"] = self._referencias_fixas["_stage_reference"]

        if "_scale_reference" in self._referencias_fixas:
            json_base["romantic_subtext"]["_scale_reference"] = self._referencias_fixas["_scale_reference"]

        # Inserir TOC (prioriza o toc_data fornecido)
        if toc_data is not None:
            json_base["volume_metadata"]["table_of_contents"] = toc_data.get("table_of_contents", [])
            if "title" in toc_data:
                json_base["volume_metadata"]["title"] = toc_data["title"]
        else:
            # Usa o TOC padrão do template
            json_base["volume_metadata"]["table_of_contents"] = self._template_original.get("volume_metadata", {}).get("table_of_contents", [])

        return json_base

    def _criar_estrutura_vazia(self) -> dict[str, Any]:
        """
        Cria uma estrutura JSON base com campos vazios, pronta para receber dados.
        Remove dados específicos de história mantendo apenas a estrutura.
        """
        estrutura = {
            "volume_metadata": {
                "table_of_contents": [],
                "title": "",
                "current_fragment": "fragment_00",
                "current_chapter": 0,
                "current_arc": "",
                "translation_notes": []
            },
            "story_state": {
                "current_arc": "",
                "arc_summary": "",
                "unresolved_tensions": [],
                "pending_relationship_developments": [],
                "recent_turning_points": []
            },
            "characters": {},
            "relationships": {},
            "romantic_subtext": {},
            "emotional_progress": {},
            "speech_dynamics": {},
            "important_moments": [],
            "chapter_history": [],
            "glossary": {},
            "locations": {},
            "organizations": {},
            "magic_terms": {}
        }

        # Copiar tipos de personagens do template se existirem
        if "characters" in self._template_original:
            # Manter apenas a estrutura de exemplo se necessário
            pass

        return estrutura

    def carregar_json_capitulo(self, numero_capitulo: int) -> dict[str, Any] | None:
        """
        Carrega um JSON de capítulo consolidado da pasta knowledge/.

        Parâmetros
        ----------
        numero_capitulo : int
            Número do capítulo.

        Retorna
        -------
        dict[str, Any] | None
            Conteúdo do JSON ou None se não existir.
        """
        path = self._pasta_saida / f"capitulo-{numero_capitulo:03d}.json"
        
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def salvar_json_capitulo(self, numero_capitulo: int, dados: dict[str, Any]) -> Path:
        """
        Salva um JSON de capítulo consolidado na pasta knowledge/.

        Parâmetros
        ----------
        numero_capitulo : int
            Número do capítulo.
        dados : dict[str, Any]
            Dados do JSON consolidado.

        Retorna
        -------
        Path
            Caminho do arquivo salvo.
        """
        self._pasta_saida.mkdir(parents=True, exist_ok=True)
        path = self._pasta_saida / f"capitulo-{numero_capitulo:03d}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        return path

    def carregar_json_parcial(self, indice_fragmento: int) -> dict[str, Any] | None:
        """
        Carrega um JSON parcial de fragmento da pasta knowledge/.

        Parâmetros
        ----------
        indice_fragmento : int
            Índice do fragmento.

        Retorna
        -------
        dict[str, Any] | None
            Conteúdo do JSON ou None se não existir.
        """
        path = self._pasta_saida / f"analise-fragmento-{indice_fragmento:03d}.json"
        
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def salvar_json_parcial(self, indice_fragmento: int, dados: dict[str, Any]) -> Path:
        """
        Salva um JSON parcial de fragmento na pasta knowledge/.

        Parâmetros
        ----------
        indice_fragmento : int
            Índice do fragmento.
        dados : dict[str, Any]
            Dados do JSON parcial.

        Retorna
        -------
        Path
            Caminho do arquivo salvo.
        """
        self._pasta_saida.mkdir(parents=True, exist_ok=True)
        path = self._pasta_saida / f"analise-fragmento-{indice_fragmento:03d}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        return path

    @property
    def referencias_fixas(self) -> dict[str, Any]:
        """Retorna os campos de referência extraídos do template."""
        return self._referencias_fixas
