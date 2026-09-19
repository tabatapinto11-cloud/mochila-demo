"""Asignaturas del demo, alineadas a los Campos de Saberes del Curriculo Base.

Para agregar una asignatura:
  1. Crear knowledge_base/<clave>/ con uno o mas archivos .md
  2. Agregar la clave en DOMAIN_LABELS y en DOMAIN_KEYWORDS
  3. Llamar POST /api/reindexar
"""

DOMAIN_LABELS = {
    "matematica": "Matematica",
    "ciencias_naturales": "Ciencias Naturales",
    "comunicacion": "Comunicacion y Lenguajes",
    "ciencias_sociales": "Ciencias Sociales",
}

DOMAIN_FIELD = {
    "matematica": "Ciencia Tecnologia y Produccion",
    "ciencias_naturales": "Vida Tierra Territorio",
    "comunicacion": "Comunidad y Sociedad",
    "ciencias_sociales": "Comunidad y Sociedad",
}

# Palabras que empujan una consulta hacia una asignatura cuando el texto
# del alumno no coincide con el vocabulario formal de la base.
# Incluye registro escolar boliviano ("quebrados", "sacar el area").
DOMAIN_KEYWORDS = {
    "matematica": [
        "fraccion", "fracciones", "quebrado", "quebrados", "numerador",
        "denominador", "ecuacion", "algebra", "sumar", "restar", "multiplicar",
        "dividir", "area", "perimetro", "triangulo", "porcentaje",
        "regla de tres", "mcm", "mcd", "promedio", "raiz", "numero",
    ],
    "ciencias_naturales": [
        "celula", "fotosintesis", "planta", "plantas", "hoja", "clorofila",
        "animal", "cuerpo", "digestivo", "respiracion", "atomo", "energia",
        "fuerza", "ecosistema", "agua", "aire", "sol", "altura", "altiplano",
    ],
    "comunicacion": [
        "sujeto", "predicado", "verbo", "sustantivo", "adjetivo", "oracion",
        "tilde", "acento", "ortografia", "escribir", "leer", "texto",
        "resumen", "ensayo", "metafora", "cuento",
    ],
    "ciencias_sociales": [
        "bolivia", "historia", "tiwanaku", "inca", "incario", "colonia",
        "independencia", "revolucion", "guerra", "pacifico", "chaco",
        "constitucion", "plurinacional", "departamento", "departamentos",
        "mapa", "geografia", "derechos", "democracia", "voto",
    ],
}

# Peso del empujon por keyword frente al puntaje TF-IDF del fragmento.
KEYWORD_BOOST = 0.18
