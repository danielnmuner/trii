# Impuestos y seguridad social

_Trading activo de acciones colombianas a través de trii / Acciones & Valores_

_Versión de trabajo: 14 de agosto de 2026 · Perfil: persona natural residente fiscal en Colombia · Estrategia: operaciones activas, múltiples compras/ventas y órdenes durante la jornada, exclusivamente en acciones inscritas en una bolsa colombiana._

> **REGLA CENTRAL: La exención del artículo 36-1 del Estatuto Tributario puede hacer que la utilidad de la venta de acciones inscritas en una Bolsa de Valores Colombiana no constituya renta ni ganancia ocasional, pero únicamente si se cumplen simultáneamente sus requisitos. No es automática y no convierte toda la actividad bursátil en “libre de impuestos”.**

## 1. Resumen ejecutivo

Para el escenario definido aquí, el punto tributario más importante es el artículo 36-1 del Estatuto Tributario. La norma vigente establece que las utilidades provenientes de la enajenación de acciones inscritas en una Bolsa de Valores Colombiana no constituyen renta ni ganancia ocasional cuando las acciones pertenecen al mismo beneficiario real y la enajenación no supera el 3% de las acciones en circulación de la respectiva sociedad durante el mismo año gravable. [1][2]

| Tema | Regla práctica | Qué debe controlarse |
| --- | --- | --- |
| Impuesto de renta / GO | Beneficio potencial del Art. 36-1, sujeto a requisitos. | Listado BVC, beneficiario real y % anual por emisor. |
| Valor que se reporta | La operación no desaparece porque la utilidad sea no gravada. | Venta bruta, costo fiscal y utilidad deben poder conciliarse. |
| Costo / utilidad | La renta bruta de una venta se determina por precio de enajenación menos costo del activo enajenado. | Cada venta debe estar vinculada a uno o más lotes de compra. |
| PEPS | La fuente suministrada usa PEPS para asignar las ventas a compras antiguas. | Fecha, cantidad y costo de cada lote. |
| Seguridad social | Es un análisis separado del beneficio de renta. | Ingreso neto mensual, costos, IBC, salud y pensión. |
| Trading frecuente | Puede elevar el riesgo de que las acciones sean consideradas activos movibles si se enajenan dentro del giro ordinario. | Validación de clasificación fiscal con contador tributario. |
| Trazabilidad | La plataforma no sustituye un libro fiscal propio. | Exportes, certificados, comprobantes, conciliaciones y archivo mensual. |

> **OBJETIVO LEGAL: La meta no debe formularse como “no pagar impuestos”, sino como aplicar correctamente los beneficios que la ley permite, pagar lo que corresponda y evitar pagar de más por errores de clasificación, liquidación o diligenciamiento.**

## 2. Jerarquía de fuentes y cómo leer este documento

Este documento consolida tres niveles de fuente. Cuando existe una diferencia, se prioriza la norma y doctrina oficial vigente sobre el contenido educativo de terceros.

| Nivel | Fuente | Uso |
| --- | --- | --- |
| 1 · Primaria | Estatuto Tributario, decretos, DIAN, UGPP y demás norma oficial vigente. | Determina la regla jurídica. |
| 2 · Fuente suministrada | Transcripción del video indicado por el usuario. | Aporta la explicación operativa y ejemplos del tratamiento. |
| 3 · Herramienta suministrada | HTML “Utilidad en venta de acciones · Método PEPS”. | Sirve como calculadora/estructura de control; no sustituye la norma. |

Fuentes del usuario: video https://www.youtube.com/watch?v=V4clPFo3_hg y archivos adjuntos “Markdown.md pegado” y “utilidad-venta-acciones-peps.html”.

## 3. Artículo 36-1: el beneficio tributario que soporta la estrategia

La regla vigente del artículo 36-1 es concreta: las utilidades provenientes de la enajenación de acciones inscritas en una Bolsa de Valores Colombiana no constituyen renta ni ganancia ocasional cuando las acciones son del mismo beneficiario real y la enajenación no supera el 3% de las acciones en circulación de la respectiva sociedad durante el mismo año gravable. La DIAN ha reiterado estos tres requisitos como acumulativos. [1][2]

