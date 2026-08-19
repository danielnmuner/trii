from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    formula: str
    variables: str
    practical_definition: str
    how_to_use: str
    decision_support: str


@dataclass(frozen=True)
class GlossarySection:
    title: str
    summary: str
    entries: tuple[GlossaryEntry, ...]


GLOSSARY_SECTIONS: tuple[GlossarySection, ...] = (
    GlossarySection(
        title="Profundidad visible del libro",
        summary=(
            "Estas referencias permiten leer la liquidez inmediata que realmente tienes disponible delante del mercado. "
            "Sirven para estimar si una orden puede entrar o salir con poco deslizamiento y para detectar donde esta "
            "concentrado el volumen visible en los cinco niveles del libro."
        ),
        entries=(
            GlossaryEntry(
                term="Lineas de profundidad",
                formula=r"$bid\_levels_{1:5}$ y $ask\_levels_{1:5}$",
                variables=(
                    "`bid_levels` = niveles compradores visibles.  \n"
                    "`ask_levels` = niveles vendedores visibles.  \n"
                    "`price_i` = precio del nivel `i`.  \n"
                    "`quantity_i` = cantidad disponible en el nivel `i`."
                ),
                practical_definition=(
                    "Muestran los primeros escalones reales del libro de ordenes, con precio y cantidad disponible a cada lado del mercado."
                ),
                how_to_use=(
                    "Revisalas para detectar si la liquidez esta concentrada, si hay paredes de compra o venta, y si el mercado puede absorber tu orden sin moverse demasiado."
                ),
                decision_support=(
                    "Permiten decidir tamano de orden, agresividad de entrada y si conviene usar precio limite para reducir deslizamiento."
                ),
            ),
            GlossaryEntry(
                term="Bid depth total top 5",
                formula=r"$bid\_depth\_total\_5 = \sum_{i=1}^{5} bid\_quantity_i$",
                variables=(
                    "`bid_quantity_i` = cantidad visible en el nivel comprador `i`.  \n"
                    "La suma usa solo los 5 primeros niveles del lado comprador."
                ),
                practical_definition=(
                    "Resume el peso comprador visible en el libro usando solo los cinco primeros niveles, que son los que normalmente importan en ejecucion tactica."
                ),
                how_to_use=(
                    "Mira si el volumen comprador visible crece o se vacia entre snapshots. Cuando este bloque aumenta mientras el precio resiste, suele haber mejor soporte inmediato."
                ),
                decision_support=(
                    "Ayuda a decidir si hay base suficiente para entrar comprando sin perseguir precio o si el soporte visible todavia es fragil."
                ),
            ),
            GlossaryEntry(
                term="Ask depth total top 5",
                formula=r"$ask\_depth\_total\_5 = \sum_{i=1}^{5} ask\_quantity_i$",
                variables=(
                    "`ask_quantity_i` = cantidad visible en el nivel vendedor `i`.  \n"
                    "La suma usa solo los 5 primeros niveles del lado vendedor."
                ),
                practical_definition=(
                    "Resume el peso vendedor visible en el libro y muestra cuanta oferta inmediata tendria que absorber el mercado para seguir subiendo."
                ),
                how_to_use=(
                    "Comparalo contra `bid_depth_total_5` para ver si la oferta domina claramente. Si este bloque crece mas rapido, la subida puede agotarse o necesitar mas tiempo."
                ),
                decision_support=(
                    "Sirve para decidir si conviene esperar confirmacion antes de comprar o si una salida rapida puede encontrar suficiente liquidez enfrente."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Referencias de precio y ejecucion",
        summary=(
            "Estas metricas describen el costo inmediato de cruce y el centro teorico del libro. Son la base para decidir "
            "si vale la pena ejecutar ya, si la friccion esta muy alta o si el precio visible todavia ofrece una entrada eficiente."
        ),
        entries=(
            GlossaryEntry(
                term="Mejor compra y mejor venta",
                formula=r"$best\_bid\_price,\ best\_bid\_quantity,\ best\_ask\_price,\ best\_ask\_quantity$",
                variables=(
                    "`best_bid_price` = mejor precio comprador.  \n"
                    "`best_bid_quantity` = cantidad visible en la mejor compra.  \n"
                    "`best_ask_price` = mejor precio vendedor.  \n"
                    "`best_ask_quantity` = cantidad visible en la mejor venta."
                ),
                practical_definition=(
                    "Son el bid y el ask vigentes: el precio mas alto que alguien ofrece pagar y el mas bajo al que alguien acepta vender."
                ),
                how_to_use=(
                    "Comparalos para medir el spread y evaluar si la ejecucion inmediata seria eficiente o cara frente al precio de referencia."
                ),
                decision_support=(
                    "Sirven para fijar un precio limite inicial y decidir si vale la pena esperar mejor cruce antes de enviar la orden."
                ),
            ),
            GlossaryEntry(
                term="Spread absoluto",
                formula=r"$spread = best\_ask\_price - best\_bid\_price$",
                variables=(
                    "`best_ask_price` = mejor precio vendedor.  \n"
                    "`best_bid_price` = mejor precio comprador."
                ),
                practical_definition=(
                    "Es la friccion inmediata del mercado medida en pesos. Cuanto mas grande sea, mas caro es cruzar de una punta a la otra."
                ),
                how_to_use=(
                    "Leelo como costo minimo de ejecucion inmediata. Un spread amplio suele indicar menor eficiencia, mas riesgo de slippage y menor urgencia para entrar a mercado."
                ),
                decision_support=(
                    "Te ayuda a decidir si ejecutas ya, si reduces tamano o si esperas a que el libro se cierre antes de comprar o vender."
                ),
            ),
            GlossaryEntry(
                term="Spread bps",
                formula=r"$spread\_bps = \left(\frac{spread}{mid\_price}\right)\times 10000$",
                variables=(
                    "`spread` = distancia entre mejor venta y mejor compra.  \n"
                    "`mid_price` = punto medio entre ambas puntas.  \n"
                    "`10000` convierte la proporcion a puntos basicos."
                ),
                practical_definition=(
                    "Es el spread expresado en puntos basicos, por lo que permite comparar friccion entre acciones de precios muy distintos."
                ),
                how_to_use=(
                    "Usalo cuando quieras rankear especies por costo relativo de ejecucion. Dos acciones pueden tener spreads en pesos muy distintos, pero el spread bps muestra cual es mas eficiente proporcionalmente."
                ),
                decision_support=(
                    "Permite priorizar especies mas negociables, detectar deterioro de liquidez y evitar entradas donde el costo relativo ya es demasiado alto."
                ),
            ),
            GlossaryEntry(
                term="Mid price",
                formula=r"$mid\_price = \frac{best\_bid\_price + best\_ask\_price}{2}$",
                variables=(
                    "`best_bid_price` = mejor precio comprador.  \n"
                    "`best_ask_price` = mejor precio vendedor."
                ),
                practical_definition=(
                    "Es el centro teorico del libro. No implica que realmente puedas ejecutar alli, pero sirve como precio de referencia neutral."
                ),
                how_to_use=(
                    "Comparalo con `last_price`, `microprice` y `spread_bps` para saber si el precio operado esta razonablemente centrado o ya muy sesgado hacia un lado."
                ),
                decision_support=(
                    "Ayuda a poner en contexto el punto medio real del mercado antes de decidir un limite de entrada o salida."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Presion inmediata en la punta",
        summary=(
            "Este bloque sirve para leer quien manda en el nivel uno y si la presion visible favorece una continuidad al alza o a la baja. "
            "Es especialmente util cuando necesitas decidir rapido si la siguiente agresion tiene mas probabilidad de barrer el ask o el bid."
        ),
        entries=(
            GlossaryEntry(
                term="Microprice",
                formula=(
                    r"$microprice = \frac{(best\_ask\_price \times best\_bid\_quantity) + "
                    r"(best\_bid\_price \times best\_ask\_quantity)}{best\_bid\_quantity + best\_ask\_quantity}$"
                ),
                variables=(
                    "`best_ask_price` = mejor precio vendedor.  \n"
                    "`best_bid_price` = mejor precio comprador.  \n"
                    "`best_bid_quantity` = cantidad visible en la mejor compra.  \n"
                    "`best_ask_quantity` = cantidad visible en la mejor venta."
                ),
                practical_definition=(
                    "Es un precio teorico mas sensible que el mid price porque pondera el centro del libro segun la fuerza relativa de las cantidades en la mejor punta."
                ),
                how_to_use=(
                    "Si el microprice se acerca al ask, la presion compradora inmediata suele ser mayor; si se acerca al bid, la presion vendedora suele dominar."
                ),
                decision_support=(
                    "Sirve para decidir si conviene tomar liquidez rapido o esperar, especialmente cuando el mid price por si solo no revela suficiente sesgo."
                ),
            ),
            GlossaryEntry(
                term="OBI L1",
                formula=(
                    r"$OBI_{L1} = \frac{best\_bid\_quantity - best\_ask\_quantity}"
                    r"{best\_bid\_quantity + best\_ask\_quantity}$"
                ),
                variables=(
                    "`best_bid_quantity` = volumen en la mejor compra.  \n"
                    "`best_ask_quantity` = volumen en la mejor venta."
                ),
                practical_definition=(
                    "Mide el imbalance de la punta del libro en una escala de -1 a 1. Positivo implica mas peso comprador; negativo, mas peso vendedor."
                ),
                how_to_use=(
                    "Usalo como lectura tactica de muy corto plazo. Un `obi_l1` muy negativo con spread abierto suele advertir que la oferta inmediata sigue mandando."
                ),
                decision_support=(
                    "Apoya decisiones de timing: entrar, esperar o incluso evitar una ejecucion agresiva cuando la punta va claramente en contra."
                ),
            ),
            GlossaryEntry(
                term="Depth-weighted microprice deviation",
                formula=r"$depth\_weighted\_microprice\_deviation = microprice - mid\_price$",
                variables=(
                    "`microprice` = centro ponderado por cantidades de la punta.  \n"
                    "`mid_price` = centro simple entre mejor compra y mejor venta."
                ),
                practical_definition=(
                    "Muestra cuanto se desplaza el centro ponderado frente al centro simple. Si es positivo, la presion suele empujar hacia arriba; si es negativo, hacia abajo."
                ),
                how_to_use=(
                    "Leelo como un sesgo corto y accionable. No importa solo el signo: cuanto mas se aleja de cero, mas fuerte suele ser la inclinacion inmediata del libro."
                ),
                decision_support=(
                    "Ayuda a validar si el sesgo de la punta realmente acompana una entrada o si la microestructura todavia te empuja en sentido contrario."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Presion agregada top 5",
        summary=(
            "Estas metricas suavizan el ruido del nivel uno y ayudan a leer la presion visible en los cinco niveles del libro. "
            "Son mas utiles para dashboards operativos, comparaciones entre especies y seguimiento de cambios de sesgo entre snapshots."
        ),
        entries=(
            GlossaryEntry(
                term="OBI top 5",
                formula=(
                    r"$OBI_{top5} = \frac{bid\_depth\_total\_5 - ask\_depth\_total\_5}"
                    r"{bid\_depth\_total\_5 + ask\_depth\_total\_5}$"
                ),
                variables=(
                    "`bid_depth_total_5` = suma de cantidades compradoras visibles entre los niveles 1 y 5.  \n"
                    "`ask_depth_total_5` = suma de cantidades vendedoras visibles entre los niveles 1 y 5."
                ),
                practical_definition=(
                    "Es una version mas estable del imbalance del libro porque ya no depende solo del nivel uno, sino del peso conjunto de los cinco niveles visibles."
                ),
                how_to_use=(
                    "Observa su evolucion en serie. Si `obi_l1` y `obi_top_5` apuntan en la misma direccion, el sesgo visible suele ser mas confiable."
                ),
                decision_support=(
                    "Sirve para validar si una lectura puntual de la punta tiene soporte mas profundo o si solo es ruido del primer escalon."
                ),
            ),
            GlossaryEntry(
                term="Book pressure ratio",
                formula=r"$book\_pressure\_ratio = \frac{bid\_depth\_total\_5}{ask\_depth\_total\_5}$",
                variables=(
                    "`bid_depth_total_5` = peso comprador visible.  \n"
                    "`ask_depth_total_5` = peso vendedor visible."
                ),
                practical_definition=(
                    "Es una relacion muy intuitiva para tablero: mayor a 1 implica mas profundidad compradora visible; menor a 1, mas profundidad vendedora."
                ),
                how_to_use=(
                    "Usalo para comparar especies o snapshots rapidamente. Es muy util cuando quieres una lectura simple de quien domina el libro sin entrar a formulas mas densas."
                ),
                decision_support=(
                    "Ayuda a decidir prioridad operativa: donde vale la pena mirar primero, donde la liquidez acompana una idea y donde la oferta todavia pesa demasiado."
                ),
            ),
            GlossaryEntry(
                term="Lectura conjunta recomendada",
                formula=r"$OBI_{L1} + OBI_{top5} + book\_pressure\_ratio + spread\_bps$",
                variables=(
                    "`OBI_L1` = sesgo inmediato de la punta.  \n"
                    "`OBI_top5` = sesgo agregado en los primeros 5 niveles.  \n"
                    "`book_pressure_ratio` = relacion entre profundidad compradora y vendedora.  \n"
                    "`spread_bps` = costo relativo de cruce."
                ),
                practical_definition=(
                    "La mejor lectura operativa no sale de una sola metrica. Conviene combinar sesgo inmediato, sesgo agregado y costo de cruce para evitar decisiones incompletas."
                ),
                how_to_use=(
                    "Busca alineacion: sesgo comprador en `obi_l1`, confirmacion en `obi_top_5`, ratio mayor a 1 y `spread_bps` controlado. Si uno de esos elementos falla, la senal es menos limpia."
                ),
                decision_support=(
                    "Permite decidir si el libro esta realmente favorable para ejecutar, si solo hay apariencia de soporte o si el costo de entrada invalida la idea."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Contexto minimo de sesion",
        summary=(
            "Estas metricas ubican el precio actual dentro del contexto minimo de la jornada para interpretar fuerza, debilidad y calidad del movimiento."
        ),
        entries=(
            GlossaryEntry(
                term="Cierre anterior, maximo y minimo",
                formula=r"$previous\_close,\ high\_price,\ low\_price$",
                variables=(
                    "`previous_close` = ultimo cierre valido.  \n"
                    "`high_price` = maximo del dia.  \n"
                    "`low_price` = minimo del dia."
                ),
                practical_definition=(
                    "Son referencias base de la sesion para ubicar el precio actual dentro de su rango reciente y frente al ultimo cierre valido."
                ),
                how_to_use=(
                    "Contrasta el precio actual con estos niveles para identificar fuerza relativa, debilidad o compresion intradia."
                ),
                decision_support=(
                    "Sirven para estimar riesgo intradia y validar si el activo esta rompiendo rango o solo oscilando sin conviccion."
                ),
            ),
            GlossaryEntry(
                term="Volumen y valor volumen",
                formula=r"$traded\_volume,\ traded\_value$",
                variables=(
                    "`traded_volume` = titulos negociados durante la sesion.  \n"
                    "`traded_value` = capital negociado en COP."
                ),
                practical_definition=(
                    "Reflejan cuantos titulos se han negociado y cuanto capital real ha pasado por el mercado durante la jornada."
                ),
                how_to_use=(
                    "Usalos para diferenciar movimientos respaldados por participacion real del mercado frente a cambios de precio con poca confirmacion."
                ),
                decision_support=(
                    "Ayudan a decidir si un movimiento tiene respaldo suficiente para ejecutarse o si conviene esperar mas liquidez."
                ),
            ),
            GlossaryEntry(
                term="Cambio diario",
                formula=r"$daily\_change\_amount,\ daily\_change\_percent,\ daily\_change\_direction$",
                variables=(
                    "`daily_change_amount` = cambio en pesos frente a la referencia previa.  \n"
                    "`daily_change_percent` = cambio porcentual del dia.  \n"
                    "`daily_change_direction` = direccion general del sesgo del dia."
                ),
                practical_definition=(
                    "Resume cuanto ha subido o bajado el activo frente a su referencia previa, tanto en dinero como en porcentaje."
                ),
                how_to_use=(
                    "Leelo junto con cierre anterior, maximo, minimo y profundidad para separar un cambio saludable de un movimiento sin soporte real."
                ),
                decision_support=(
                    "Permite decidir si el mercado acompana el sesgo del dia o si el precio ya se encuentra demasiado exigido para entrar de inmediato."
                ),
            ),
        ),
    ),
)
