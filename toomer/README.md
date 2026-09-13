# Toomer

Caja de herramientas de escritorio, **en español**, para análisis de ecommerce, marketing y SEO.
Disponible como app de macOS (`Toomer.app` / `Toomer.dmg`) y como instalador de Windows
(`Toomer-Setup-1.0.0.exe`).

Es una adaptación con interfaz gráfica de [EcommerceTools](https://github.com/practical-data-science/ecommercetools)
de Matt Clarke (MIT): las mismas técnicas, sin escribir Python ni abrir un notebook.

## Qué hace

Todo parte de un archivo de **líneas de pedido** (una fila por producto dentro de cada pedido) en CSV o Excel.
Al abrirlo, Toomer detecta las columnas (`order_id`, `sku`, `quantity`, `order_date`, `unit_price`,
`customer_id`… en inglés o español) y te deja corregir el mapeo. También puedes descargar el dataset de
ejemplo *Online Retail* o generar datos sintéticos para probar.

| Sección | Herramientas |
|---|---|
| **Transacciones** | Una fila por pedido: SKUs, unidades, ingresos, número de pedido del cliente. |
| **Productos** | Métricas por SKU · tasas de recompra y de compra por volumen. |
| **Clientes** | Agregado por cliente · segmentación **RFM(H)** con K-means · clases **ABC** · **cohortes** y retención · **latencia** de compra · **predicciones** de compras, ticket y CLV (**BG/NBD + Gamma-Gamma**). |
| **Operaciones** | Clasificación ABC de inventario. |
| **Informes** | Informes por día/semana/mes/trimestre/año de transacciones y de clientes (nuevos vs recurrentes). |
| **Publicidad** | Generador de keywords (4 concordancias de Google Ads) · expansión de textos Spintax. |
| **Marketing** | Calendario comercial (Reyes, San Valentín, Día de la Madre/Padre, Black Friday, Cyber Monday, Navidad, días de pago…). |
| **SEO** | robots.txt y sitemaps · análisis de metadatos de páginas · Google Autocomplete · Core Web Vitals (PageSpeed) · Knowledge Graph · páginas indexadas y SERPs · Search Console (consulta, comparación de períodos, ABCD de páginas). |
| **Texto** | Resúmenes extractivos de texto o de una columna de un CSV. |
| **Métricas** | Calculadora con ~45 fórmulas de retail, marketing, inventario y atención al cliente. |

Toda tabla se puede filtrar, ordenar y exportar a CSV o Excel.

### Diferencias con EcommerceTools

- **Predicciones (CLV):** los modelos BG/NBD y Gamma-Gamma están reimplementados con SciPy en vez de usar
  `lifetimes` (sin mantenimiento; rompe con pandas 2). Los tests comprueban que recuperan los parámetros
  de datos simulados.
- **RFM:** K-means unidimensional propio en lugar de scikit-learn (mismo resultado, sin la dependencia).
- **Resúmenes de texto:** extractivos por frecuencia de términos, en vez de un transformer con `torch`
  (varios GB que no tienen sentido en una app de escritorio). Funcionan sin conexión y en español.
- **Calendario comercial:** adaptado al calendario hispanoamericano en lugar del británico.
- **Tests SEO con CausalImpact** (`seo.seo_test`) y **Google Analytics UA** (`gapandas`): no incluidos.
  La API de Universal Analytics ya no existe, y CausalImpact arrastra TensorFlow.
- Los nombres de columnas de salida están en español (`id_cliente`, `ingresos`, `ticket_medio`…).

## Desarrollo

```bash
cd toomer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
python -m toomer.main
pytest -q
```

## Empaquetar

**macOS** (desde un Mac):

```bash
pip install pyinstaller
pyinstaller packaging/toomer.spec --noconfirm       # → dist/Toomer.app
```

Para el `.dmg`, ver el paso *Package .dmg* de [`build-toomer.yml`](../.github/workflows/build-toomer.yml).

**Windows:** PyInstaller no compila cruzado, así que el `.exe` y el instalador Inno Setup
([`packaging/windows/toomer.iss`](packaging/windows/toomer.iss)) los construye GitHub Actions en un runner
`windows-latest` con cada push que toque `toomer/`. Descarga **Toomer-windows-installer**,
**Toomer-windows-portable** o **Toomer-macos** desde la pestaña *Actions*. Un tag `toomer-v1.0.0`
publica los tres archivos en un release.

Windows mostrará el aviso de SmartScreen la primera vez (instalador sin firma digital): *Más información →
Ejecutar de todas formas*.

## Ícono

`packaging/icon/toomer_icon.svg` es la fuente. `python packaging/icon/render_iconset.py` regenera el PNG de la
app, el `.ico` de Windows y el iconset; `iconutil -c icns packaging/icon/Toomer.iconset` produce el `.icns`.

## Licencia

MIT. Código derivado de EcommerceTools © Matt Clarke, MIT.
