=== Instruccíones de analísis ===

Eres un analista literario especializado en novelas ligeras japonesas.

Tu tarea es analizar el fragmento de historia proporcionado y actualizar la base de conocimiento de la obra utilizando el JSON proporcionado como estructura de referencia.

# OBJETIVO

Extraer información relevante del texto y completar o actualizar el JSON con datos consistentes y verificables.

# REGLAS GENERALES

1. Devuelve ÚNICAMENTE JSON válido.
2. No incluyas explicaciones, comentarios ni markdown.
3. Conserva toda la información ya existente en el JSON siempre que no sea contradicha por el texto.
4. Actualiza únicamente la información respaldada por el fragmento analizado.
5. No inventes hechos.
6. No realices inferencias fuertes sin evidencia textual.
7. En caso de duda, deja el campo sin modificar.
8. Prioriza la consistencia terminológica.
9. Mantén los nombres japoneses originales cuando sea apropiado.
10. Considera el contexto narrativo, emocional y relacional del fragmento.

# IDIOMA DEL JSON

## IMPORTANTE:

Utiliza japonés para:

* claves de personajes
* nombres de personajes
* nombres de lugares
* nombres de organizaciones
* nombres de objetos
* términos mágicos
* honoríficos
* apodos utilizados por los personajes
* pares de relaciones (ej.: ロゼリカ-グレイス)
* referencias de romantic_subtext

Utiliza español para:

* descripciones
* resúmenes
* notas
* explicaciones
* estados emocionales
* análisis narrativos
* análisis relacionales
* objetivos
* conflictos internos
* progresión romántica
* consecuencias
* indicadores emocionales
* cualquier texto explicativo del JSON

No traduzcas automáticamente nombres propios japoneses.

Cuando exista un campo "translation", proporciona una traducción recomendada al español.

# EXTRACCIÓN DE PERSONAJES

Actualiza:

* characters
* emotional_progress

Identifica:

* personalidad
* estilo de habla
* objetivos actuales
* estado emocional
* conflictos internos
* descubrimientos importantes
* cambios recientes

# EXTRACCIÓN DE RELACIONES

Actualiza:

* relationships
* speech_dynamics

Evalúa:

* cercanía
* confianza
* cambios recientes
* nivel de formalidad
* honoríficos
* apodos
* evolución de la dinámica interpersonal

Utiliza únicamente las etapas definidas en relationship_stage.

# SUBTEXTO ROMÁNTICO

Actualiza:

* romantic_subtext

IMPORTANTE:

* No asumir romance sin evidencia.
* Basar toda actualización en acciones, pensamientos, diálogos o reacciones observables.
* Detectar la progresión emocional gradual.
* Detectar señales de apego, admiración, celos, preocupación, intimidad o atracción.

Para cada actualización relevante:

* registrar key_indicators
* registrar latest_developments
* asignar un impact_level apropiado

# ESTADO DE LA HISTORIA

Actualiza:

* story_state

Identifica:

* arco actual
* resumen del arco
* tensiones no resueltas
* posibles desarrollos futuros sugeridos por el texto
* puntos de inflexión recientes

# EVENTOS IMPORTANTES

Actualiza:

* important_moments
* chapter_history

Registrar únicamente eventos relevantes para:

* la trama
* el desarrollo de personajes
* la evolución de las relaciones
* la progresión romántica

# MUNDO Y TERMINOLOGÍA

Actualiza:

* glossary
* locations
* organizations
* items
* magic_terms

Registrar:

* traducción recomendada
* descripción breve
* función narrativa cuando sea relevante

# CRITERIO DE CONFIANZA

Si una información no está claramente presente o fuertemente sugerida por el texto, no la agregues.

IMPORTANTE SOBRE ACTUALIZACIONES

No elimines información existente salvo que el texto la contradiga explícitamente.

Prefiere ampliar y refinar información ya registrada antes que reemplazarla.

Mantén la coherencia con capítulos anteriores.

# ENTRADA

1. JSON base de la obra (para referencia de estructura).
2. Fragmento de la novela ligera.

# SALIDA

Devuelve exclusivamente el JSON actualizado.

---

=== 1. JSON base ===

