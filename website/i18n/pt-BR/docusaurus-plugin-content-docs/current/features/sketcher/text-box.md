---
description:
  "Coloque texto gravado, etiquetas e números de série em um esboço com a ferramenta de caixa de
  texto do Rayforge."
---

# Caixa de texto

A ferramenta de caixa de texto (`G+T`) coloca texto no esboço como geometria editável — texto
gravado, etiquetas e números de série. As caixas de texto são totalmente paramétricas: os glifos
vivem dentro de um quadro com restrições, de modo que são resolvidos novamente sempre que o quadro é
movido ou dimensionado.

![Uma marca nominativa e uma etiqueta de peça](/screenshots/addons-sketcher-tool-text-box.webp)

## Criar e editar texto

1. Selecione a ferramenta de caixa de texto no menu circular, no menu **Esboço**, ou com `G+T`.
2. Clique onde deseja que o texto comece: uma caixa de texto aparece no ponto do clique e a
   ferramenta passa direto para o modo de edição.
3. Digite o texto — a caixa se redimensiona para caber enquanto você digita.
4. Pressione `Enter` ou `Esc` para terminar a edição.

Para editar uma caixa de texto existente, clique dentro dela. Um clique duplo seleciona uma palavra,
um clique triplo a linha inteira, e o texto pode ser selecionado e substituído como em qualquer
editor de texto, incluindo `Ctrl+C`/`Ctrl+V`, desfazer/refazer e colar no meio da edição.

## Propriedades da Fonte

![O painel de propriedades da fonte](/screenshots/addons-sketcher-tool-text-box-font-properties.webp)

O painel **Propriedades da Fonte** na barra lateral controla a aparência da caixa de texto
selecionada no canvas:

- **Família da Fonte** — escolha entre as fontes do sistema instaladas.
- **Fonte personalizada** — escolha uma fonte que você mesmo instalou (consulte
  [Fontes personalizadas](#custom-fonts)).
- **Tamanho da Fonte** — em pontos.
- Alternadores **Negrito** e **Itálico**.

## Transformações de texto {#text-transforms}

O mesmo painel pode alterar como o texto é disposto dentro de seu quadro:

- **Espelhar** — inverte o texto da esquerda para a direita, para gravar no verso de um material
  transparente.
- **Inverter caracteres** — escreve os caracteres em ordem inversa sem invertê-los.
- **Vertical** — empilha caracteres em pé de cima para baixo.
- **Rotação** — gira o texto ao redor do centro do seu quadro. O próprio quadro permanece
  horizontal.
- **De cabeça para baixo** — um atalho para uma rotação de 180°.

Enquanto uma dessas opções estiver ativa, você ainda poderá digitar na caixa de texto, mas clicar
não posicionará mais o cursor dentro do texto.

## Texto Knock-out {#knock-out-text}

Ative **Knock-out** para gravar uma placa deixando o texto em branco. A placa é o quadro de texto
expandido pela **Margem de knock-out** em cada lado. O contorno contém a placa e as letras; o
preenchimento cobre a placa, exceto as letras.

As partes internas de letras como O, A e B não são mantidas, portanto o texto knock-out é destinado
à gravação, não ao corte de estêncil.

## Texto em um caminho {#text-on-a-path}

O texto pode seguir uma linha, um arco, um círculo ou uma curva:

1. Selecione a caixa de texto junto com a forma que ela deve seguir.
2. Ative **Seguir caminho** no painel Propriedades da Fonte.

- **Lado do caminho** — **Externo** posiciona o texto à esquerda da direção do caminho; **Interno**
  o posiciona no outro lado e inverte o sentido de leitura, de modo que o texto no interior de um
  círculo seja lido em pé na parte inferior.
- **Alinhamento do caminho** — início, centro ou fim do caminho.
- **Deslocamento do caminho** — desloca o texto ao longo do caminho.
- **Texto inferior** — em um círculo, uma segunda linha de texto centralizada na parte inferior no
  lado interno, enquanto o texto principal fica centralizado no topo no lado externo. Ambos são
  lidos em pé, formando um carimbo ou selo redondo.

Para liberar o texto, selecione apenas a caixa de texto e ative **Seguir caminho** novamente. Se a
forma for excluída, o texto retornará ao seu quadro.

O texto em um caminho mantém o tamanho da fonte, e espelhar, vertical, rotação e knock-out não se
aplicam a ele. Um caminho é uma única forma; o texto não continua de uma linha ou arco para o
próximo.

## Fontes personalizadas {#custom-fonts}

Use **Instalar fonte…** para adicionar um arquivo `.ttf` ou `.otf`. As fontes instaladas aparecem na
lista **Fonte personalizada** em todos os esboços, e **Remover fonte personalizada** exclui a
selecionada.

As fontes são armazenadas no seu computador, não dentro do arquivo de projeto. Quando um projeto usa
uma fonte que não está instalada, o painel exibe **Fonte não instalada** e uma fonte substituta é
usada até que você instale a fonte ou escolha outra.

## Predefinições {#presets}

Uma predefinição armazena a fonte e o estilo do texto, mas não o texto em si nem o caminho que ele
segue. Digite um nome em **Salvar como predefinição** para armazenar as configurações da caixa de
texto selecionada, escolha um nome em **Predefinição** para aplicá-la e use **Excluir predefinição**
para remover a predefinição selecionada. A aplicação de uma predefinição é uma única etapa de
desfazer.

## Números de série {#serial-numbers}

**Inserir número de série** adiciona `{serial()}` ao texto, mostra o próximo número e explica que o
contador avança um passo a cada trabalho enviado para a máquina ou exportado como G-code. O
enquadramento, as visualizações e os trabalhos cancelados ou com falha não consomem um número.

Os contadores são compartilhados por todos os documentos e são gerenciados em **Configurações →
Números de série**. A página de configurações orienta através de três etapas: crie um contador,
vincule-o com `{serial("name")}` ou Inserir número de série nas Propriedades da fonte e observe que
o contador avança uma vez por trabalho em vez de a cada cópia na tela. Cada cartão de contador exibe
`Use as {serial("name")}. Next number: ...` (ou `{serial()}` para o contador padrão), juntamente com
controles de valor inicial, passo, preenchimento com zeros, prefixo e sufixo.

## Um quadro paramétrico

Uma caixa de texto não é uma imagem raster: seus glifos são geometria de esboço real, disposta
dentro de um quadro definido por uma origem e pontos de largura e altura. O quadro é desenhado
tracejado como geometria de construção, portanto serve como referência de layout e nunca acaba nas
trajetórias de ferramenta quando o esboço é fabricado. Como tudo o mais no esboçador, o quadro tem
restrições, então pode ser dimensionado como qualquer outra geometria — altere a restrição de
largura e o texto é resolvido novamente para preencher a caixa.

Clicar dentro de uma caixa de texto com a [ferramenta de preenchimento](fill.md) alterna o
preenchimento dos glifos do texto em vez de criar um preenchimento de região.

## Expressões de modelo

As caixas de texto aceitam **expressões de modelo**: tudo o que estiver entre chaves é avaliado
quando o esboço é resolvido, de modo que rótulos podem exibir valores ao vivo, como dimensões, datas
ou números de série exclusivos. Consulte
[Expressões de modelo em caixas de texto](expressions.md#template-expressions-in-text-boxes) para
obter detalhes e as funções integradas.