| Requisito | Qué significa | Control recomendado |
| --- | --- | --- |
| 1. Acción inscrita en BVC | Debe tratarse de una acción efectivamente inscrita en una bolsa colombiana. | Crear un catálogo maestro de tickers elegibles y conservar evidencia de listado. |
| 2. Mismo beneficiario real | La titularidad relevante debe corresponder al mismo beneficiario real. | No mezclar posiciones de personas/estructuras distintas para el cálculo. |
| 3. Límite 3% | La enajenación no puede superar el 3% de las acciones en circulación del emisor durante el año gravable. | Calcular un límite anual por emisor y acumular todas las ventas del año. |

> **IMPORTANTE: El 3% no es 3% del valor de tu portafolio ni 3% del dinero vendido. Es un límite expresado en relación con el número de acciones en circulación de la respectiva sociedad. Por eso, el control debe hacerse por emisor y en número de acciones, no solo en pesos.**

## 4. Cómo se aplica el 3% a un trader que rota posiciones

Ejemplo hipotético: una sociedad tiene 1.000.000.000 de acciones en circulación. El 3% equivale a 30.000.000 de acciones. Si el trader vende 10.000 acciones cada día durante 200 días, habría enajenado 2.000.000 de acciones durante el año, equivalente al 0,2% de las acciones en circulación del emisor. En este ejemplo, el volumen de ventas en pesos podría ser enorme, pero el control del artículo 36-1 sigue girando alrededor del porcentaje de acciones en circulación. El cálculo real debe considerar la cifra de acciones en circulación aplicable y el conjunto de enajenaciones del año.

> **CONTROL ANUAL: Para cada emisor debes tener: acciones en circulación de referencia, límite 3%, acciones vendidas acumuladas en el año, porcentaje acumulado y margen restante. Este control debe actualizarse después de cada venta.**

## 5. Liquidación de una venta: qué debe calcularse

La DIAN señala que la renta bruta o pérdida proveniente de la enajenación de activos se determina, en términos generales, por la diferencia entre el precio de enajenación y el costo de los activos enajenados. La fuente suministrada por el usuario también insiste en que la plataforma muestra la venta, pero no necesariamente la utilidad fiscal de cada operación, por lo que el inversionista debe reconstruirla. [3]

| Paso | Cálculo | Dato mínimo |
| --- | --- | --- |
| 1 | Valor bruto de venta = cantidad × precio de venta | Cantidad, fecha, precio. |
| 2 | Costo fiscal del lote vendido | Compra vinculada, cantidad y precio/costo fiscal. |
| 3 | Utilidad bruta de la operación | Venta menos costo fiscal. |
| 4 | Clasificación tributaria | Beneficio Art. 36-1 si procede; si no, aplicar reglas ordinarias/GO según naturaleza del activo y tiempo de posesión. |
| 5 | Conciliación | Comparar con extracto, certificado y movimientos de trii/Acciones & Valores. |

## 6. PEPS y trazabilidad de lotes

La fuente educativa suministrada utiliza PEPS (primeras en entrar, primeras en salir): una venta se descuenta primero contra las compras más antiguas. Por ejemplo, si se compraron 10 acciones en 2022, 10 en 2023 y 10 en 2024, y en 2026 se venden 12, la fuente asigna 10 a 2022 y 2 a 2023. [4]

| Campo por lote | Ejemplo | Por qué importa |
| --- | --- | --- |
| Ticker | ECOPETROL | Identifica el emisor. |
| Fecha compra | 2026-02-10 | Determina antigüedad y vinculación. |
| Cantidad | 10.000 | Permite PEPS y control del 3%. |
| Precio unitario | $2.500 | Base del costo. |
| Costo total | $25.000.000 | Se compara con la venta. |
| Comisión | $X | Se registra aparte; no asumir automáticamente su tratamiento fiscal. |
| Saldo | Restante después de cada venta | Evita vender “papel” dos veces. |

> **NO CONFUNDIR: PEPS es el método operativo usado por la plantilla y el video suministrados. La norma tributaria no debe considerarse sustituida por la herramienta. En un trader que compra y vende muy frecuentemente, el contador debe confirmar el método de identificación de lotes y la clasificación fiscal aplicable.**

