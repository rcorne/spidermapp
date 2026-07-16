from __future__ import annotations

from dataclasses import dataclass

from spidermapp.core.models import Issue


@dataclass
class Recommendation:
    title: str
    why: str
    fix_steps: list[str]


_RECOMMENDATIONS: dict[str, Recommendation] = {
    "blocked_by_robots": Recommendation(
        "Esta URL está bloqueada en robots.txt",
        "Se descubrió por un enlace, pero robots.txt le prohíbe a los bots rastrearla, así que no se analizó su contenido.",
        ["Revisa la regla Disallow correspondiente en robots.txt.", "Si debería ser rastreable, quita o ajusta esa regla."],
    ),
    "canonical_points_elsewhere": Recommendation(
        "Google podría no indexar esta página",
        "El canonical le dice a Google que la versión «real» es otra URL. Si esta página tiene tráfico propio, se lo está regalando a la otra.",
        ["Revisa si esta página debería indexarse por sí sola.", "Si sí, cambia el canonical para que apunte a sí misma.", "Si no, está bien así."],
    ),
    "duplicate_content": Recommendation(
        "Contenido idéntico a otra(s) URL(s)",
        "Google elige una sola versión para indexar y puede diluir la relevancia de todas entre sí.",
        ["Decide cuál URL es la versión canónica.", "Usa un canonical o un redirect 301 hacia ella desde las demás."],
    ),
    "duplicate_title": Recommendation(
        "Title repetido en otra(s) página(s)",
        "Un title duplicado le quita a Google una señal clave para diferenciar el contenido de cada página en resultados de búsqueda.",
        ["Escribe un title único que describa específicamente esta página."],
    ),
    "duplicate_meta_description": Recommendation(
        "Meta description repetida en otra(s) página(s)",
        "No bloquea la indexación, pero desaprovecha una oportunidad de diferenciar el snippet en resultados de búsqueda.",
        ["Escribe una meta description única para esta página."],
    ),
    "error_404": Recommendation(
        "Página no encontrada (404)",
        "Los visitantes y Google llegan a un callejón sin salida; si tenía enlaces o tráfico, ese valor se pierde.",
        ["Si la página se movió, agrega un redirect 301 a la URL correcta.", "Si ya no existe, quita los enlaces internos que apuntan aquí."],
    ),
    "error_4xx": Recommendation(
        "Error del cliente al pedir esta URL",
        "El servidor está rechazando la solicitud antes de mostrar contenido.",
        ["Revisa por qué el servidor devuelve este código.", "Corrige el enlace o la configuración del servidor."],
    ),
    "error_5xx": Recommendation(
        "Error del servidor al cargar esta URL",
        "El servidor falló al generar la respuesta; si persiste, Google puede empezar a desindexar la página.",
        ["Revisa los logs del servidor para esta ruta.", "Si es intermitente, confirma que no sea un problema de carga/timeout."],
    ),
    "fetch_error": Recommendation(
        "No se pudo conectar a esta URL",
        "Ni siquiera se obtuvo una respuesta HTTP — puede ser un problema de DNS, TLS o el servidor caído.",
        ["Verifica que la URL sea correcta y el servidor esté disponible.", "Vuelve a intentar el crawl más tarde para descartar un problema temporal."],
    ),
    "h1_missing": Recommendation(
        "Falta el encabezado H1",
        "El H1 ayuda a Google y a los usuarios a entender de qué trata la página de un vistazo.",
        ["Agrega un H1 que resuma el tema principal de la página."],
    ),
    "h2_missing": Recommendation(
        "La página no tiene encabezados H2",
        "Los H2 estructuran el contenido en secciones que Google usa para entender los subtemas de la página.",
        ["Si la página tiene suficiente contenido, organízalo en secciones con H2 descriptivos."],
    ),
    "img_alt_missing": Recommendation(
        "Imágenes sin atributo alt",
        "El alt describe la imagen para Google Imágenes y para lectores de pantalla — sin él pierdes tráfico de imágenes y accesibilidad.",
        ["Agrega un alt descriptivo a cada imagen con contenido.", "Para imágenes decorativas, usa alt=\"\" (vacío) explícito."],
    ),
    "empty_anchors": Recommendation(
        "Etiquetas <a> vacías",
        "Enlaces sin href o sin texto/imagen no transmiten señal a Google y confunden a lectores de pantalla.",
        ["Elimina las etiquetas <a> vacías o dales un href y texto ancla descriptivo."],
    ),
    "not_in_sitemap": Recommendation(
        "Página indexable ausente del sitemap",
        "El sitemap debería listar todas las páginas que quieres que Google indexe — esta no aparece.",
        ["Agrega esta URL al sitemap.xml si debe indexarse."],
    ),
    "spa_render_unavailable": Recommendation(
        "El sitio requiere JavaScript pero el navegador de renderizado no está disponible",
        "El HTML inicial no contiene enlaces (aplicación JavaScript) y no se pudo iniciar Chromium para leer el DOM renderizado, así que el crawl no puede continuar más allá de esta página.",
        ["Ejecuta 'playwright install chromium' una vez en esta Mac.", "Vuelve a correr el crawl."],
    ),
    "render_browser_unavailable": Recommendation(
        "No se pudo iniciar el navegador de renderizado",
        "Activaste 'Renderizar JS' pero Chromium no pudo iniciarse, así que el crawl siguió sin comparar HTML renderizado ni mobile vs desktop.",
        ["Ejecuta 'playwright install chromium' en una terminal.", "Vuelve a correr el crawl con 'Renderizar JS' activado."],
    ),
    "h1_multiple": Recommendation(
        "Hay más de un H1 en la página",
        "Múltiples H1 diluyen la señal de cuál es el tema principal de la página.",
        ["Deja un solo H1 y baja los demás a H2 o inferior."],
    ),
    "http_check_failed": Recommendation(
        "No se pudo verificar el redirect HTTP→HTTPS",
        "No se logró confirmar si la versión sin cifrar del sitio redirige correctamente.",
        ["Prueba manualmente abrir la versión http:// del sitio y revisa a dónde te lleva."],
    ),
    "http_not_redirected_to_https": Recommendation(
        "La versión HTTP no redirige a HTTPS",
        "Cualquiera puede acceder al sitio sin cifrado, y Google penaliza sitios sin HTTPS forzado.",
        ["Configura un redirect 301 permanente de todo el tráfico HTTP a HTTPS."],
    ),
    "http_to_https_not_permanent": Recommendation(
        "El redirect a HTTPS no es permanente",
        "Un redirect temporal (302/307) no transfiere el valor SEO de forma tan clara como uno permanente.",
        ["Cambia el redirect de HTTP a HTTPS a un código 301 o 308."],
    ),
    "https_no_redirect_detected": Recommendation(
        "No se detectó redirect de HTTP a HTTPS",
        "La versión HTTP responde sin redirigir explícitamente, lo cual puede dejar ambas versiones activas.",
        ["Confirma en el servidor que exista una regla explícita de redirect a HTTPS."],
    ),
    "js_redirect": Recommendation(
        "Redirect implementado con JavaScript",
        "Los bots que no ejecutan JS pueden no seguir este redirect, y pierde parte del valor SEO de un 301 HTTP.",
        ["Reemplázalo por un redirect 301 a nivel de servidor."],
    ),
    "meta_description_missing": Recommendation(
        "Falta la meta description",
        "Sin ella, Google genera un snippet automático que muchas veces es menos efectivo para atraer clics.",
        ["Escribe una meta description de 50–160 caracteres que resuma la página."],
    ),
    "meta_description_too_long": Recommendation(
        "Meta description demasiado larga",
        "Google la recorta en los resultados de búsqueda, cortando el mensaje a mitad de frase.",
        ["Recórtala a 160 caracteres o menos, priorizando la idea principal al inicio."],
    ),
    "meta_description_too_short": Recommendation(
        "Meta description demasiado corta",
        "Desaprovecha el espacio disponible en el snippet de resultados para convencer al usuario de hacer clic.",
        ["Amplíala a al menos 50 caracteres con una descripción más completa."],
    ),
    "meta_refresh_redirect": Recommendation(
        "Redirect implementado con meta-refresh",
        "Es más lento y menos confiable para SEO que un redirect HTTP, y algunos bots no lo siguen.",
        ["Reemplázalo por un redirect 301 a nivel de servidor."],
    ),
    "mixed_scheme": Recommendation(
        "El sitio responde en HTTP y HTTPS sin unificar",
        "Google puede indexar ambas versiones como páginas distintas, diluyendo autoridad y generando contenido duplicado.",
        ["Fuerza un redirect 301 de HTTP a HTTPS en todo el sitio."],
    ),
    "mixed_trailing_slash": Recommendation(
        "URLs con y sin barra final conviven en el sitio",
        "Cada variante puede indexarse como una URL distinta, dividiendo señales de relevancia.",
        ["Elige una convención (con o sin /) y redirige la otra versión con 301."],
    ),
    "mixed_www": Recommendation(
        "El sitio responde en www y sin www a la vez",
        "Son dos versiones del mismo sitio compitiendo por indexación en vez de sumar autoridad a una sola.",
        ["Elige una versión (www o sin www) y redirige la otra con 301."],
    ),
    "mobile_desktop_mismatch": Recommendation(
        "El contenido difiere entre mobile y desktop",
        "Google indexa principalmente la versión mobile; si le falta contenido que sí tiene desktop, ese contenido no cuenta para el ranking.",
        ["Confirma que la versión mobile muestre el mismo contenido e enlaces que desktop."],
    ),
    "nofollow_page": Recommendation(
        "La página tiene nofollow a nivel de página",
        "Los enlaces salientes de esta página no transmiten autoridad, lo cual puede ser intencional o un descuido.",
        ["Confirma que sea intencional; si no, quita la directiva nofollow."],
    ),
    "noindex": Recommendation(
        "Esta página tiene la directiva noindex",
        "Google no la incluirá en resultados de búsqueda aunque la rastree.",
        ["Si debería ser indexable, quita la etiqueta noindex.", "Si es intencional (ej. página de checkout), no hace falta hacer nada."],
    ),
    "orphan_page": Recommendation(
        "Página huérfana: sin enlaces internos",
        "Está en el sitemap pero ningún otro lugar del sitio enlaza hacia ella, así que Google le asigna menos importancia y a los usuarios les cuesta encontrarla navegando.",
        ["Enlázala desde alguna página relevante del sitio (categoría, menú, contenido relacionado)."],
    ),
    "priority_url_not_indexable": Recommendation(
        "URL marcada como importante, pero no es indexable",
        "Está bloqueada por noindex, canonical hacia otra URL, o no responde 200 — y la marcaste como prioritaria.",
        ["Revisa esta URL primero: es de las páginas donde un problema de indexación duele más."],
    ),
    "redirect_chain_too_long": Recommendation(
        "Cadena de redirects demasiado larga",
        "Cada salto adicional demora la carga y diluye ligeramente el valor SEO que se transmite al destino final.",
        ["Actualiza el enlace o la regla de redirect para que apunte directo al destino final."],
    ),
    "redirect_loop": Recommendation(
        "Bucle de redirects detectado",
        "La URL nunca resuelve a una página real — navegadores y bots eventualmente abandonan el intento.",
        ["Revisa la cadena de redirects y corrige la regla que causa el ciclo."],
    ),
    "render_description_mismatch": Recommendation(
        "La meta description cambia al ejecutar JavaScript",
        "Si el bot no ejecuta JS (o lo hace con retraso), podría indexar una descripción distinta a la que ven los usuarios.",
        ["Verifica que la meta description esté presente en el HTML inicial, no solo tras renderizar."],
    ),
    "render_failed": Recommendation(
        "No se pudo renderizar esta página con un navegador",
        "No se pudo confirmar qué ve realmente un usuario (o un bot que ejecuta JS) en esta página.",
        ["Abre la URL manualmente en un navegador para descartar errores de carga."],
    ),
    "render_h1_mismatch": Recommendation(
        "El H1 cambia al ejecutar JavaScript",
        "El H1 del HTML inicial no coincide con el que arma el navegador — riesgo de que un bot vea uno distinto al del usuario.",
        ["Verifica que el H1 correcto esté presente sin depender de JavaScript."],
    ),
    "render_title_mismatch": Recommendation(
        "El title cambia al ejecutar JavaScript",
        "El title del HTML inicial no coincide con el renderizado — Google podría indexar el título equivocado.",
        ["Verifica que el <title> correcto esté en el HTML inicial, no inyectado después por JS."],
    ),
    "robots_blocks_everything": Recommendation(
        "robots.txt bloquea todo el sitio",
        "Ningún bot puede rastrear ninguna página — el sitio completo queda fuera de los resultados de búsqueda.",
        ["Revisa la regla Disallow: / en robots.txt — probablemente sea un error de configuración."],
    ),
    "robots_missing": Recommendation(
        "No se encontró robots.txt",
        "No es un error crítico (se asume todo permitido), pero pierdes control explícito sobre qué debe rastrearse.",
        ["Considera agregar un robots.txt, aunque sea mínimo, con la referencia al sitemap."],
    ),
    "robots_no_sitemap_directive": Recommendation(
        "robots.txt no declara el sitemap",
        "Es una forma estándar y simple de ayudar a los motores de búsqueda a encontrar tu sitemap.",
        ["Agrega una línea Sitemap: https://tu-sitio.com/sitemap.xml en robots.txt."],
    ),
    "sitemap_broken_urls": Recommendation(
        "El sitemap incluye URLs rotas",
        "Le estás pidiendo a Google que indexe URLs que ni siquiera cargan — desperdicia presupuesto de rastreo.",
        ["Quita del sitemap las URLs que devuelven error 4xx/5xx."],
    ),
    "sitemap_empty": Recommendation(
        "El sitemap no tiene URLs",
        "Google usa el sitemap como ayuda para descubrir e indexar contenido; vacío, no aporta nada.",
        ["Genera un sitemap con las URLs importantes del sitio."],
    ),
    "sitemap_missing_crawled_urls": Recommendation(
        "Hay páginas rastreadas que no están en el sitemap",
        "El sitemap no refleja el sitio completo, lo que puede ralentizar el descubrimiento de contenido nuevo.",
        ["Actualiza el sitemap para incluir estas URLs, si deberían ser indexables."],
    ),
    "sitemap_off_domain_urls": Recommendation(
        "El sitemap incluye URLs de otro dominio",
        "Puede confundir a los motores de búsqueda sobre qué contenido pertenece realmente a tu sitio.",
        ["Revisa por qué aparecen URLs externas y quítalas si no corresponden."],
    ),
    "soft_404": Recommendation(
        "Página de error disfrazada de 200 (soft 404)",
        "Google trata este patrón como señal de baja calidad y puede dejar de rastrear páginas similares con el tiempo.",
        ["Haz que esta URL devuelva un código 404 (o 410) real en vez de 200."],
    ),
    "temporary_redirect_should_be_permanent": Recommendation(
        "Redirect temporal (302) para un movimiento permanente",
        "Un 302 le dice a Google que no transfiera el valor SEO de forma definitiva a la nueva URL.",
        ["Si el movimiento es definitivo, cambia el código a 301."],
    ),
    "thin_content": Recommendation(
        "Contenido posiblemente escaso",
        "Páginas con muy poco texto suelen rankear peor porque le dan a Google poca señal sobre el tema.",
        ["Evalúa si vale la pena ampliar el contenido o si la página debería ser noindex."],
    ),
    "title_missing": Recommendation(
        "Falta la etiqueta <title>",
        "El title es uno de los factores on-page más importantes para SEO y es lo primero que se ve en resultados de búsqueda.",
        ["Agrega un <title> único y descriptivo para esta página."],
    ),
    "title_too_long": Recommendation(
        "Title demasiado largo",
        "Google lo recorta en los resultados de búsqueda, ocultando parte del mensaje.",
        ["Acórtalo a 60 caracteres o menos, priorizando las palabras clave al inicio."],
    ),
    "title_too_short": Recommendation(
        "Title demasiado corto",
        "Desaprovecha espacio para comunicar de qué trata la página y atraer clics.",
        ["Amplíalo a al menos 15 caracteres con una descripción más específica."],
    ),
    "tls_expired": Recommendation(
        "El certificado HTTPS ya expiró",
        "Los navegadores muestran una advertencia de seguridad a los visitantes, y muchos abandonarán el sitio.",
        ["Renueva el certificado TLS lo antes posible."],
    ),
    "tls_expiring_soon": Recommendation(
        "El certificado HTTPS expira pronto",
        "Si expira sin renovarse, el sitio empezará a mostrar advertencias de seguridad a los visitantes.",
        ["Programa la renovación del certificado antes de la fecha de expiración."],
    ),
    "tls_invalid": Recommendation(
        "Certificado HTTPS inválido o inalcanzable",
        "Los navegadores bloquean o advierten fuertemente antes de mostrar el sitio, afectando tráfico y confianza.",
        ["Revisa la configuración TLS del servidor y que el certificado sea válido para este dominio."],
    ),
    "url_multi_slash": Recommendation(
        "La URL tiene barras (/) duplicadas",
        "Puede generar URLs duplicadas funcionalmente distintas para Google, dividiendo señales de relevancia.",
        ["Normaliza la URL para eliminar las barras repetidas."],
    ),
    "url_numeric_or_special": Recommendation(
        "La URL tiene números o caracteres especiales",
        "No es un error grave, pero URLs más limpias suelen ser más legibles para usuarios y buscadores.",
        ["Si es viable, usa una versión de la URL basada en palabras en vez de IDs o parámetros."],
    ),
    "url_underscore": Recommendation(
        "La URL usa guion bajo en vez de guion medio",
        "Google trata el guion medio (-) como separador de palabras; el guion bajo (_) no siempre se interpreta igual.",
        ["Si es posible, usa guiones medios en vez de guiones bajos en la URL."],
    ),
    "url_uppercase": Recommendation(
        "La URL contiene mayúsculas",
        "Las URLs son sensibles a mayúsculas/minúsculas — la misma página con distinta capitalización puede indexarse como duplicada.",
        ["Usa siempre minúsculas y redirige las variantes con mayúsculas."],
    ),
}


_DEFAULT_FIX = ["Revisa este hallazgo y decide si aplica una corrección."]


def get_recommendation(issue: Issue) -> Recommendation:
    return _RECOMMENDATIONS.get(
        issue.code,
        Recommendation(title=issue.message, why="", fix_steps=list(_DEFAULT_FIX)),
    )
