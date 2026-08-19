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
            "Este grupo ayuda a entender el estado inmediato del libro de ordenes, la liquidez disponible y el costo "
            "probable de ejecutar una compra o una venta sin mover demasiado el precio."
        ),
        entries=(
            GlossaryEntry(
                term="Lineas de profundidad",
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
                term="Mejor compra y mejor venta",
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
                term="Spread y mid price",
                practical_definition=(
                    "El spread es la distancia entre mejor compra y mejor venta; el mid price es el punto medio entre ambas puntas."
                ),
                how_to_use=(
                    "Usalos para medir friccion operativa: spreads amplios suelen implicar mas costo de entrada o salida y menor eficiencia de ejecucion."
                ),
                decision_support=(
                    "Ayudan a decidir si conviene esperar liquidez adicional, reducir tamano o cambiar el precio limite de la orden."
                ),
            ),
        ),
    ),
    GlossarySection(
        title="Referencias de sesion",
        summary=(
            "Estas metricas ubican el precio actual dentro del contexto minimo de la jornada para interpretar fuerza, debilidad y calidad del movimiento."
        ),
        entries=(
            GlossaryEntry(
                term="Cierre anterior, maximo y minimo",
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