## 7. ALERTA CRÍTICA: el trading frecuente y la naturaleza del activo

La normativa colombiana distingue entre activos fijos e inventarios/activos movibles. El Decreto 1625 señala expresamente que las acciones que se adquieren y no se enajenan dentro del giro ordinario de los negocios son activos fijos, mientras que las acciones que se enajenan dentro del giro ordinario son activos movibles. [4][5]

> **POR QUÉ ES CRÍTICO PARA TU CASO: El perfil que definiste —múltiples compras, ventas, cancelaciones y reaperturas de posiciones durante la misma jornada— se parece mucho más a una actividad de negociación frecuente que al comportamiento de un inversionista que simplemente mantiene acciones. Eso NO significa automáticamente que tu portafolio sea “inventario”; significa que la clasificación debe ser analizada y sustentada por un profesional tributario antes de adoptar como dogma el esquema “menos de 2 años = renta ordinaria / 2 años o más = ganancia ocasional”.**

La regla general de ganancia ocasional por venta de activos fijos exige activos fijos poseídos por dos años o más. [6] Por eso, el criterio de dos años tiene una conexión directa con la naturaleza de activo fijo. Para un trader activo, la primera pregunta profesional no debería ser solamente “¿cuánto tiempo tuve la acción?”, sino también “¿cómo está clasificada fiscalmente esta acción en mi actividad?”.

## 8. Qué pasa con el “menos de 2 años / más de 2 años”

| Situación | Lectura correcta |
| --- | --- |
| Acción BVC + Art. 36-1 cumple todos los requisitos | La utilidad puede ser ingreso no constitutivo de renta ni ganancia ocasional. El beneficio depende del 36-1; la antigüedad no es el requisito central de esa exención. |
| Acción BVC pero 36-1 no procede | Debe aplicarse el régimen que corresponda según naturaleza del activo, costo fiscal y reglas de renta/GO. |
| Activo fijo mantenido 2 años o más | La utilidad puede entrar en el régimen de ganancia ocasional, sujeto a las reglas aplicables. |
| Activo enajenado dentro del giro ordinario | La clasificación como movible puede llevar el resultado al tratamiento de renta ordinaria; debe validarse en el caso concreto. |

## 9. Declaración: por qué “no pagar impuesto” no significa “no reportar”

La DIAN ha indicado que, para efectos del impuesto de renta, en la enajenación de acciones debe declararse la totalidad de los ingresos, sin perjuicio de informar los costos correspondientes; y que para información exógena también debe reportarse la totalidad del ingreso, junto con los costos en el formato respectivo. [3]

> **CONSECUENCIA PRÁCTICA: Una venta exenta/no constitutiva no se debe borrar de la declaración. La estrategia correcta es reportar los componentes de la operación de forma que la utilidad exenta quede correctamente tratada. El beneficio se obtiene por la norma, no ocultando la venta.**

La fuente suministrada explica este punto de forma práctica: en la cédula de renta no laboral deben poder verse el ingreso (valor de la venta), el ingreso no constitutivo de renta/ganancia ocasional y el costo, de modo que el resultado líquido gravable refleje correctamente el beneficio cuando procede. [7]

## 10. Información exógena y trazabilidad

La Resolución 227 de 2025 de la DIAN muestra la importancia de conservar datos de identificación de la operación, incluyendo tipo de título, número de acciones, fecha de adquisición, fecha de enajenación, clasificación y costo fiscal en los reportes que correspondan. [8] La fuente de video además advierte que el certificado del intermediario puede no contener todo el costo de adquisición necesario para reconstruir cada lote. [4]

| Evidencia | Frecuencia | Conservar |
| --- | --- | --- |
| Comprobante de compra | Cada operación | PDF/CSV/descarga de trii/Acciones & Valores. |
| Comprobante de venta | Cada operación | PDF/CSV/descarga y hora. |
| Certificado tributario | Anual | Versión emitida por el intermediario. |
| Libro de lotes PEPS | Continuo | Archivo maestro con saldos. |
| Control 3% por emisor | Cada venta | Cálculo acumulado anual. |
| Libro de seguridad social | Mensual | Cálculo, PILA y soportes. |
| Noticias/eventos relevantes | Cuando existan | Útil para auditoría interna de la estrategia. |

