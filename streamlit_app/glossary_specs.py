from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
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
        title="Lectura de mercado y profundidad",
        summary=(
            "Este grupo ayuda a entender el estado inmediato del libro de órdenes, la liquidez disponible y el costo "
            "probable de ejecutar una compra o una venta sin mover demasiado el precio."
        ),
        entries=(
            GlossaryEntry(
                term="Líneas de profundidad",
                practical_definition=(
                    "Muestran los primeros escalones reales del libro de órdenes, con precio y cantidad disponible a cada lado del mercado."
                ),
                how_to_use=(
                    "Revísalas para detectar si la liquidez está concentrada, si hay paredes de compra o venta, y si el mercado puede absorber tu orden sin moverse demasiado."
                ),
                decision_support=(
                    "Permiten decidir tamaño de orden, agresividad de entrada y si conviene usar precio límite para reducir deslizamiento."
                ),
            ),
            GlossaryEntry(
                term="Mejor compra y mejor venta",
                practical_definition=(
                    "Son el bid y el ask vigentes: el precio más alto que alguien ofrece pagar y el más bajo al que alguien acepta vender."
                ),
                how_to_use=(
                    "Compáralos para medir el spread y evaluar si la ejecución inmediata sería eficiente o cara frente al precio de referencia."
                ),
                decision_support=(
                    "Sirven para fijar un precio límite inicial y decidir si vale la pena esperar mejor cruce antes de enviar la orden."
                ),
            ),
            GlossaryEntry(
                term="Volumen y valor volumen",
                practical_definition=(
                    "Reflejan cuántos títulos se han negociado y cuánto capital real ha pasado por el mercado durante la jornada."
                ),
                how_to_use=(
                    "Úsalos para diferenciar movimientos respaldados por participación real del mercado frente a cambios de precio con poca confirmación."
                ),
                decision_support=(
                    "Ayudan a decidir si una señal técnica merece confianza operativa o si conviene asumir que la liquidez sigue siendo frágil."
                ),
            ),
            GlossaryEntry(
                term="Cierre anterior, máximo y mínimo",
                practical_definition=(
                    "Son referencias base de la sesión para ubicar el precio actual dentro de su rango reciente y frente al último cierre válido."
                ),
                how_to_use=(
                    "Contrasta el precio actual con estos niveles para identificar fuerza relativa, debilidad o compresión intradía."
                ),
                decision_support=(
                    "Sirven para estimar riesgo intradía y validar si el activo está rompiendo rango o solo oscilando sin convicción."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Osciladores y momentum",
        summary=(
            "Estos indicadores sirven para medir aceleración, agotamiento y posibles giros del precio, especialmente "
            "cuando se evalúan entradas tácticas o confirmaciones de corto plazo."
        ),
        entries=(
            GlossaryEntry(
                term="RSI 7, 21, 50 y 200",
                practical_definition=(
                    "Miden la velocidad relativa de las subidas frente a las caídas en varios horizontes de tiempo."
                ),
                how_to_use=(
                    "Busca consistencia entre horizontes: lecturas altas sugieren sobrecompra, bajas sugieren sobreventa y niveles intermedios suelen indicar neutralidad o tendencia estable."
                ),
                decision_support=(
                    "Ayudan a decidir si conviene esperar mejor precio, entrar con paciencia o evitar perseguir un movimiento ya muy exigido."
                ),
            ),
            GlossaryEntry(
                term="Estocástico lento D y rápido D",
                practical_definition=(
                    "Comparan el cierre reciente contra su rango para mostrar aceleración, agotamiento y cercanía a extremos de corto plazo."
                ),
                how_to_use=(
                    "Úsalos para ver si el activo entra en zona extrema o empieza a perder fuerza después de un impulso rápido."
                ),
                decision_support=(
                    "Sirven para evitar compras tardías en sobreextensión o ventas apresuradas cuando todavía no aparece agotamiento real."
                ),
            ),
            GlossaryEntry(
                term="MACD",
                practical_definition=(
                    "Compara una media corta con una más larga para resumir si el impulso se fortalece o se debilita frente a la tendencia."
                ),
                how_to_use=(
                    "Léelo junto con el comentario técnico para confirmar si el precio acompaña una tendencia alcista, bajista o sin convicción."
                ),
                decision_support=(
                    "Apoya decisiones de continuación o cautela cuando el activo parece moverse contra la dirección esperada."
                ),
            ),
            GlossaryEntry(
                term="Williams %R",
                practical_definition=(
                    "Indica qué tan cerca está el cierre de la parte alta o baja de su rango reciente, con foco en extremos de momentum."
                ),
                how_to_use=(
                    "Úsalo para complementar RSI y estocásticos cuando quieras validar si el activo está sobrecomprado, sobrevendido o neutral."
                ),
                decision_support=(
                    "Permite decidir si una entrada agresiva todavía tiene sentido o si el precio ya está demasiado extendido."
                ),
            ),
            GlossaryEntry(
                term="Señales: compra, mantener, venta, compra fuerte, venta fuerte",
                practical_definition=(
                    "Son etiquetas resumidas de interpretación técnica que condensan la lectura del indicador en una acción sugerida."
                ),
                how_to_use=(
                    "No las leas de forma aislada; compáralas con el valor numérico, el comentario y la liquidez real del mercado."
                ),
                decision_support=(
                    "Sirven para priorizar revisión rápida, pero la decisión final debe apoyarse en tendencia, niveles y liquidez."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Tendencia, medias y volatilidad",
        summary=(
            "Este grupo permite entender si el precio sigue una dirección clara, si acelera con fuerza suficiente y "
            "si todavía se mueve dentro de un rango de volatilidad razonable."
        ),
        entries=(
            GlossaryEntry(
                term="MMS 7, 21 y 200",
                practical_definition=(
                    "Son medias móviles simples de corto, medio y largo plazo que resumen la dirección predominante del precio."
                ),
                how_to_use=(
                    "Observa la posición del precio frente a cada media para saber si la acción sigue alineada con la tendencia o empieza a deteriorarse."
                ),
                decision_support=(
                    "Ayudan a decidir si conviene operar a favor de tendencia, esperar confirmación o evitar entradas contra estructura."
                ),
            ),
            GlossaryEntry(
                term="Momento 14",
                practical_definition=(
                    "Mide la velocidad reciente del movimiento y si el precio está ganando o perdiendo tracción."
                ),
                how_to_use=(
                    "Combínalo con medias y osciladores para distinguir entre una subida sostenida, un rebote débil o un impulso agotado."
                ),
                decision_support=(
                    "Sirve para decidir si una ruptura tiene fuerza suficiente o si aún no justifica ejecución inmediata."
                ),
            ),
            GlossaryEntry(
                term="Bollinger Up y Bollinger Down",
                practical_definition=(
                    "Definen bandas superior e inferior alrededor de la media para estimar volatilidad y distancia relativa del precio."
                ),
                how_to_use=(
                    "Evalúa si el precio se mantiene dentro de un rango razonable o si ya se aproxima a una zona de extensión."
                ),
                decision_support=(
                    "Permiten decidir si la entrada todavía tiene recorrido sano o si el riesgo aumenta por exceso de extensión."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Niveles operativos y escenarios",
        summary=(
            "Estos niveles convierten la lectura técnica en zonas concretas de trabajo para planear entradas, salidas y control de riesgo."
        ),
        entries=(
            GlossaryEntry(
                term="Soporte 1 y soporte 2",
                practical_definition=(
                    "Son zonas donde históricamente el precio podría frenar caídas o intentar rebote por presencia de demanda."
                ),
                how_to_use=(
                    "Úsalos como zonas de observación para rebote, invalidación o gestión de riesgo si el precio empieza a cederlas."
                ),
                decision_support=(
                    "Sirven para definir entradas prudentes, stops técnicos y escenarios de deterioro adicional."
                ),
            ),
            GlossaryEntry(
                term="Resistencia 1 y resistencia 2",
                practical_definition=(
                    "Son zonas donde el precio podría enfrentar oferta, pausa, rechazo o toma de utilidades."
                ),
                how_to_use=(
                    "Revisa si el precio llega con fuerza, llega exhausto o necesita confirmación adicional para romper."
                ),
                decision_support=(
                    "Ayudan a fijar objetivos parciales, zonas de salida y confirmaciones para continuar una posición."
                ),
            ),
            GlossaryEntry(
                term="Cambio (%) y precio de cierre",
                practical_definition=(
                    "Miden la distancia del precio frente a cada nivel y anclan el escenario técnico al cierre usado como referencia."
                ),
                how_to_use=(
                    "Compáralos con el precio actual para estimar recorrido potencial y proximidad real a cada soporte o resistencia."
                ),
                decision_support=(
                    "Permiten priorizar escenarios con mejor relación entre oportunidad y riesgo antes de tomar una orden."
                ),
            ),
            GlossaryEntry(
                term="Escenario técnico",
                practical_definition=(
                    "Es la interpretación textual del sesgo actual, la presión dominante y las condiciones que cambiarían la lectura del activo."
                ),
                how_to_use=(
                    "Léelo como contexto final para entender qué nivel invalida el escenario y qué ruptura lo confirma."
                ),
                decision_support=(
                    "Ayuda a decidir si la operación depende de ruptura, de rebote o de mantener una postura neutral."
                ),
            ),
        ),
    ),
)
