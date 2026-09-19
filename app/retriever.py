"""Recuperador ligero: TF-IDF + similitud coseno, solo con la libreria estandar.

Motivo: una Raspberry Pi 3 tiene 1 GB de RAM. sentence-transformers + FAISS
necesitan ~500 MB solo para cargarse. Con 4 asignaturas y unos cientos de
fragmentos, TF-IDF sobre texto normalizado da resultados equivalentes y
responde en milisegundos.

Cuando el proyecto pase a Raspberry Pi 5, este modulo se puede reemplazar por
el pipeline de embeddings sin tocar main.py: basta respetar la firma
buscar(texto) -> list[Resultado].
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from domains import DOMAIN_FIELD, DOMAIN_KEYWORDS, DOMAIN_LABELS, KEYWORD_BOOST

# Palabras sin valor discriminante en espanol escolar.
STOPWORDS = {
    "a", "al", "algo", "algun", "alguna", "algunos", "ante", "aqui", "asi",
    "aunque", "cada", "como", "con", "cual", "cuales", "cuando", "cuanto",
    "de", "del", "desde", "donde", "dos", "el", "ella", "ellos", "en", "entre",
    "era", "eres", "es", "esa", "ese", "eso", "esta", "estan", "este", "esto",
    "estos", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me", "mi",
    "muy", "no", "nos", "o", "para", "pero", "por", "porque", "que", "quien",
    "se", "ser", "si", "sin", "sobre", "solo", "son", "su", "sus", "tan",
    "te", "tiene", "todo", "todos", "tu", "un", "una", "uno", "unos", "y",
    "ya", "yo", "profe", "hola", "favor", "gracias", "entiendo", "explicame",
    "ayuda", "ayudame", "sirve", "significa",
}


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes, sin signos. 'Fracción' y 'fraccion' coinciden."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def tokenizar(texto: str) -> list[str]:
    palabras = re.findall(r"[a-z0-9]+", normalizar(texto))
    return [p for p in palabras if len(p) > 2 and p not in STOPWORDS]


@dataclass
class Fragmento:
    """Un concepto del curriculo con su andamiaje socratico."""

    dominio: str
    tema: str
    nivel: str = ""
    pregunta: str = ""
    pistas: list[str] = field(default_factory=list)
    error_comun: str = ""
    lengua_originaria: str = ""
    claves: str = ""
    archivo: str = ""

    def texto_indexable(self) -> str:
        partes = [
            self.tema, self.tema, self.tema,  # el titulo pesa triple
            self.claves, self.claves,
            self.pregunta,
            " ".join(self.pistas),
            self.error_comun,
        ]
        return " ".join(p for p in partes if p)


@dataclass
class Resultado:
    fragmento: Fragmento
    puntaje: float


CAMPOS = {
    "NIVEL": "nivel",
    "PREGUNTA": "pregunta",
    "ERROR COMUN": "error_comun",
    "LENGUA": "lengua_originaria",
    "CLAVES": "claves",
}


def _parsear_bloque(bloque: str, dominio: str, archivo: str) -> Fragmento | None:
    """Convierte un bloque de markdown en un Fragmento.

    Formato esperado (los bloques se separan con una linea '---'):

        ## Fracciones equivalentes
        NIVEL: Primaria 5to-6to
        CLAVES: quebrados, partes iguales, mitad
        PREGUNTA: Si partes una marraqueta en dos y comes una, cuanto comiste?
        PISTAS:
        - Dibuja las dos formas de partir y compara los pedazos.
        - Mira que le paso al numero de arriba y al de abajo.
        ERROR COMUN: multiplicar solo el numerador.
        LENGUA: aymara: t'aqa (parte, porcion)
    """
    lineas = [l.rstrip() for l in bloque.strip().splitlines() if l.strip()]
    if not lineas:
        return None

    tema = ""
    if lineas[0].startswith("#"):
        tema = lineas[0].lstrip("#").strip()
        lineas = lineas[1:]
    if not tema:
        return None

    frag = Fragmento(dominio=dominio, tema=tema, archivo=archivo)
    en_pistas = False

    for linea in lineas:
        if linea.upper().startswith("PISTAS"):
            en_pistas = True
            continue
        if en_pistas and linea.startswith(("-", "*")):
            frag.pistas.append(linea.lstrip("-* ").strip())
            continue

        encontrado = False
        for etiqueta, atributo in CAMPOS.items():
            if linea.upper().startswith(etiqueta + ":"):
                valor = linea.split(":", 1)[1].strip()
                setattr(frag, atributo, valor)
                en_pistas = False
                encontrado = True
                break
        if not encontrado and not en_pistas:
            # Texto libre: se suma a las claves para que tambien sea buscable.
            frag.claves = (frag.claves + " " + linea).strip()

    return frag if frag.pregunta else None


class Indice:
    """Indice TF-IDF en memoria. Se reconstruye entero en cada reindexado."""

    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.fragmentos: list[Fragmento] = []
        self.vectores: list[dict[str, float]] = []
        self.idf: dict[str, float] = {}

    # ---------- construccion ----------

    def cargar(self) -> int:
        self.fragmentos = []
        for carpeta in sorted(self.raiz.iterdir()):
            if not carpeta.is_dir():
                continue
            dominio = carpeta.name
            if dominio not in DOMAIN_LABELS:
                print(f"[aviso] carpeta '{dominio}' sin entrada en domains.py, se ignora")
                continue
            for archivo in sorted(carpeta.glob("*.md")):
                texto = archivo.read_text(encoding="utf-8")
                # Las lineas '---' son separadores visuales; el corte real
                # ocurre en cada titulo '## '. Lo anterior al primer '##' es
                # el encabezado del archivo y no es un concepto.
                texto = re.sub(r"(?m)^-{3,}\s*$", "", texto)
                for bloque in re.split(r"(?m)^##\s+", texto)[1:]:
                    frag = _parsear_bloque("## " + bloque, dominio, archivo.name)
                    if frag:
                        self.fragmentos.append(frag)
        self._vectorizar()
        return len(self.fragmentos)

    def _vectorizar(self) -> None:
        docs = [tokenizar(f.texto_indexable()) for f in self.fragmentos]
        n = len(docs) or 1
        apariciones: Counter[str] = Counter()
        for d in docs:
            apariciones.update(set(d))
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in apariciones.items()}

        self.vectores = []
        for d in docs:
            tf = Counter(d)
            total = sum(tf.values()) or 1
            vec = {t: (c / total) * self.idf.get(t, 1.0) for t, c in tf.items()}
            norma = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.vectores.append({t: v / norma for t, v in vec.items()})

    # ---------- consulta ----------

    def _vector_consulta(self, texto: str) -> dict[str, float]:
        tf = Counter(tokenizar(texto))
        total = sum(tf.values()) or 1
        vec = {t: (c / total) * self.idf.get(t, 1.0) for t, c in tf.items()}
        norma = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norma for t, v in vec.items()}

    def _dominios_sugeridos(self, texto: str) -> set[str]:
        norm = normalizar(texto)
        return {
            dom
            for dom, claves in DOMAIN_KEYWORDS.items()
            if any(normalizar(k) in norm for k in claves)
        }

    def buscar(self, texto: str, k: int = 3) -> list[Resultado]:
        if not self.fragmentos:
            return []
        q = self._vector_consulta(texto)
        if not q:
            return []
        sugeridos = self._dominios_sugeridos(texto)

        puntajes: list[Resultado] = []
        for frag, vec in zip(self.fragmentos, self.vectores):
            s = sum(peso * vec.get(t, 0.0) for t, peso in q.items())
            if frag.dominio in sugeridos:
                s += KEYWORD_BOOST
            if s > 0:
                puntajes.append(Resultado(frag, round(s, 4)))

        puntajes.sort(key=lambda r: r.puntaje, reverse=True)
        return puntajes[:k]

    # ---------- utilidades ----------

    def resumen(self) -> dict:
        por_dominio: Counter[str] = Counter(f.dominio for f in self.fragmentos)
        return {
            "fragmentos": len(self.fragmentos),
            "asignaturas": {
                DOMAIN_LABELS[d]: {
                    "fragmentos": c,
                    "campo": DOMAIN_FIELD.get(d, ""),
                }
                for d, c in sorted(por_dominio.items())
            },
            "vocabulario": len(self.idf),
        }