## 11. Seguridad social: separado del impuesto de renta

Este es el punto donde el beneficio del artículo 36-1 NO debe confundirse con la seguridad social. La fuente de video suministrada advierte expresamente que el beneficio tributario de las acciones en bolsa no elimina por sí mismo la discusión de seguridad social. La UGPP identifica las acciones entre las fuentes de ingresos de un rentista de capital y señala que existe obligación de cotizar cuando los ingresos mensuales netos son iguales o superiores a 1 SMLMV. La cotización ordinaria señalada por la UGPP es 12,5% en salud y 16% en pensión. [9]

Para 2026, el SMLMV es $1.750.905. [10] En el esquema general de rentista de capital, la UGPP explica: ingreso bruto menos costos/gastos = ingreso neto; el IBC corresponde, como regla, al 40% del ingreso neto con un piso de 1 SMLMV. El ejemplo oficial de la UGPP muestra que con $5.000.000 de ingreso neto, el IBC es $2.000.000 y los aportes son $250.000 de salud + $320.000 de pensión = $570.000. [9]

| Concepto | Regla 2026 | Fuente |
| --- | --- | --- |
| Umbral de obligación | Ingreso neto mensual >= 1 SMLMV | UGPP [9] |
| IBC | 40% del ingreso neto, sujeto a piso y topes aplicables | UGPP / Decreto 379 de 2026 [9][11] |
| Salud | 12,5% del IBC | UGPP [9] |
| Pensión | 16% del IBC | UGPP [9] |
| SMLMV 2026 | $1.750.905 | Decreto 1469 de 2025 [10] |
| Riesgos laborales para rentista de capital | La UGPP indica que no es obligatorio para el rentista de capital; puede ser voluntario | UGPP [9] |

## 12. Costos reales vs. presunción de costos para seguridad social

El Decreto 379 de 2026 modificó el procedimiento de liquidación de aportes para independientes: primero se determina el ingreso bruto; luego se descuentan costos asociados conforme al artículo 107 y normas aplicables o se puede aplicar el esquema de presunción de costos que expida/actualice la UGPP; finalmente se calcula el aporte sobre el ingreso correspondiente. [11]

> **CAMBIO IMPORTANTE EN 2026: El material de apoyo suministrado usa 28,08% como presunción para rentistas de capital. La nueva regulación de 2026 hace que la referencia operativa sea el porcentaje que la UGPP tenga vigente mediante su resolución. Por eso, para un cálculo definitivo hay que usar la tabla vigente de UGPP aplicable a la actividad y al período, no memorizar un porcentaje aislado.**

La plantilla HTML suministrada conserva 28,08% como valor de trabajo y calcula el IBC sobre 40% del ingreso neto, pero debe tratarse como una herramienta de apoyo. [12] La UGPP todavía mantiene en su página ABC un ejemplo general con 27,5% basado en el esquema anterior, mientras que el Decreto 379 de 2026 remite al esquema actualizado que expida la UGPP. [9][11] Para el ejercicio 2026, esta diferencia debe resolverse utilizando la resolución vigente de UGPP para el período concreto y la clasificación de la actividad, idealmente con revisión profesional.

> **PUNTO QUE DEBE VALIDARSE: El HTML suministrado dice que la ganancia ocasional no cotiza a seguridad social. Esa afirmación no la elevamos aquí a “regla universal” porque la UGPP centra su guía en ingresos netos mensuales de rentistas de capital y el tratamiento puede depender de la naturaleza de la actividad y de la clasificación fiscal. La seguridad social debe revisarse por separado con el profesional que lleve tu PILA/UGPP.**

## 13. Ejemplo completo de una operación del trader

Supuesto: se compran 10.000 acciones de una empresa BVC a $50.000 y se venden posteriormente a $50.500. Para simplificar, se ignoran comisiones en la primera capa del ejemplo.

