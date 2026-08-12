# Licencias de terceros

## LibreCrawl

Pidge 2.0 incorpora ideas y código adaptado de
[LibreCrawl](https://github.com/PhialsBasement/LibreCrawl), un crawler SEO
open source. Los módulos afectados llevan una nota en su encabezado:

| Archivo en Pidge | Qué se tomó de LibreCrawl |
|---|---|
| `spidermapp/core/rate_limiter.py` | El limitador de ritmo por intervalo mínimo, reescrito sobre asyncio (el original usa `threading.Lock` + `time.sleep`, que bloquearía el event loop). |
| `spidermapp/core/fetch_errors.py` | La clasificación de errores de red (DNS / timeout / conexión rechazada / TLS), adaptada de `requests`/`urllib3` a las excepciones de `httpx`. |
| `spidermapp/core/checkpoint.py` | La idea de guardar el estado de la cola para poder retomar un crawl interrumpido. LibreCrawl lo persiste en SQLite desde un hilo de fondo; Pidge escribe un JSON por sitio, al ser una app de escritorio con un crawl a la vez. |
| `spidermapp/core/crawler.py` | La detección de imágenes rotas y el concepto de pausa/reanudación del rastreo. |

El motor de rastreo en sí **no** se reemplazó: LibreCrawl usa `requests` con
`ThreadPoolExecutor` (un hilo por petición, síncrono), mientras que Pidge ya
usaba asyncio + httpx con HTTP/2 y reutilización de conexiones, que es más
eficiente para trabajo limitado por I/O como este.

Ambos proyectos son MIT, así que la reutilización es compatible. Texto de la
licencia original, incluido según lo exige la MIT:

```
MIT License

Copyright (c) 2025 Phiality

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
