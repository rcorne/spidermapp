# Pidge 2.0

Auditor de SEO de escritorio, similar a Screaming Frog SEO Spider. Rastrea un sitio siguiendo
enlaces internos y audita cada URL contra una lista amplia de checks técnicos de SEO.
Disponible como app de macOS y como programa de Windows.

(El paquete de Python y el repositorio conservan el nombre interno `spidermapp` — solo el
branding de cara al usuario, los binarios empaquetados y el título de la ventana usan
"Pidge".)

## Novedades de la 2.0

Incorpora funcionalidad adaptada de [LibreCrawl](https://github.com/PhialsBasement/LibreCrawl)
(MIT — ver [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)) sobre el motor asíncrono que
Pidge ya tenía:

- **Pausar y retomar un rastreo.** El crawler guarda la cola pendiente en disco cada pocos
  segundos. Si pausas, detienes, cierras la app, o el equipo se suspende a medio camino, el
  avance no se pierde: *Análisis → Retomar crawl guardado…* continúa desde donde quedó en vez
  de volver a rastrear todo. (Complementa la opción de evitar la suspensión: esa *previene* que
  el equipo duerma, el checkpoint *sobrevive* a que duerma igual.)
- **Errores de red diagnosticados.** Un fallo de rastreo ya no dice solo "no se pudo conectar":
  distingue dominio que no resuelve (DNS), timeout, conexión rechazada y problema de
  certificado/TLS — cada uno con su propia recomendación, porque cada uno se arregla distinto.
- **Detección de imágenes rotas.** Antes se revisaba el `alt`; ahora también se verifica que
  cada imagen efectivamente cargue (con HEAD, para no descargar los archivos completos).
- **Límite de ritmo opcional.** Un tope de peticiones por segundo para sitios frágiles o
  compartidos, que reparte las peticiones de forma pareja en vez de mandarlas en ráfagas.
- **Windows.** La prevención de suspensión ahora usa `SetThreadExecutionState` en Windows y
  `caffeinate` en macOS, y el empaquetado cubre ambas plataformas.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
playwright install chromium   # necesario para el check de renderizado JS / mobile vs desktop
```

## Uso

```bash
source .venv/bin/activate
python -m spidermapp.main
# o, tras el pip install -e .:
spidermapp
```

En la app: ingresa la URL semilla, ajusta máx. páginas / profundidad / concurrencia, activa
"Renderizar JS" si quieres comparar HTML crudo vs renderizado y mobile vs desktop (más lento),
y presiona "Iniciar crawl". Los resultados aparecen en vivo en la tabla; la barra lateral
izquierda filtra por categoría de issue. Exporta a CSV o XLSX desde la barra superior.

## Empaquetar para Windows (.exe)

**PyInstaller solo puede construir para el sistema operativo donde se ejecuta** — no existe
compilación cruzada: desde un Mac no se puede generar un `.exe` de Windows. Por eso el binario
de Windows lo construye GitHub Actions en un runner `windows-latest`, no la máquina local.

El workflow está en [`.github/workflows/build.yml`](.github/workflows/build.yml) y corre solo
en cada push a `main`. Produce dos formatos para Windows:

- **`Pidge-Setup-2.0.0.exe`** — el instalador. Instala en Archivos de programa, crea accesos
  directos en el menú Inicio (y opcionalmente en el escritorio) y registra un desinstalador en
  "Aplicaciones y características". Es lo que se le entrega a alguien más.
- **`Pidge-windows-portable.zip`** — la carpeta cruda con `Pidge.exe` dentro, para correrlo sin
  instalar nada.

El instalador se arma con [Inno Setup](https://jrsoftware.org/isinfo.php) a partir de
[`packaging/windows/pidge.iss`](packaging/windows/pidge.iss). Igual que el `.exe`, **solo se
puede compilar en Windows** — de ahí que lo haga el runner y no la máquina local.

Para bajar el resultado:

1. Ve a la pestaña **Actions** del repo en GitHub.
2. Abre la ejecución más reciente de "Build Pidge".
3. Descarga **Pidge-windows-installer**, **Pidge-windows-portable** o **Pidge-macos**.

Windows va a mostrar una advertencia de SmartScreen la primera vez que se ejecute el
instalador ("Windows protegió tu PC" → *Más información* → *Ejecutar de todas formas*). Es
normal en instaladores sin firma digital: eliminarla requiere un certificado de firma de código
(unos USD 200–400 al año, a nombre tuyo o de tu empresa), que es un trámite aparte.

Al publicar un tag de versión (`git tag v2.0.0 && git push --tags`) el workflow además adjunta
ambos instaladores al release de GitHub automáticamente.

Si prefieres construirlo tú en una máquina Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller packaging/spidermapp.spec --noconfirm
```

El resultado queda en `dist\Pidge\Pidge.exe`.

## Empaquetar como app de macOS (.app / .dmg)

Ya generado en este repo: [`packaging/icon/Spidermapp.icns`](packaging/icon/Spidermapp.icns) (ícono,
diseñado a partir de [`spidermapp_icon.svg`](packaging/icon/spidermapp_icon.svg)),
[`packaging/spidermapp.spec`](packaging/spidermapp.spec) (spec de PyInstaller) y
`packaging/Pidge.dmg` (instalador). Para regenerarlos tras cambios en el código:

```bash
source .venv/bin/activate
pip install pyinstaller
rm -rf build dist
pyinstaller packaging/spidermapp.spec --noconfirm
```

Esto produce `dist/Pidge.app`. Para armar el `.dmg` (app + acceso directo a /Applications,
con ícono de volumen propio):

```bash
rm -rf packaging/dmg_staging packaging/Pidge.dmg
mkdir -p packaging/dmg_staging
cp -R dist/Pidge.app packaging/dmg_staging/
ln -s /Applications packaging/dmg_staging/Applications
cp packaging/icon/Spidermapp.icns packaging/dmg_staging/.VolumeIcon.icns
hdiutil create -srcfolder packaging/dmg_staging -volname "Pidge" -fs HFS+ -format UDRW -ov packaging/Pidge_rw.dmg
VOLUME=$(hdiutil attach packaging/Pidge_rw.dmg -readwrite -noverify -noautoopen | grep -Eo '/Volumes/.*')
SetFile -a C "$VOLUME"
hdiutil detach "$VOLUME"
hdiutil convert packaging/Pidge_rw.dmg -format UDZO -o packaging/Pidge.dmg -ov
rm -f packaging/Pidge_rw.dmg
```

Para instalar: abre el `.dmg` y arrastra `Pidge.app` al acceso directo de Applications, o
directamente `cp -R dist/Pidge.app /Applications/`.

**Nota sobre Playwright en la app empaquetada:** el binario de Chromium (~170 MB) no viaja dentro
del `.app` — Playwright lo busca en `~/Library/Caches/ms-playwright`, el mismo caché que usa
cualquier instalación de Playwright en esa Mac. Si Pidge se instala en una máquina donde
nunca se corrió `playwright install chromium`, el check de renderizado fallará hasta correr ese
comando una vez en esa Mac (con cualquier Python que tenga `playwright` instalado, no hace falta
el venv del proyecto).

## Cuentas y chat (pidge_server)

Crear cuenta, iniciar sesión con Google/GitHub/Apple, y el chat en tiempo real dependen de
`pidge_server/`, un backend FastAPI aparte (no vive dentro de la app de escritorio, que no tiene
servidor propio). Para correrlo localmente:

```bash
source .venv/bin/activate
uvicorn pidge_server.main:app --reload
```

Por defecto escucha en `http://127.0.0.1:8000` y guarda todo (usuarios, mensajes) en SQLite en
`~/.pidge_server/pidge.db`. La app apunta ahí por defecto (Preferencias → Cuenta → Servidor Pidge);
mientras el servidor esté corriendo en esa misma Mac, crear cuenta/iniciar sesión/chatear funciona
igual que cualquier app cliente-servidor.

**Para que varias personas lo usen de verdad** (no solo en una Mac) hay que desplegar
`pidge_server/` en algún lugar accesible por todos, y apuntar el campo "Servidor" (Preferencias →
Cuenta) de cada instalación de Pidge a esa URL.

### Por qué no en el hosting compartido de GoDaddy

El hosting compartido/cPanel típico de GoDaddy (el que usa la mayoría de los sitios web
tradicionales) **no puede correr `pidge_server`**: está pensado para PHP servido por Apache, sin
acceso para dejar un proceso Python corriendo de forma persistente (`uvicorn`), sin soporte real
de WebSockets (lo que necesita el chat en tiempo real), y sin acceso root/Docker. No es un
límite de la app — es una limitación real de ese tipo de hosting, y forzarlo no va a funcionar.

**Lo que sí funciona** — mantener el dominio en GoDaddy (para eso sirve bien) y correr
`pidge_server` en un servicio pensado para procesos Python persistentes. La opción más simple es
**Railway**:

1. Crea una cuenta en [railway.app](https://railway.app) (con tu email o GitHub) — esto lo tienes
   que hacer tú, no puedo crear cuentas ni pagar servicios en tu nombre.
2. "New Project" → "Deploy from GitHub repo" → selecciona `rcorne/spidermapp`. Railway detecta el
   `pidge_server/Dockerfile` automáticamente si le indicas ese subdirectorio como raíz de build
   (Settings → Build → Root Directory: `pidge_server`, Dockerfile Path: `Dockerfile`).
3. En Variables del servicio, agrega al menos `PIDGE_JWT_SECRET` con un valor largo y aleatorio
   (no el de desarrollo) — es lo que firma las sesiones; si se filtra, cualquiera puede falsificar
   un login.
4. Agrega un Volume (Railway → tu servicio → Volumes) montado en `/data` para que la base SQLite
   (`~/.pidge_server/pidge.db` dentro del contenedor, controlado por `PIDGE_DATA_DIR=/data`, ya
   seteado en el Dockerfile) sobreviva a los redeploys. Para más de un puñado de usuarios
   conviene migrar a Postgres (Railway lo ofrece como addon con un clic) — avísame si llegan a
   ese punto y adapto `pidge_server/db.py`.
5. Railway te da una URL pública (`algo.up.railway.app`) con HTTPS automático. Puedes usarla tal
   cual, o darle un subdominio propio: en GoDaddy → DNS de tu dominio, agrega un registro CNAME
   (ej. `api` → el dominio que te da Railway) y en Railway agrega ese dominio custom al servicio.
6. En cada instalación de Pidge: Preferencias → Cuenta → Servidor Pidge → pega esa URL (con
   `https://`) → Guardar.

Render y Fly.io son alternativas equivalentes si prefieres explorarlas — mismo principio: un
servicio que corre contenedores Docker con procesos persistentes y WebSockets, no hosting
compartido de archivos.

Inicio de sesión con Google/GitHub/Apple sigue el mismo flujo OAuth PKCE descrito en
[`spidermapp/core/auth.py`](spidermapp/core/auth.py) — corre en la app de escritorio misma
(no en el servidor), así que no depende de dónde despliegues `pidge_server`; sigues necesitando
tus propias credenciales de cada proveedor (Preferencias → Cuenta), el mismo requisito que ya
aplicaba antes del chat.

## Tests

```bash
source .venv/bin/activate
pytest
```

## Checks incluidos en v1

Códigos de respuesta (404, soft-404, 5xx), title/meta/H1, canonicals, directivas noindex/nofollow,
enlaces internos/externos, contenido duplicado, redirects (301 vs 302, cadenas, loops, meta-refresh
y redirects por JS), convenciones de URL (mayúsculas, guion bajo, `//`, trailing slash), HTTPS
(certificado, redirect http→https), consistencia www/non-www, sitemap.xml y robots.txt,
detección de CMS/tecnología, renderizado (bot vs usuario, mobile vs desktop) y Core Web Vitals
en modo "lab" (Playwright, no CrUX real).

## Fuera de alcance en v1 (pendiente para v2)

Todo lo que depende de la API de Google Search Console (cobertura de índice, confirmación de
sitemap enviado, fuentes de tráfico) — requiere que se creen credenciales OAuth en Google Cloud
Console. Ver [`spidermapp/gsc/client.py`](spidermapp/gsc/client.py) para los pasos de setup y el
punto de extensión ya preparado.
