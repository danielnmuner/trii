from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaqEntry:
    question: str
    answer_paragraphs: tuple[str, ...]


FAQ_ENTRIES: tuple[FaqEntry, ...] = (
    FaqEntry(
        question="¿Qué es trii?",
        answer_paragraphs=(
            "trii es una Fintech colombiana determinada a democratizar el acceso de todas las personas al mercado bursátil, de una forma amigable, fácil de entender, accesible y barata.",
        ),
    ),
    FaqEntry(
        question="¿Cuáles son los beneficios de usar trii?",
        answer_paragraphs=(
            "Al usar trii, puedes comprar y vender acciones y ETF's de empresas de Colombia y el mundo a cualquier hora y desde cualquier parte del mundo pagando comisiones bajas y con un proceso 100% digital, rápido y seguro.",
            "Además tendrás acceso a una plataforma completamente en español en la que podrás recibir asesoría por un profesional debidamente certificado por el AMV. Los productos y servicios son prestados en alianza con Acciones & Valores S.A. SCB, entidad vigilada por la Superintendencia Financiera de Colombia y con más de 60 años en el mercado bursátil.",
        ),
    ),
    FaqEntry(
        question="¿Qué seguridad tiene el dinero que se encuentra en trii?",
        answer_paragraphs=(
            "Tu dinero se encuentra 100% seguro. trii no administra recursos directamente; cuando depositas dinero para invertir, este llega a una cuenta creada para ti por Acciones & Valores S.A. y se denomina saldo en caja.",
            "De ese dinero solo tú puedes disponer ingresando a la aplicación con tu usuario y contraseña.",
        ),
    ),
    FaqEntry(
        question="¿En qué horario puedo comprar y vender acciones?",
        answer_paragraphs=(
            "Las acciones se negocian en los horarios definidos por la BVC: días hábiles entre las 8:30 a. m. y las 3:00 p. m. entre marzo y noviembre, y entre las 9:30 a. m. y las 4:00 p. m. entre noviembre y marzo.",
            "Sin embargo, puedes programar tus órdenes en cualquier momento para que sean enviadas al mercado cuando este abra.",
        ),
    ),
    FaqEntry(
        question="¿Me puedo contactar con un asesor financiero?",
        answer_paragraphs=(
            "Al estar vinculado a Acciones y Valores S.A. comisionista de bolsa podrás solicitar asesoría con un profesional certificado por el AMV a través de servicioalcliente@accivalores.com o juan.espitia@accivalores.com.",
        ),
    ),
    FaqEntry(
        question="¿Qué entidad nos supervisa?",
        answer_paragraphs=(
            "trii es la herramienta tecnológica por medio de la cual accedes a los servicios ofrecidos por Acciones & Valores S.A. S.C.B., entidad que se encuentra vigilada y supervisada por la Superintendencia Financiera de Colombia.",
        ),
    ),
    FaqEntry(
        question="¿Qué es Acciones y Valores?",
        answer_paragraphs=(
            "Acciones & Valores es la firma comisionista más antigua de Colombia y, a sus más de 60 años, sigue siendo una de las más innovadoras, con productos y servicios orientados a generar beneficios para sus clientes.",
        ),
    ),
    FaqEntry(
        question="¿Cuál es la relación entre trii y Acciones y Valores S.A. SCB?",
        answer_paragraphs=(
            "trii es la herramienta tecnológica por medio de la cual accedes a los productos y servicios ofrecidos por Acciones & Valores S.A. S.C.B., quien es el intermediario del mercado bursátil que envía a la Bolsa de Valores las órdenes de compra y venta colocadas por los usuarios desde la app.",
            "Ante la BVC, todas las operaciones realizadas a través de trii App son operadas por Acciones & Valores S.A. SCB. Además, todos los recursos de los usuarios de trii son custodiados por Acciones & Valores S.A. SCB.",
        ),
    ),
    FaqEntry(
        question="¿Qué es la BVC?",
        answer_paragraphs=(
            "La Bolsa de Valores de Colombia es una bolsa multiproducto y multimercado que administra los sistemas de negociación y registro de los mercados de acciones, renta fija, derivados, divisas, OTC y servicios de emisores en Colombia.",
        ),
    ),
    FaqEntry(
        question="¿Qué es la Superintendencia Financiera?",
        answer_paragraphs=(
            "Es un organismo técnico adscrito al Ministerio de Hacienda y Crédito Público. Supervisa el sistema financiero colombiano para preservar su estabilidad, seguridad y confianza, así como promover, organizar y desarrollar el mercado de valores colombiano y la protección de inversionistas, ahorradores y asegurados.",
        ),
    ),
    FaqEntry(
        question="¿Qué es Deceval?",
        answer_paragraphs=(
            "Deceval es el Depósito Centralizado de Valores de Colombia. Además de custodiar títulos, también los administra, liquida y compensa cuando se negocian en el mercado.",
        ),
    ),
    FaqEntry(
        question="¿Cuál es el monto máximo que puedo depositar?",
        answer_paragraphs=(
            "Como los depósitos se realizan a través de PSE, el monto máximo por transacción que podrás realizar es de $19.000.000 COP.",
        ),
    ),
    FaqEntry(
        question="¿Cuánto demora en llegar el retiro a mi cuenta bancaria?",
        answer_paragraphs=(
            "El retiro demora alrededor de 3 a 5 días hábiles en llegar a la cuenta bancaria.",
        ),
    ),
    FaqEntry(
        question="¿Me cobran por retirar dinero?",
        answer_paragraphs=(
            "Los retiros no tienen cobro. Se aplica el impuesto del 4x1000 cuando el dinero retirado no fue operado o invertido en la app.",
        ),
    ),
    FaqEntry(
        question="¿Debo dejar algún porcentaje en mi saldo disponible?",
        answer_paragraphs=(
            "Cuando la orden es a precio de mercado, no toman el 100% del saldo disponible en la cuenta de trii, sino el 90%. Esto se debe a que en cuestión de segundos el precio de la acción puede aumentar o disminuir.",
        ),
    ),
    FaqEntry(
        question="¿Cuando envío una orden, ésta se calza inmediatamente?",
        answer_paragraphs=(
            "Si la orden es a precio mercado, calzará inmediatamente, a menos que no haya liquidez en el mercado o no exista punta contraria.",
            "Si la orden es a precio límite, se ejecutará cuando haya una punta contraria al mismo precio. Si eso no sucede antes del cierre del mercado, la orden se cancelará automáticamente.",
        ),
    ),
    FaqEntry(
        question="¿Cuánto me cobran por realizar compras y ventas?",
        answer_paragraphs=(
            "La comisión es de $14.875 COP por una compra o venta de hasta $5.000.000. Si supera ese monto, se cobra 0.25% + IVA.",
            "Con trii Pro tienes 50% de descuento sobre la comisión normal. Ejemplos: para $5.000.000 la comisión normal es $14.875 y en trii Pro es $7.437,50; para $5.010.000 la comisión normal es $14.904,75 y en trii Pro es $7.452,38 COP.",
        ),
    ),
    FaqEntry(
        question="¿Qué es la subasta de cierre y cómo funciona?",
        answer_paragraphs=(
            "La subasta de cierre determina el precio al que una acción cerrará la jornada y puede concentrar algunos de los mayores volúmenes de negociación del día, especialmente en rebalanceos de índices bursátiles.",
            "En Colombia, la subasta comienza aproximadamente a las 2:55 p. m. Durante ese periodo solo se reciben órdenes y no hay calce inmediato. En trii Pro se pueden observar las líneas de profundidad y el precio indicativo, que muestra el precio al que potencialmente se produciría el calce si la subasta terminara en ese instante.",
            "El calce se realiza al terminar la subasta, alrededor de la hora de cierre. La documentación de trabajo indica que puede ocurrir hasta 60 segundos antes o después de la hora de cierre, pero conviene tratar esa afirmación como operativa y no como regla normativa fija sin verificarla directamente con la BVC.",
        ),
    ),
    FaqEntry(
        question="¿Qué se debe tener en cuenta para operar en la subasta de cierre?",
        answer_paragraphs=(
            "Durante la subasta las órdenes se acumulan y no se ejecutan inmediatamente. El sistema calcula continuamente un precio indicativo, que puede cambiar conforme entran, modifican o cancelan órdenes. Ese precio indicativo no garantiza ni el precio final ni que una orden vaya a ejecutarse.",
            "Para participar, es recomendable usar órdenes límite, indicando el precio máximo que estás dispuesto a pagar al comprar o el mínimo que aceptas al vender. Una orden puede quedar parcialmente ejecutada o sin ejecutar si al precio de equilibrio no existe suficiente contraparte.",
            "La cantidad disponible en cada nivel de precio es fundamental. No basta con mirar el precio; hay que observar cuánto volumen existe por encima y por debajo de él. En trii Pro puedes observar en tiempo real la profundidad y las cinco mejores puntas de compra y venta.",
            "Antes de participar conviene revisar precio indicativo, volumen disponible, profundidad y distancia entre compra y venta, y no decidir únicamente por el último precio observado o por un incremento aislado del volumen.",
        ),
    ),
    FaqEntry(
        question="¿Qué es un rebalanceo de índices?",
        answer_paragraphs=(
            "Un índice, como el MSCI COLCAP, está compuesto por determinadas acciones. Periódicamente se revisa su composición y los pesos que tiene cada empresa. Cuando cambia esa composición, los fondos que buscan replicar el índice pueden verse obligados a comprar o vender grandes cantidades de acciones para ajustar sus portafolios.",
            "Si una acción aumenta su peso dentro del índice, los fondos replicadores podrían necesitar comprar más. Si reduce su peso o sale del índice, podrían necesitar vender. Esa demanda u oferta adicional puede concentrarse en la subasta de cierre y provocar volúmenes excepcionalmente altos.",
        ),
    ),
    FaqEntry(
        question="¿Cómo puedo aprovechar la subasta de cierre para comprar o vender?",
        answer_paragraphs=(
            "Si quieres comprar, puedes colocar una orden límite, por ejemplo, a $50.900: si el cierre queda en $51.200, no compras; si queda en $50.800, podrías comprar. Si quieres vender, puedes colocar una orden límite a $51.000: si el cierre queda en $51.200, podrías vender; si queda en $50.800, no.",
            "La subasta permite observar cómo el mercado está formando el posible precio de cierre antes de que este sea definitivo. La idea no es asumir que si el precio indicativo sube la acción necesariamente subirá, sino analizar conjuntamente precio indicativo, volumen y profundidad para decidir qué precio límite estás dispuesto a aceptar.",
        ),
    ),
    FaqEntry(
        question="¿Cómo sé en Colombia que ese día existe un rebalanceo de índice que puede generar compras o ventas institucionales?",
        answer_paragraphs=(
            "Los rebalanceos de índices se anuncian previamente, por lo que no es necesario descubrirlos observando la subasta. En el caso del MSCI COLCAP, MSCI publica los resultados del rebalanceo con anticipación y normalmente los cambios se implementan al cierre del último día hábil del mes y empiezan a regir al día siguiente.",
            "Para operar la subasta, lo importante es consultar el calendario y los avisos oficiales de MSCI, BVC o nuam, y saber qué acciones cambian de peso y en qué fecha exacta se hace efectivo el cambio.",
        ),
    ),
    FaqEntry(
        question="¿Qué es un Stop Loss en trii Pro y cómo me sirve?",
        answer_paragraphs=(
            "El Stop Loss es una orden automática que permite vender una acción si su precio cae hasta el nivel que previamente definiste. Por ejemplo, si compraste una acción a $50.000 y estableces un Stop Loss en $45.000, cuando la acción alcance ese precio se activa automáticamente la venta.",
            "En trii Pro puedes elegir entre Stop Loss a Mercado y Stop Loss Límite: el primero prioriza que la venta se ejecute al mejor precio disponible, aunque puede hacerlo por debajo del umbral; el segundo prioriza el precio y solo vende a ese nivel o mejor, pero podría no ejecutarse si la acción cae rápidamente.",
            "Actualmente, estas órdenes tienen una vigencia de 30 días. En la documentación también se indica que trii Pro ofrece Take Profit automático.",
        ),
    ),
    FaqEntry(
        question="¿Qué es Trader Trii MC?",
        answer_paragraphs=(
            "Es un perfil orientado a la operación activa de acciones del mercado colombiano, con seguimiento continuo de la sesión entre las 8:30 a. m. y las 3:00 p. m. Analiza en tiempo real precio, variaciones, volumen negociado, puntas de compra y venta, profundidad del mercado, precio indicativo, noticias y eventos relevantes, incluyendo subastas de cierre y posibles rebalanceos de índices.",
            "Puede crear, modificar y cancelar múltiples órdenes durante la jornada, principalmente órdenes límite, ajustando sus decisiones según cambian las condiciones del mercado y buscando aprovechar movimientos de corto plazo.",
            "Además, mantiene una trazabilidad temporal de la actividad del mercado, registrando por hora y minuto precio, volumen, profundidad, puntas y precio indicativo, junto con órdenes realizadas y noticias o eventos que ayuden a explicar cada movimiento. El objetivo es identificar oportunidades, controlar el riesgo mediante Stop Loss y gestionar activamente las posiciones con base en datos observables e históricos.",
        ),
    ),
)
