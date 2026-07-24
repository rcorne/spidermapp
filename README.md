# Pidgeot

Auditor de SEO de escritorio, similar a Screaming Frog SEO Spider. Rastrea un sitio siguiendo
enlaces internos y audita cada URL contra una lista amplia de checks técnicos de SEO.

(El paquete de Python y el repositorio conservan el nombre interno `spidermapp` — solo el
branding de cara al usuario, el `.app`/`.dmg` empaquetados y el título de la ventana usan
"Pidgeot".)

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
`packaging/Pidgeot.dmg` (instalador). Para regenerarlos tras cambios en el código:

```bash
source .venv/bin/activate
pip install pyinstaller
rm -rf build dist
pyinstaller packaging/spidermapp.spec --noconfirm
```

Esto produce `dist/Pidgeot.app`. Para armar el `.dmg` (app + acceso directo a /Applications,
con ícono de volumen propio):

```bash
rm -rf packaging/dmg_staging packaging/Pidgeot.dmg
mkdir -p packaging/dmg_staging
cp -R dist/Pidgeot.app packaging/dmg_staging/
ln -s /Applications packaging/dmg_staging/Applications
cp packaging/icon/Spidermapp.icns packaging/dmg_staging/.VolumeIcon.icns
hdiutil create -srcfolder packaging/dmg_staging -volname "Pidgeot" -fs HFS+ -format UDRW -ov packaging/Pidgeot_rw.dmg
VOLUME=$(hdiutil attach packaging/Pidgeot_rw.dmg -readwrite -noverify -noautoopen | grep -Eo '/Volumes/.*')
SetFile -a C "$VOLUME"
hdiutil detach "$VOLUME"
hdiutil convert packaging/Pidgeot_rw.dmg -format UDZO -o packaging/Pidgeot.dmg -ov
rm -f packaging/Pidgeot_rw.dmg
```

Para instalar: abre el `.dmg` y arrastra `Pidgeot.app` al acceso directo de Applications, o
directamente `cp -R dist/Pidgeot.app /Applications/`.

**Nota sobre Playwright en la app empaquetada:** el binario de Chromium (~170 MB) no viaja dentro
del `.app` — Playwright lo busca en `~/Library/Caches/ms-playwright`, el mismo caché que usa
cualquier instalación de Playwright en esa Mac. Si Pidgeot se instala en una máquina donde
nunca se corrió `playwright install chromium`, el check de renderizado fallará hasta correr ese
comando una vez en esa Mac (con cualquier Python que tenga `playwright` instalado, no hace falta
el venv del proyecto).

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