| Etapa | Cálculo | Resultado |
| --- | --- | --- |
| Compra | 10.000 × $50.000 | $500.000.000 de costo del lote |
| Venta | 10.000 × $50.500 | $505.000.000 de ingreso bruto |
| Utilidad | $505.000.000 - $500.000.000 | $5.000.000 de utilidad bruta |
| Art. 36-1 | Si cumple los 3 requisitos | Los $5.000.000 pueden ser INCRNGO/no gravados por renta y GO |
| Registro | Aun así | Conservar y declarar/reconciliar ingreso + costo + tratamiento no gravado |
| Seguridad social | Análisis separado | Revisar ingreso neto mensual, costos e IBC; no asumir que el beneficio de renta elimina SS |

En una estrategia de alta rotación, la capa comercial y la capa fiscal deben estar separadas. Comercialmente conviene medir la utilidad neta después de comisiones. Fiscalmente se debe liquidar con el costo fiscal que corresponda y con la clasificación adoptada. La plantilla suministrada por el usuario registra las comisiones, pero su cálculo de costo fiscal usa el valor de compra y las deja fuera de la base del lote; por eso no conviene introducir automáticamente una comisión como costo fiscal sin validar la regla que aplique al caso. [12]

## 14. Ejemplo PEPS con varias ventas y varias compras

| Compra | Cantidad | Precio | Costo |
| --- | --- | --- | --- |
| Lote A · 10-01-2026 | 100 | 10.000 | $1.000.000 |
| Lote B · 20-02-2026 | 100 | 11.000 | $1.100.000 |
| Venta · 15-03-2026 | 150 | 13.000 | $1.950.000 ingreso bruto |

Bajo el PEPS usado por la fuente: la venta consume primero las 100 acciones del lote A y luego 50 del lote B. El costo asignado sería $1.000.000 + $550.000 = $1.550.000; utilidad bruta = $400.000. Los 50 restantes del lote B quedan en inventario/stock para futuras ventas. [4][12]

## 15. Libro maestro recomendado para este trader

El libro fiscal debe ser más completo que el historial visual de la app. La intención es que un tercero pueda reconstruir cualquier venta de principio a fin sin preguntarte nada.

| Columna | Obligatorio | Uso |
| --- | --- | --- |
| Fecha y hora de compra/venta | Sí | Trazabilidad. |
| Ticker / emisor | Sí | Aplicación del 36-1 por sociedad. |
| Tipo operación | Sí | Compra / venta / corrección. |
| Cantidad | Sí | 3%, PEPS y conciliación. |
| Precio unitario | Sí | Ingreso y costo. |
| Valor bruto | Sí | Cruce con reportes. |
| Comisión | Sí | Resultado económico y conciliación. |
| Lote fiscal asignado | Sí | Reconstrucción del costo. |
| Costo fiscal asignado | Sí | Liquidación de utilidad. |
| Utilidad bruta | Sí | Base del análisis tributario. |
| Estado 36-1 | Sí | Cumple / no cumple / por validar. |
| % 3% acumulado del emisor | Sí | Control anual. |
| Clasificación activo fijo/movible | Sí | Definición tributaria. |
| Tiempo de tenencia | Sí | Análisis GO/renta si aplica. |
| SS: ingreso neto mensual | Mensual | Control UGPP. |
| Noticias/evento | Opcional pero útil | Explicación del movimiento y auditoría interna. |

## 16. Cierre mensual obligatorio del trader

Exportar todas las compras y ventas ejecutadas.

Conciliar el saldo de efectivo y de acciones contra trii/Acciones & Valores.

Actualizar PEPS y saldos de cada lote.

Actualizar el acumulado anual de acciones vendidas por emisor y el porcentaje frente a las acciones en circulación.

Calcular utilidad por operación y utilidad del mes.

Separar utilidad económica neta de la liquidación fiscal.

Calcular el ingreso neto mensual relevante para seguridad social y conservar la PILA y soportes.

Guardar certificado, extractos, comprobantes, CSV/JSON y una copia congelada del libro del mes.

Revisar si hubo cambios societarios, emisiones, recompras o modificaciones que puedan afectar la cifra de acciones en circulación usada para el control del 3%.

## 17. Cierre fiscal anual

Bloquear una copia del libro al 31 de diciembre.

Calcular por emisor la cantidad total de acciones enajenadas durante el año y el porcentaje frente a acciones en circulación.

