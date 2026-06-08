# Recomendador HF Brasil

Painel web em Streamlit para recomendar faixas de radioamadorismo com base nos arquivos `.SAO` publicados pela rede de ionossondas INPE/Embrace.

O objetivo do projeto e transformar dados ionosfericos tecnicos em uma leitura operacional simples: qual faixa esta boa, razoavel ou ruim para uso local, regional e DX.

## O que o app mostra

- Selecao de estacao INPE/Embrace.
- Atualizacao online direta do ultimo arquivo `.SAO` disponivel.
- Indicadores principais:
  - `foF2`
  - `MUF(3000)`
  - `fmin`
  - `foEs`
  - `TEC`
- Resumo rapido das melhores bandas para:
  - Local
  - Regional
  - DX
- Regua visual de 0 a 35 MHz com:
  - faixas de radioamadorismo de 160m a 10m;
  - marcadores de `fmin`, `foE`, `foEs`, `foF2` e `MUF`.
- Tabela de condicao por banda de 160m a 6m.
- Cores independentes para cada uso:
  - Local
  - Regional
  - DX

Isso permite ver, por exemplo, uma banda boa para DX mas ruim para contato local, sem pintar a linha inteira com uma unica cor.

## Cores

- Verde: bom.
- Amarelo: razoavel, limite ou monitorar.
- Vermelho: ruim, fechada ou absorvida.
- Cinza: sem dado suficiente.

## Bandas avaliadas

- 160m
- 80m
- 60m
- 40m
- 30m
- 20m
- 17m
- 15m
- 12m
- 10m
- 6m

O 6m aparece na tabela, mas nao aparece na regua de 0 a 35 MHz.

## Como funciona a leitura

O app usa os dados medidos/calculados no arquivo `.SAO`:

- Local: usa principalmente `foF2` e `fmin`.
- Regional: usa uma estimativa simples de MUF para 800 km.
- DX: usa `MUF(3000)`.
- 6m: usa `foEs` como indicio de E esporadica e `MUF(3000)` como referencia rara de F2.

Essa leitura é uma triagem operacional. A decisao real ainda depende de horario, caminho, antena, ruido, potencia, atividade real na banda e clima espacial.

## Fonte dos dados

Os dados sao obtidos dos arquivos `.SAO` publicados pelo INPE/Embrace:

`https://embracedata.inpe.br/ionosonde`

O projeto nao substitui os produtos oficiais do INPE. Ele apenas reorganiza parte dos dados publicos em um formato mais direto para radioamadores.