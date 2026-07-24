# Pidge

Auditor de SEO de escritorio, similar a Screaming Frog SEO Spider. Rastrea un sitio siguiendo
enlaces internos y audita cada URL contra una lista amplia de checks técnicos de SEO.

(El paquete de Python y el repositorio conservan el nombre interno `spidermapp` — solo el
branding de cara al usuario, el `.app`/`.dmg` empaquetados y el título de la ventana usan
"Pidge".)

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
`pidge_server/` en algún lugar accesible por todos — un VPS propio, o un servicio como Railway,
Render o Fly.io — y apuntar el campo "Servidor" de cada instalación de Pidge a esa URL. Esa parte
requiere que tú mismo crees la cuenta de hosting (no puedo crearla ni pagarla en tu nombre); incluye
[`pidge_server/Dockerfile`](pidge_server/Dockerfile) para facilitarlo. Configura al menos
`PIDGE_JWT_SECRET` (un secreto real, no el valor de desarrollo) vía variables de entorno en producción.

Inicio de sesión con Google/GitHub/Apple sigue el mismo flujo OAuth PKCE descrito en
[`spidermapp/core/auth.py`](spidermapp/core/auth.py) — necesitas tus propias credenciales de cada
proveedor (Preferencias → Cuenta), el mismo requisito que ya aplicaba antes del chat.

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