Identificar las ventas que cumplen 36-1 y las que requieren tratamiento tributario diferente.

Reconstruir el costo fiscal de cada venta y conciliarlo con certificados y reportes.

Revisar la clasificación fiscal de las acciones y la naturaleza de la actividad del trader.

Preparar la información que el contador necesita para declarar ingreso, costo y tratamiento no gravado correctamente.

Revisar exógena y diferencias frente a la información reportada por terceros.

Revisar seguridad social anual/mensual y conservar PILA, soportes y cálculos.

Revisar por separado dividendos, rendimientos de otros activos y, si aplica, patrimonio para otros impuestos.

## 18. Errores que esta estrategia debe evitar

| Error | Por qué es peligroso | Regla correcta |
| --- | --- | --- |
| “Como son acciones colombianas, todo está exento.” | Art. 36-1 tiene requisitos. | Verificar 3 condiciones por emisor/año. |
| Usar 3% del valor del portafolio. | El límite legal es sobre acciones en circulación. | Control en número de acciones y emisor. |
| No registrar una venta porque “no paga impuesto”. | La operación puede ser reportable y fiscalmente relevante. | Registrar y conciliar todo. |
| Confiar solo en el certificado tributario. | Puede no contener el costo de cada lote. | Llevar libro propio de lotes. |
| Suponer PEPS sin validar. | La norma de clasificación y costo puede depender de la actividad. | Adoptar y documentar una metodología confirmada. |
| Ignorar que el trading frecuente puede ser giro ordinario. | Puede afectar la naturaleza de los activos. | Revisar fijo vs. movible con profesional. |
| Aplicar 27,5% o 28,08% de SS de memoria. | El esquema UGPP fue actualizado en 2026. | Usar resolución vigente del período. |
| Mezclar impuesto de renta con seguridad social. | Son sistemas y beneficios distintos. | Liquidarlos en hojas separadas. |
| Intentar reducir impuesto ocultando operaciones. | Sería una conducta de alto riesgo legal. | Aplicar beneficios legítimos y documentados. |

## 19. Hoja de control 36-1: estructura mínima

| Emisor | Acciones en circulación | Límite 3% | Ventas acumuladas YTD | % usado | Margen restante | Estado |
| --- | --- | --- | --- | --- | --- | --- |
| Ejemplo A | 1.000.000.000 | 30.000.000 | 2.000.000 | 0,20% | 28.000.000 | Dentro del límite |
| Ejemplo B | 50.000.000 | 1.500.000 | 1.450.000 | 2,90% | 50.000 | Alerta |
| Ejemplo C | 10.000.000 | 300.000 | 310.000 | 3,10% | -10.000 | Requiere análisis fiscal |

> **NO AUTOMATIZAR SIN REVISIÓN: Si el porcentaje llega o supera 3%, detén la presunción de exención para nuevas ventas de ese emisor hasta que el contador valide exactamente el tratamiento del año y el efecto de haber superado el umbral.**

## 20. Puntos que un contador tributario debe aprobar antes de iniciar el trading a escala

Clasificación de las acciones como activos fijos o movibles dada la frecuencia y finalidad de las operaciones.

Metodología de identificación del costo de cada venta (PEPS u otra metodología fiscalmente soportable) y forma de documentarla.

Tratamiento de comisiones, derechos, gastos de intermediación y otros costos en la liquidación fiscal y de seguridad social.

Aplicación exacta del artículo 36-1 por emisor y beneficiario real, incluida la forma de acumular el 3% durante el año.

Tratamiento mensual de seguridad social del trader, especialmente cuando también existen salario, honorarios, dividendos, CDT u otros ingresos.

Porcentaje de presunción de costos UGPP aplicable a la actividad y período concretos bajo la resolución vigente en 2026.

Formato y conciliación de información exógena y del certificado anual de Acciones & Valores.

## 21. Árbol de decisión operativo para cada venta

¿La acción está inscrita en una Bolsa de Valores Colombiana? → Si no, no aplicar 36-1 de este documento.

¿El titular es el mismo beneficiario real? → Si no, detener y revisar.