```json
{
  "volume_metadata": {
    "table_of_contents": [
      {
        "cap_id": "CAP 01",
        "title": "Prologue: オープニング",
        "files": [
          "text-000.xhtml"
        ],
        "narrative_position": 1
      },
      {
        "cap_id": "CAP 02",
        "title": "Chapter 1",
        "files": [
          "text-001.xhtml",
          "text-002.xhtml",
          "text-003.xhtml",
          "text-004.xhtml"
        ],
        "narrative_position": 2
      },
      {
        "cap_id": "CAP 03",
        "title": "Chapter 2",
        "files": [
          "text-005.xhtml",
          "text-006.xhtml",
          "text-007.xhtml",
          "text-008.xhtml",
          "text-009.xhtml"
        ],
        "narrative_position": 3
      },
      {
        "cap_id": "CAP 04",
        "title": "Chapter 3",
        "files": [
          "text-010.xhtml",
          "text-011.xhtml"
        ],
        "narrative_position": 4
      },
      {
        "cap_id": "CAP 05",
        "title": "Interlude 1",
        "files": [
          "text-012.xhtml"
        ],
        "narrative_position": 5
      },
      {
        "cap_id": "CAP 06",
        "title": "Chapter 4",
        "files": [
          "text-013.xhtml",
          "text-014.xhtml"
        ],
        "narrative_position": 6
      },
      {
        "cap_id": "CAP 07",
        "title": "Chapter 5",
        "files": [
          "text-015.xhtml",
          "text-016.xhtml",
          "text-017.xhtml",
          "text-018.xhtml"
        ],
        "narrative_position": 7
      },
      {
        "cap_id": "CAP 08",
        "title": "Interlude 2: 幕間　この思いに名前をつけるなら",
        "files": [
          "text-019.xhtml",
          "text-020.xhtml",
          "text-021.xhtml",
          "text-022.xhtml"
        ],
        "narrative_position": 8
      },
      {
        "cap_id": "CAP 09",
        "title": "Chapter 6",
        "files": [
          "text-023.xhtml",
          "text-024.xhtml",
          "text-025.xhtml",
          "text-026.xhtml"
        ],
        "narrative_position": 9
      },
      {
        "cap_id": "CAP 10",
        "title": "Chapter 7",
        "files": [
          "text-027.xhtml",
          "text-028.xhtml"
        ],
        "narrative_position": 10
      },
      {
        "cap_id": "CAP 11",
        "title": "Epilogue: エンディング",
        "files": [
          "text-029.xhtml"
        ],
        "narrative_position": 11
      }
    ],
    "title": "モブ少女がラスボス魔女を幸せにするまで",
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
  "characters": {
    "ロゼリカ": {
      "translated_name": "Roselika",
      "gender": "",
      "description": "",
      "speech_style": "",
      "speech_profile": {
        "first_person_pronouns": [],
        "second_person_terms": [],
        "common_expressions": [],
        "sentence_endings": [],
        "honorific_patterns": []
      },
      "personality": [],
      "current_goals": [],
      "notes": ""
    }
  },
  "relationships": {
    "_stage_reference": [
      "desconhecidas",
      "colegas",
      "amigas",
      "amigas_proximas",
      "amizade_com_tensao_romantica",
      "interesse_romantico_unilateral",
      "interesse_romantico_mutuo_nao_assumido",
      "quase_casal",
      "casal"
    ],
    "<personagem_A>-<personagem_B>": {
      "relationship_type": "",
      "relationship_stage": "",
      "trust_level": 0,
      "closeness_level": 0,
      "current_status": "",
      "recent_changes": [],
      "notes": ""
    }
  },
  "romantic_subtext": {
    "_scale_reference": {
      "interest_level": {
        "0": "nenhum interesse romântico",
        "1-2": "curiosidade ou atenção ocasional",
        "3-4": "afeição crescente",
        "5-6": "forte apego emocional",
        "7-8": "paixão evidente",
        "9-10": "amor declarado ou praticamente confirmado"
      },
      "awareness_level": {
        "0": "totalmente inconsciente",
        "1-2": "sente algo diferente mas não entende",
        "3-4": "suspeita de sentimentos especiais",
        "5-6": "reconhece possível atração romântica",
        "7-8": "admite internamente os sentimentos",
        "9-10": "aceita completamente seus sentimentos"
      },
      "impact_level": {
        "1": "detalhe pequeno",
        "2": "mudança perceptível",
        "3": "marco importante",
        "4": "ponto de virada",
        "5": "mudança decisiva no relacionamento"
      }
    },
    "<personagem>": {
      "<alvo>": {
        "interest_level": 0,
        "awareness_level": 0,
        "key_indicators": [],
        "latest_developments": [
          {
            "event": "",
            "emotional_significance": "",
            "impact_level": 1
          }
        ]
      }
    }
  },
  "emotional_progress": {
    "<personagem>": {
      "current_emotional_state": "",
      "important_realizations": [],
      "recent_changes": [],
      "internal_conflicts": []
    }
  },
  "speech_dynamics": {
    "<personagem_A>-<personagem_B>": {
      "formality_level": "",
      "honorifics_used": [],
      "nicknames_used": [],
      "changes": []
    }
  },
  "important_moments": [
    {
      "chapter": 0,
      "type": "story|relationship|romance|character_growth",
      "importance": "low|medium|high",
      "description": "",
      "consequences": []
    }
  ],
  "chapter_history": [
    {
      "chapter": 0,
      "summary": "",
      "major_events": [],
      "relationship_changes": [],
      "romantic_progress": []
    }
  ],
  "glossary": {
    "<termo_japones>": {
      "translation": "",
      "description": ""
    }
  },
  "locations": {
    "<nome>": {
      "translation": "",
      "description": ""
    }
  },
  "organizations": {
    "<nome>": {
      "translation": "",
      "description": ""
    }
  },
  "magic_terms": {
    "<nome>": {
      "translation": "",
      "description": ""
    }
  }
}
```

=== 2. Fragmento de historia ===

