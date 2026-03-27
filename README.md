# Genesys Transcript AI Analyzer (`gtaa`)

Herramienta de línea de comandos que se conecta a **Genesys Cloud** para descargar transcripciones de llamadas telefónicas y procesarlas con **Vertex AI (Gemini)** según los análisis o tareas que el usuario defina mediante prompts.

---

## Tabla de contenidos

- [¿Qué hace esta aplicación?](#qué-hace-esta-aplicación)
- [Arquitectura](#arquitectura)
- [Requisitos previos](#requisitos-previos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Autenticación](#autenticación)
- [Uso](#uso)
- [Modo demo](#modo-demo)
- [Formatos de salida](#formatos-de-salida)
- [Referencia de comandos](#referencia-de-comandos)
- [Estructura del proyecto](#estructura-del-proyecto)

---

## ¿Qué hace esta aplicación?

`gtaa` permite a equipos de contact center y analistas de negocio realizar análisis masivos sobre conversaciones telefónicas sin necesidad de escuchar cada llamada individualmente.

El flujo es el siguiente:

```
Genesys Cloud API
      │
      ▼
Descarga de transcripciones
(filtradas por fecha, cola, agente, etc.)
      │
      ▼
Vertex AI — Gemini
(procesamiento con prompt personalizado)
      │
      ▼
Reporte de resultados
(CSV / Excel / JSON / PDF)
```

### Casos de uso típicos

| Prompt de ejemplo | Resultado |
|---|---|
| "Resume el motivo principal de cada llamada" | Columna de resumen por conversación |
| "Identifica si el cliente quedó satisfecho" | Clasificación de satisfacción |
| "Detecta menciones de competidores" | Flag y extracto por llamada |
| "Extrae los compromisos que asumió el agente" | Lista de follow-ups por conversación |
| "Clasifica el tipo de reclamo según estas categorías: ..." | Taxonomía personalizada |

---

## Arquitectura

```
src/gtaa/
├── auth/
│   ├── genesys.py      OAuth2 Authorization Code para Genesys Cloud
│   ├── gcp.py          Credenciales de usuario GCP (gcloud o OAuth2 directo)
│   └── google.py       Inicialización de Vertex AI SDK
│
├── genesys/
│   ├── client.py       Construcción del API client con token
│   ├── conversations.py  Consulta de conversaciones con filtros y paginación
│   └── transcripts.py  Descarga y parseo de transcripciones (Speech & Text Analytics)
│
├── processor/
│   ├── gemini.py       Análisis individual con Vertex AI Gemini
│   └── batch.py        Orquestación concurrente (ThreadPoolExecutor)
│
├── output/
│   ├── csv_writer.py
│   ├── excel_writer.py
│   ├── json_writer.py
│   └── pdf_writer.py
│
├── demo/
│   └── sample_transcripts.py   5 transcripciones de ejemplo para testing
│
├── config/
│   └── settings.py     Configuración con Pydantic Settings + YAML
│
└── cli/
    └── main.py         Interfaz Click (analyze, auth, demo)
```

### Autenticación GCP — dos caminos

La aplicación detecta automáticamente si `gcloud` CLI está instalado y elige el mejor camino:

```
¿gcloud CLI instalado?
    ├── SÍ  → gcloud auth application-default login
    │         (recomendado, más simple)
    └── NO  → OAuth2 Authorization Code directo
              (requiere GCP_OAUTH_CLIENT_ID y GCP_OAUTH_CLIENT_SECRET)
```

En ambos casos el token queda vinculado al usuario que inició sesión, por lo que cada llamada a Vertex AI queda registrada en los **Cloud Audit Logs** con el email del usuario (`principalEmail`).

---

## Requisitos previos

| Herramienta | Versión mínima | Notas |
|---|---|---|
| Python | 3.11 | Verificar con `python --version` |
| Git | cualquiera | Para clonar el repositorio |
| gcloud CLI | cualquiera | Opcional pero recomendado |
| Cuenta Genesys Cloud | — | Con permisos de Analytics y Speech & Text Analytics |
| Proyecto GCP | — | Con Vertex AI API habilitada y rol `Vertex AI User` en tu cuenta |

### Instalar gcloud CLI (recomendado)

1. Descargar el instalador desde [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
2. Ejecutar el instalador y seguir los pasos
3. Verificar con `gcloud --version`

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/pcaamano182/genesys_transcipt_ai_assistant.git
cd genesys_transcipt_ai_assistant
```

### 2. (Opcional) Crear entorno virtual

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Instalar el paquete y dependencias

```bash
pip install -e .
```

Esto instala el comando `gtaa` y todas sus dependencias (Genesys SDK, Vertex AI, Click, Rich, etc.).

### 4. Verificar la instalación

```bash
python -m gtaa.cli.main --version
# gtaa, version 0.1.0
```

---

## Configuración

### Archivo `.env`

Copiar el archivo de ejemplo y completar con las credenciales:

```bash
cp .env.example .env
```

Contenido del `.env`:

```bash
# ── Genesys Cloud ──────────────────────────────────────────────
# Client ID y Secret de la aplicación OAuth2 registrada en Genesys Cloud.
# Tipo de aplicación: "Code Authorization"
GENESYS_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GENESYS_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Región de tu organización Genesys Cloud
# Opciones: us_east_1 | us_west_2 | eu_west_1 | eu_west_2 |
#           ap_southeast_2 | ap_northeast_1 | ca_central_1 | sa_east_1
GENESYS_REGION=us_west_2

# ── Google Cloud ───────────────────────────────────────────────
# ID del proyecto GCP donde está habilitada la Vertex AI API
GOOGLE_CLOUD_PROJECT=mi-proyecto-gcp

# ── Solo si gcloud CLI NO está instalado ───────────────────────
# Crear en GCP Console → APIs & Services → Credentials
# → Create OAuth Client ID → Desktop app
GCP_OAUTH_CLIENT_ID=
GCP_OAUTH_CLIENT_SECRET=
```

### Archivo `config/default.yaml`

Configuración avanzada con valores por defecto. No es necesario modificarlo en uso normal.

```yaml
genesys:
  region: us_west_2
  page_size: 100            # Conversaciones por página en la API

google:
  location: "us-central1"   # Región de Vertex AI
  model: "gemini-1.5-pro"   # Modelo Gemini a utilizar

processing:
  batch_size: 20            # Transcripciones por batch
  max_workers: 5            # Llamadas concurrentes a Vertex AI
  max_retries: 3            # Reintentos ante errores transitorios
  max_transcript_chars: 100000  # Límite de caracteres por transcripción

output:
  default_formats: [csv]
  output_dir: "./output"
```

---

## Autenticación

La aplicación requiere autenticación por separado para Genesys Cloud y Google Cloud. Ambas sesiones se guardan localmente en `~/.gtaa/` y se renuevan automáticamente.

### Genesys Cloud

```bash
python -m gtaa.cli.main auth login
```

Abre el browser. Completar el login con tu cuenta corporativa (SSO). El token se guarda en `~/.gtaa/tokens.json`.

Verificar estado:

```bash
python -m gtaa.cli.main auth status
```

### Google Cloud

```bash
python -m gtaa.cli.main auth gcp-login --project mi-proyecto-gcp
```

Abre el browser. Completar el login con tu cuenta corporativa (SSO — Okta, Azure AD, etc. si está federado). Las credenciales se guardan en `~/.gtaa/gcp_credentials.json`.

Verificar estado:

```bash
python -m gtaa.cli.main auth gcp-status
```

Cerrar sesión GCP:

```bash
python -m gtaa.cli.main auth gcp-logout
```

> **¿Por qué credenciales de usuario y no service account?**
> Usando credenciales personales, cada llamada a Vertex AI queda registrada en Cloud Audit Logs con tu email (`principalEmail`), lo que permite trazabilidad de uso y control de costos por usuario.

---

## Uso

### Análisis básico

```bash
python -m gtaa.cli.main analyze \
  --start-date 2025-03-01 \
  --end-date 2025-03-07 \
  --prompt "Resume el motivo principal de cada llamada en una oración"
```

### Con filtros

```bash
python -m gtaa.cli.main analyze \
  --start-date 2025-03-01 \
  --end-date 2025-03-31 \
  --queue "a1b2c3d4-queue-id" \
  --min-duration 60 \
  --prompt "Identifica si el cliente manifestó intención de cancelar el servicio" \
  --output-format csv \
  --output-format excel \
  --output-dir ./reportes/marzo
```

### Prompt desde archivo

Para prompts largos o que se reutilizan, conviene guardarlos en un archivo `.txt`:

```bash
python -m gtaa.cli.main analyze \
  --start-date 2025-03-01 \
  --end-date 2025-03-07 \
  --prompt-file prompts/analisis_retencion.txt \
  --output-format excel
```

### Ver conversaciones sin procesar (dry run)

Útil para verificar los filtros antes de consumir tokens de Vertex AI:

```bash
python -m gtaa.cli.main analyze \
  --start-date 2025-03-01 \
  --end-date 2025-03-07 \
  --dry-run
```

### Ajustar concurrencia para alto volumen

```bash
python -m gtaa.cli.main analyze \
  --start-date 2025-03-01 \
  --end-date 2025-03-31 \
  --prompt "Clasifica el tipo de consulta" \
  --batch-size 50 \
  --max-workers 10 \
  --output-format csv
```

---

## Modo demo

Permite probar el análisis con transcripciones de ejemplo sin necesitar credenciales de Genesys Cloud. Solo requiere GCP autenticado.

### Transcripciones disponibles

```bash
python -m gtaa.cli.main demo --list-samples
```

```
  #   Queue / Scenario      Duration
  1   Billing Support        5m 12s    Disputa de cobro duplicado (banco)
  2   Technical Support      8m 07s    Corte de internet - soporte técnico
  3   Customer Retention    10m 23s    Cliente quiere cancelar servicio
  4   Appointments           4m 18s    Reprogramación de turno médico
  5   Customer Service       9m 02s    TV dañado en envío - e-commerce
```

### Ver el texto de una transcripción

```bash
python -m gtaa.cli.main demo --sample 1 --show-transcript
```

### Analizar con prompt personalizado

```bash
# Todos los samples
python -m gtaa.cli.main demo \
  --prompt "Evalúa el desempeño del agente en escala del 1 al 5 y justifica" \
  --output-format csv \
  --output-format excel

# Un sample específico
python -m gtaa.cli.main demo \
  --sample 3 \
  --prompt "El cliente intentó cancelar. ¿El agente logró retenerlo? ¿Qué oferta realizó?"
```

---

## Formatos de salida

Todos los archivos se generan en `./output/` (configurable con `--output-dir`).

| Flag | Archivo generado | Descripción |
|---|---|---|
| `--output-format csv` | `analysis_FECHA.csv` | Tabla plana, ideal para Excel o BI |
| `--output-format json` | `analysis_FECHA.json` | Datos estructurados con transcript completo |
| `--output-format excel` | `analysis_FECHA.xlsx` | Planilla formateada con colores y anchos de columna |
| `--output-format pdf` | `analysis_FECHA.pdf` | Reporte imprimible, una conversación por página |

Se pueden combinar en el mismo comando:

```bash
--output-format csv --output-format excel --output-format pdf
```

---

## Referencia de comandos

### `gtaa analyze`

| Opción | Requerido | Descripción |
|---|---|---|
| `--start-date` | Sí | Fecha de inicio `YYYY-MM-DD` |
| `--end-date` | Sí | Fecha de fin `YYYY-MM-DD` |
| `--queue` | No | ID de cola (repetible) |
| `--agent` | No | ID de agente (repetible) |
| `--division` | No | ID de división (repetible) |
| `--min-duration` | No | Duración mínima en segundos |
| `--prompt` | No | Texto del prompt de análisis |
| `--prompt-file` | No | Path a archivo `.txt` con el prompt |
| `--output-format` | No | `csv` / `json` / `excel` / `pdf` (repetible, default: `csv`) |
| `--output-dir` | No | Directorio de salida (default: `./output`) |
| `--batch-size` | No | Conversaciones por batch (default: `20`) |
| `--max-workers` | No | Hilos concurrentes (default: `5`) |
| `--dry-run` | No | Lista conversaciones sin procesar |
| `--config` | No | Path a YAML de configuración custom |

### `gtaa auth`

| Comando | Descripción |
|---|---|
| `auth login` | Autenticar con Genesys Cloud (abre browser) |
| `auth status` | Ver estado de sesión Genesys |
| `auth gcp-login --project ID` | Autenticar con Google Cloud (abre browser) |
| `auth gcp-status` | Ver estado de sesión GCP |
| `auth gcp-logout` | Eliminar credenciales GCP en caché |

### `gtaa demo`

| Opción | Descripción |
|---|---|
| `--list-samples` | Listar transcripciones de ejemplo disponibles |
| `--sample 1..5` | Seleccionar samples específicos (repetible) |
| `--show-transcript` | Imprimir el texto de la transcripción antes del análisis |
| `--prompt` | Prompt personalizado |
| `--prompt-file` | Path a archivo con el prompt |
| `--output-format` | Igual que en `analyze` |
| `--output-dir` | Directorio de salida (default: `./output/demo`) |

---

## Estructura del proyecto

```
genesys_transcipt_ai_assistant/
├── .env.example              Variables de entorno (plantilla)
├── .gitignore
├── pyproject.toml            Definición del paquete y dependencias
├── config/
│   └── default.yaml          Configuración por defecto
├── src/
│   └── gtaa/
│       ├── auth/
│       │   ├── gcp.py        Autenticación GCP con soporte SSO
│       │   ├── genesys.py    OAuth2 Genesys Cloud
│       │   └── google.py     Inicialización Vertex AI
│       ├── cli/
│       │   └── main.py       Comandos CLI (Click)
│       ├── config/
│       │   └── settings.py   Validación de configuración (Pydantic)
│       ├── demo/
│       │   └── sample_transcripts.py  Datos de prueba
│       ├── genesys/
│       │   ├── client.py
│       │   ├── conversations.py
│       │   └── transcripts.py
│       ├── output/
│       │   ├── csv_writer.py
│       │   ├── excel_writer.py
│       │   ├── json_writer.py
│       │   └── pdf_writer.py
│       └── processor/
│           ├── batch.py
│           └── gemini.py
└── tests/
```