¿La venta acumulada del emisor durante el año se mantiene dentro del 3%? → Si no, detener la presunción de beneficio y revisar con contador.

¿Qué lotes de compra se están vendiendo? → Aplicar la metodología documentada y actualizar saldos.

¿Cuál es el ingreso bruto, costo fiscal y utilidad? → Registrar las tres cifras.

¿El tratamiento 36-1 procede? → Marcar la operación y preparar su correcto reflejo en la declaración/información correspondiente.

¿La operación genera un impacto de seguridad social? → Liquidar por separado con la metodología UGPP vigente.

¿Quedó saldo del lote? → Actualizar el inventario fiscal para la próxima venta.

## 22. Conclusión para este proyecto

Para un trader que opera exclusivamente acciones inscritas en una bolsa colombiana, el artículo 36-1 es potencialmente muy valioso: permite que determinadas utilidades de enajenación no constituyan renta ni ganancia ocasional. Pero la estrategia fiscal correcta no consiste en asumir “0% de impuestos” desde el primer día. Consiste en construir un sistema que demuestre, venta por venta y emisor por emisor, que se cumplen los requisitos del 36-1, que la utilidad y el costo están correctamente reconstruidos, que la clasificación de los activos es defendible dada la frecuencia de trading, y que la seguridad social se liquida separadamente cuando corresponda.

> **DECISIÓN RECOMENDADA: Antes de ejecutar una estrategia de alta rotación con capital importante, consigue una opinión escrita de un contador tributario colombiano sobre dos cosas: (1) clasificación fiscal de tu actividad y activos bajo el artículo 60 / Decreto 1625; y (2) aplicación del artículo 36-1 y del esquema UGPP a tu caso concreto. Esa opinión debe integrarse como regla del libro de control, no quedar como una conversación informal.**

## 23. Fuentes utilizadas

[1] Estatuto Tributario, artículo 36-1, texto vigente en Normograma DIAN. https://normograma.dian.gov.co/dian/compilacion/docs/estatuto_tributario.htm

[2] DIAN, Concepto 8706 de 2025: requisitos acumulativos del artículo 36-1. https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_8706_2025.htm

[3] DIAN, Concepto 5272 de 2023: ingreso total, costo y determinación de renta bruta; información exógena. https://normograma.dian.gov.co/dian/compilacion/docs/oficio_dian_5272_2023.htm

[4] Archivo suministrado por el usuario: transcripción del video sobre venta de acciones (YouTube). https://www.youtube.com/watch?v=V4clPFo3_hg

[5] Decreto 1625 de 2016, art. 1.2.1.6.4: naturaleza de las acciones como activos fijos o movibles. https://normograma.dian.gov.co/dian/compilacion/docs/decreto_1625_2016.htm

[6] Decreto 2344 de 2014 / artículo 300 E.T.: ganancia ocasional por activos fijos poseídos dos años o más. https://normograma.dian.gov.co/dian/compilacion/docs/decreto_2344_2014.htm

[7] Archivo suministrado por el usuario: transcript sobre diligenciamiento de ingreso, INCRNGO y costo. Archivo local adjunto: Markdown.md pegado

[8] DIAN, Resolución 227 de 2025: datos de enajenación y costo fiscal en reportes de información. https://normograma.dian.gov.co/dian/compilacion/docs/resolucion_dian_0227_2025.htm

[9] UGPP, ABC Rentistas de capital: umbral, IBC, salud, pensión y costos. https://www.ugpp.gov.co/abc_rentistas_capital/

[10] Decreto 1469 de 2025 / referencia oficial 2026: SMLMV $1.750.905. https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=276596

[11] Decreto 0379 de 2026: procedimiento actualizado para costos reales o presunción UGPP. https://www1.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=275076

[12] Archivo suministrado por el usuario: calculadora HTML “Utilidad en venta de acciones · Método PEPS”. Archivo local adjunto: utilidad-venta-acciones-peps.html

> **ALCANCE: Este documento es una guía de control y conciliación basada en las fuentes indicadas y en verificación normativa realizada al 14/08/2026. No sustituye una opinión tributaria personalizada. En especial, la clasificación de una persona que realiza trading frecuente y la liquidación de seguridad social requieren revisión del caso concreto.**
