---
description:
  "Coloque texto grabado, etiquetas y números de serie en un boceto con la herramienta de cuadro de
  texto de Rayforge."
---

# Cuadro de texto

La herramienta de cuadro de texto (`G+T`) coloca texto en el boceto como geometría editable — texto
grabado, etiquetas y números de serie. Los cuadros de texto son totalmente paramétricos: los glifos
viven dentro de un marco con restricciones, de modo que se vuelven a resolver cada vez que el marco
se mueve o se dimensiona.

![Una marca denominativa y una etiqueta de pieza](/screenshots/addons-sketcher-tool-text-box.webp)

## Crear y editar texto

1. Seleccione la herramienta de cuadro de texto en el menú circular, en el menú **Boceto**, o con
   `G+T`.
2. Haga clic donde desea que comience el texto: aparece un cuadro de texto en el punto de clic y la
   herramienta pasa directamente al modo de edición.
3. Escriba el texto — el cuadro se redimensiona solo para adaptarse mientras escribe.
4. Pulse `Enter` o `Escape` para terminar la edición.

Para editar un cuadro de texto existente, haga clic dentro de él. Un doble clic selecciona una
palabra, un triple clic la línea completa, y el texto puede seleccionarse y reemplazarse como en
cualquier editor de texto, incluidos `Ctrl+C`/`Ctrl+V`, deshacer/rehacer y pegar a mitad de la
edición.

## Propiedades de fuente

![El panel de propiedades de fuente](/screenshots/addons-sketcher-tool-text-box-font-properties.webp)

El panel **Propiedades de fuente** de la barra lateral controla el aspecto del cuadro de texto
seleccionado en el lienzo:

- **Familia de fuente** — elija entre las fuentes del sistema instaladas.
- **Fuente personalizada** — elija una fuente instalada por usted mismo (consulte
  [Fuentes personalizadas](#custom-fonts)).
- **Tamaño de fuente** — en puntos.
- Alternadores **Negrita** y **Cursiva**.

## Transformaciones de texto {#text-transforms}

El mismo panel puede cambiar cómo se distribuye el texto dentro de su marco:

- **Espejar** — voltea el texto de izquierda a derecha, para grabar en la parte posterior de un
  material transparente.
- **Invertir caracteres** — escribe los caracteres en orden inverso sin voltearlos.
- **Vertical** — apila los caracteres erguidos de arriba a abajo.
- **Rotación** — gira el texto alrededor del centro de su marco. El marco en sí permanece
  horizontal.
- **Boca abajo** — un atajo para una rotación de 180°.

Mientras una de estas opciones esté activa, aún puede escribir en el cuadro de texto, pero hacer
clic ya no colocará el cursor dentro del texto.

## Texto Knock-out {#knock-out-text}

Active **Knock-out** para grabar una placa dejando el texto en blanco. La placa es el marco de texto
ampliado por el **Margen de knock-out** en cada lado. El contorno contiene la placa y las letras; el
relleno cubre la placa excepto las letras.

Las partes cerradas de letras como O, A y B no se conservan, por lo que el texto knock-out está
pensado para grabado, no para cortar plantillas.

## Texto en una trayectoria {#text-on-a-path}

El texto puede seguir una línea, un arco, un círculo o una curva:

1. Seleccione el cuadro de texto junto con la forma que debe seguir.
2. Active **Seguir trayectoria** en el panel Propiedades de fuente.

- **Lado de la trayectoria** — **Exterior** coloca el texto a la izquierda de la dirección de la
  trayectoria; **Interior** lo coloca en el otro lado e invierte la dirección de lectura, de modo
  que el texto en el interior de un círculo se lee al derecho en la parte inferior.
- **Alineación de la trayectoria** — inicio, centro o fin de la trayectoria.
- **Desplazamiento de la trayectoria** — desplaza el texto a lo largo de la trayectoria.
- **Texto inferior** — en un círculo, una segunda línea de texto centrada en la parte inferior en el
  interior, mientras que el texto principal está centrado en la parte superior en el exterior. Ambos
  se leen al derecho, lo que permite crear un sello o estampa redonda.

Para liberar el texto, seleccione solo el cuadro de texto y vuelva a activar **Seguir trayectoria**.
Si se elimina la forma, el texto vuelve a su marco.

El texto en una trayectoria mantiene su tamaño de fuente, y espejar, vertical, rotación y knock-out
no se aplican a él. Una trayectoria es una sola forma; el texto no continúa de una línea o arco al
siguiente.

## Fuentes personalizadas {#custom-fonts}

Use **Instalar fuente…** para agregar un archivo `.ttf` o `.otf`. Las fuentes instaladas aparecen en
la lista **Fuente personalizada** en cada boceto, y **Eliminar fuente personalizada** elimina la
seleccionada.

Las fuentes se almacenan en su equipo, no dentro del archivo de proyecto. Cuando un proyecto utiliza
una fuente que no está instalada, el panel muestra **Fuente no instalada** y se utiliza una fuente
sustituta hasta que instale la fuente o elija otra.

## Preajustes {#presets}

Un preajuste guarda la fuente y el estilo del texto, pero no el texto en sí ni la trayectoria que
sigue. Escriba un nombre en **Guardar como preajuste** para almacenar la configuración del cuadro de
texto seleccionado, elija un nombre en **Preajuste** para aplicarlo y use **Eliminar preajuste**
para eliminar el preajuste seleccionado. Aplicar un preajuste es un único paso de deshacer.

## Números de serie {#serial-numbers}

**Insertar número de serie** añade `{serial()}` al texto, muestra el siguiente número y explica que
el contador avanza un paso cada vez que se envía un trabajo a la máquina o se exporta como G-code.
El encuadre, las vistas previas y los trabajos cancelados o fallidos no consumen un número.

Los contadores se comparten entre todos los documentos y se gestionan en **Ajustes → Números de
serie**. La página de ajustes guía a través de tres pasos: cree un contador, vincúlelo con
`{serial("name")}` o Insertar número de serie en Propiedades de fuente, y tenga en cuenta que el
contador avanza una vez por trabajo en lugar de por cada copia en el lienzo. Cada tarjeta de
contador muestra `Use as {serial("name")}. Next number: ...` (o `{serial()}` para el contador por
omisión), junto con controles para el valor inicial, paso, relleno con ceros, prefijo y sufijo.

## Un marco paramétrico

Un cuadro de texto no es una imagen rasterizada: sus glifos son geometría de boceto real, dispuesta
dentro de un marco definido por un origen y puntos de anchura y altura. El marco se dibuja
discontinuo como geometría de construcción, de modo que sirve de referencia de composición y nunca
acaba en las trayectorias de herramienta cuando se fabrica el boceto. Como todo lo demás en el
diseñador, el marco tiene restricciones, por lo que puede dimensionarse como cualquier otra
geometría — cambie la restricción de anchura y el texto se vuelve a resolver para llenar el cuadro.

Hacer clic dentro de un cuadro de texto con la [herramienta de relleno](fill.md) alterna el relleno
de los glifos del texto en lugar de crear un relleno de región.

## Expresiones de plantilla

Los cuadros de texto aceptan **expresiones de plantilla**: todo lo que esté entre llaves se evalúa
cuando el boceto se resuelve, de modo que las etiquetas pueden mostrar valores en vivo como
dimensiones, fechas o números de serie únicos. Consulte
[Expresiones de plantilla en cuadros de texto](expressions.md#template-expressions-in-text-boxes)
para conocer los detalles y las funciones integradas.
