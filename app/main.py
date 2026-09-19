"""Mochila Virtual - asistente socratico offline.

Modo demo: no genera texto con un LLM. Recupera el andamiaje socratico que el
equipo escribio para cada concepto del curriculo. Esto evita alucinaciones y
contenido inapropiado ante menores, y corre en hardware de 1 GB de RAM.

Arranque:
    cd app && uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from domains import DOMAIN_FIELD, DOMAIN_LABELS
from retriever import Indice

AQUI = Path(__file__).resolve().parent
BASE = Path(os.getenv("KB_PATH", AQUI.parent / "knowledge_base"))
DB = Path(os.getenv("DB_PATH", AQUI.parent / "uso.db"))
UMBRAL = float(os.getenv("MIN_SCORE", "0.12"))

app = FastAPI(title="Mochila Virtual", version="0.1-demo")
indice = Indice(BASE)


# ---------------------------------------------------------------- registro
# Solo contadores agregados. Nunca se guarda quien pregunto ni desde que
# dispositivo: el texto de la consulta se guarda para calibrar el enrutador,
# sin ningun identificador asociado.

def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute(
        """CREATE TABLE IF NOT EXISTS consultas (
               dia TEXT, consulta TEXT, dominio TEXT,
               puntaje REAL, resuelta INTEGER)"""
    )
    return con


def registrar(consulta: str, dominio: str, puntaje: float, resuelta: bool) -> None:
    try:
        con = _db()
        con.execute(
            "INSERT INTO consultas VALUES (?,?,?,?,?)",
            (date.today().isoformat(), consulta[:200], dominio, puntaje, int(resuelta)),
        )
        con.commit()
        con.close()
    except Exception as e:  # el registro nunca debe tumbar una respuesta
        print(f"[aviso] no se pudo registrar la consulta: {e}")


# ---------------------------------------------------------------- modelos

class Consulta(BaseModel):
    texto: str = Field(min_length=2, max_length=500)


# ---------------------------------------------------------------- ciclo

@app.on_event("startup")
def arrancar() -> None:
    t0 = time.time()
    n = indice.cargar()
    print(f"[ok] {n} fragmentos indexados en {time.time() - t0:.2f}s desde {BASE}")


# ---------------------------------------------------------------- endpoints

@app.get("/api/salud")
def salud() -> dict:
    return {"estado": "ok" if indice.fragmentos else "sin contenido", **indice.resumen()}


@app.get("/api/asignaturas")
def asignaturas() -> list[dict]:
    presentes = {f.dominio for f in indice.fragmentos}
    return [
        {"clave": d, "nombre": DOMAIN_LABELS[d], "campo": DOMAIN_FIELD.get(d, "")}
        for d in DOMAIN_LABELS
        if d in presentes
    ]


@app.post("/api/preguntar")
def preguntar(c: Consulta) -> dict:
    resultados = indice.buscar(c.texto, k=3)

    if not resultados or resultados[0].puntaje < UMBRAL:
        registrar(c.texto, "", resultados[0].puntaje if resultados else 0.0, False)
        return {
            "encontrado": False,
            "mensaje": (
                "Esa pregunta todavia no esta en la mochila. Anotala y "
                "preguntale a tu profe: la vamos a agregar."
            ),
            "cercanos": [r.fragmento.tema for r in resultados[:2]],
        }

    mejor = resultados[0]
    f = mejor.fragmento
    registrar(c.texto, f.dominio, mejor.puntaje, True)

    return {
        "encontrado": True,
        "asignatura": DOMAIN_LABELS[f.dominio],
        "campo": DOMAIN_FIELD.get(f.dominio, ""),
        "tema": f.tema,
        "nivel": f.nivel,
        "pregunta": f.pregunta,
        "pistas": f.pistas,
        "error_comun": f.error_comun,
        "lengua_originaria": f.lengua_originaria,
        "confianza": mejor.puntaje,
        "relacionados": [r.fragmento.tema for r in resultados[1:]],
    }


@app.post("/api/reindexar")
def reindexar() -> dict:
    n = indice.cargar()
    return {"reindexado": True, "fragmentos": n}


@app.get("/api/estadisticas")
def estadisticas() -> dict:
    con = _db()
    filas = con.execute(
        """SELECT dominio, COUNT(*), AVG(puntaje)
           FROM consultas WHERE resuelta=1 GROUP BY dominio"""
    ).fetchall()
    total = con.execute("SELECT COUNT(*) FROM consultas").fetchone()[0]
    sin_respuesta = con.execute(
        "SELECT COUNT(*) FROM consultas WHERE resuelta=0"
    ).fetchone()[0]
    huecos = con.execute(
        """SELECT consulta, COUNT(*) c FROM consultas WHERE resuelta=0
           GROUP BY consulta ORDER BY c DESC LIMIT 10"""
    ).fetchall()
    con.close()
    return {
        "consultas_totales": total,
        "sin_respuesta": sin_respuesta,
        "cobertura": round(1 - sin_respuesta / total, 3) if total else None,
        "por_asignatura": [
            {"asignatura": DOMAIN_LABELS.get(d, d), "consultas": n,
             "confianza_media": round(p, 3)}
            for d, n, p in filas
        ],
        "contenido_faltante": [{"consulta": q, "veces": c} for q, c in huecos],
    }


# La interfaz se sirve al final para no tapar las rutas /api
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")


@app.get("/")
def inicio() -> FileResponse:
    return FileResponse(AQUI / "static" / "index.html")
