# Mochila Virtual — demo

Asistente socrático offline para colegios. Responde con preguntas, no con
respuestas: recupera el andamiaje que el equipo docente escribió para cada
concepto del Currículo Base y lo entrega en pistas escalonadas.

Corre en una **Raspberry Pi ** sin conexión a internet.

## Por qué esta versión no usa un LLM

El repositorio principal (`proyecto-colegios`) genera respuestas con Ollama +
FAISS + sentence-transformers, y necesita una Pi 5 de 8 GB. Este demo usa en su
lugar un recuperador TF-IDF escrito con la librería estándar de Python:

| | Versión generativa | Este demo |
|---|---|---|
| RAM en reposo | ~2.5 GB | ~70 MB |
| Tiempo de respuesta en Pi 3 | minutos (swap) | < 100 ms |
| Dependencias | Docker + Ollama + torch | 3 paquetes pip |

El contenido socrático se escribe una vez, revisado por docentes. Para el
piloto con menores esto es además una ventaja: ninguna respuesta que vea un
estudiante fue generada en tiempo real.

## Estructura

```
mochila-demo/
├── app/
│   ├── main.py            API FastAPI + registro anónimo en SQLite
│   ├── retriever.py       TF-IDF y coseno, sin dependencias externas
│   ├── domains.py         asignaturas y palabras clave
│   └── static/index.html  interfaz completa, sin recursos externos
├── knowledge_base/
│   ├── matematica/
│   ├── ciencias_naturales/
│   ├── comunicacion/
│   └── ciencias_sociales/
├── scripts/install-pi.sh  instalación como servicio systemd
├── config/mikrotik-demo.rsc  configuración del router del aula
└── requirements.txt
```

20 conceptos cargados en las cuatro asignaturas.

## Probar en tu PC

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd app && uvicorn main:app --reload --port 8000
```

Abre `http://localhost:8000`.

## Instalar en la Raspberry Pi

```bash
git clone https://github.com/tabatapinto11-cloud/mochila-demo.git
cd mochila-demo
bash scripts/install-pi.sh
```

El script crea el entorno virtual, registra el servicio `mochila` y lo habilita
al arranque. Después de un corte de luz la Pi vuelve sola.

```bash
sudo systemctl status mochila     # estado
journalctl -u mochila -f          # logs en vivo
sudo systemctl restart mochila    # reiniciar
```

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/` | interfaz de chat |
| GET | `/api/salud` | estado e inventario de contenido |
| POST | `/api/preguntar` | `{"texto": "..."}` → pregunta socrática y pistas |
| POST | `/api/reindexar` | recarga `knowledge_base/` sin reiniciar |
| GET | `/api/estadisticas` | uso agregado y **qué contenido falta** |

`/api/estadisticas` lista las consultas que
el sistema no supo resolver, ordenadas por frecuencia. Ese listado es la cola
de trabajo de contenido para el siguiente ciclo.

## Agregar contenido

1. Crear o editar un `.md` en la carpeta de la asignatura.
2. `curl -X POST http://mochila.edu:8000/api/reindexar`

Formato de cada concepto:

```markdown
## Fracciones equivalentes
NIVEL: Primaria 5to-6to
CLAVES: quebrados, mitad, simplificar
PREGUNTA: Comes 1 de 2 pedazos de una api y tu amiga 2 de 4. Quién comió más?
PISTAS:
- Dibuja las dos apis del mismo tamaño y pinta lo que comió cada una.
- Compara las superficies antes de mirar los números.
ERROR COMUN: creer que 2/4 es más que 1/2 porque los números son mayores.
PALABRAS TRADUCIDAS: aymara: quechua 
```

`CLAVES` es donde va el vocabulario real de los estudiantes ("quebrados",
"sacar el área"), que casi nunca coincide con el término formal. Alimenta ese
campo con lo que aparezca en `contenido_faltante`.

Para agregar una asignatura nueva: crear la carpeta y añadir la clave en
`DOMAIN_LABELS` y `DOMAIN_KEYWORDS` de `app/domains.py`.

## Privacidad

Se registran día, texto de la consulta, asignatura y puntaje. No se guarda
nombre, dispositivo, dirección IP ni sesión, y nada sale del servidor local: la
regla de firewall del router bloquea todo tráfico hacia el puerto WAN.
