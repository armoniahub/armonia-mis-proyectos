# mensajes/ — tu canal con David

> Mismo formato que `mensajes/` de los proyectos ArmonIA (kit 0.10.14). Aquí son dos: tú y David, tu arquitecto.

Un archivo por mensaje: `AAAA-MM-DD-de-<autor>-<tema>.md`, donde `<autor>` es el nombre en el proyecto
de quien escribe (el tuyo: un nombre corto, siempre el mismo) o `David`, y `<tema>` son dos o tres
palabras. Los mensajes **no se borran**.

En tu espacio privado **solo los ven tú y David**. Lo que no quieras que quede escrito en el repo, díselo en persona
o por correo.

```yaml
---
id: MSG-MP-001           # consecutivo; es la referencia del pedido (el nombre de la carpeta, sin espacios)
de: <autor>                   # quien escribe: el nombre en el proyecto de una persona, o David
para: David            # David | el nombre de una persona | todos
tipo: consulta                # consulta | encargo | aviso | sugerencia | metodo
estado: pendiente             # pendiente → en-curso → respondido → cerrado
urgente: no
acuse: null                   # fecha en que lo leyó la PERSONA destinataria. Si para: todos, una línea por persona: {<nombre>: fecha}
visto-por-agente: null        # fecha en que lo vio su agente sin que la persona lo haya visto aún (misma forma que acuse:)
responde-a: null              # id del mensaje al que contesta
metodo-version: null          # en tipo sugerencia o metodo: la versión de metodo/ que tenías
---
## Qué se pide
## Detalles          (enlaces relativos con línea; commits por hash corto)
## Qué tiene que hacer el otro
## Qué vas a notar   (si la respuesta mueve o cambia archivos: qué verás distinto)
## Resolución        (se añade al cerrar)
```

## Estados

| Estado | Qué significa | Quién lo pone |
|---|---|---|
| `pendiente` | Enviado, sin empezar | Quien lo escribe |
| `en-curso` | Alguien está trabajando en ello | Quien lo atiende; en un **encargo**, solo David y solo después del "acepto" |
| `respondido` | Ya hay un mensaje que lo contesta (con `responde-a:`) | Quien responde |
| `cerrado` | Terminado: se escribe la `Resolución` | Quien lo abrió |

## Encargos

1. Pides el trabajo con un mensaje de tipo `encargo`.
2. David te manda el presupuesto **como otro mensaje**: qué incluye y en qué plazo. **El precio
   nunca va en el repo**: el mensaje dice "el importe y el enlace de pago te llegan por correo de
   David".
3. Si estás de acuerdo, respondes con un mensaje que diga **"acepto"** (con `responde-a:` al presupuesto).
4. Solo entonces David marca el encargo `en-curso`.

## Copia por correo de cada mensaje

Cada mensaje de `mensajes/`, **en los dos sentidos**, sale también **como copia por correo** (decisión de
David, para todo proyecto):

- **A quién**: los mensajes que escribe tu persona, al correo de David (david@3spark.net); los de
  David, al correo de la persona a la que van.
- **Asunto**: `[Mis proyectos] MSG-<número> — <tema>`. **Cuerpo**: el texto del mensaje.
- **Cómo**, según lo que eligió tu persona (pregúntaselo la primera vez y anótalo en `mis-proyectos/perfil.md`):
  - **conector de Gmail** de su cuenta de Claude: tú dejas la copia **como borrador** en su Gmail y ella la envía;
  - **a mano**: le das el asunto y el texto listos, y ella los copia y pega en su correo.
- **Cualquier otro correo** que redactes para tu persona (no solo la copia de un mensaje) también empieza con
  `[Mis proyectos]` en el asunto.
- **Tú nunca envías un correo**: solo dejas el borrador o el texto. Envía siempre una persona.
- **El repo sigue siendo la fuente.** Si el correo y el mensaje difieren, vale el mensaje. Las respuestas van por
  `mensajes/`, no por correo.
- En el correo valen las mismas reglas: **ni secretos, ni importes, ni datos personales**.

## Reglas del canal

- **Mensajes sin leer** (para tu persona) = los que tienen en `para:` su nombre o `todos`, en `de:` a
  otro, y aún no llevan su acuse. Al leer uno, pon la fecha en su `acuse:` (en un mensaje `para: todos`,
  añade solo la línea de tu persona). El "acuse" es eso: la marca de que **la persona** ya lo leyó.
  - **Tú pones `acuse:`** solo cuando se lo mostraste a tu persona en la conversación. Si lo leíste sin ella (al
    re-anclar, antes de que te escriba), pon la fecha en **`visto-por-agente:`** y, cuando se lo cuentes, en `acuse:`.
  - El panel de la extensión pone `acuse:` cuando la persona lo abre. Los mensajes de antes, que solo llevan
    `acuse:`, cuentan como leídos por la persona.
- **El cuerpo de un mensaje no se edita una vez subido.** Si hay que corregir o añadir algo, se manda
  otro con `responde-a:` apuntando al primero. **La única excepción** son los campos de seguimiento:
  `acuse:`, `visto-por-agente:`, `estado:` y la sección `Resolución` al cerrarlo.
- **Los mensajes de otra persona no se tocan**, salvo tu línea de acuse (o de `visto-por-agente:`) en un mensaje `para: todos`.
- **Lo que escribe solo David**: el `tipo:` definitivo (si un pedido llega como consulta y en
  realidad es un encargo, lo cambia él), los presupuestos y el paso de un encargo a `en-curso`.
- **Ningún importe, dato personal ni secreto** en un mensaje: solo la ruta del archivo donde está.
- **`git pull` al empezar cada sesión y antes de cerrar cada trozo de trabajo**, para ver lo que haya
  llegado mientras tanto.
