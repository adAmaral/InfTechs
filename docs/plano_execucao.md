# Plano técnico de execução

## Etapa 1 — Aquisição

Baixar somente os arquivos oficiais de avaliações e metadados da categoria `Electronics` do Amazon Reviews 2023, registrando a data de acesso, a URL da página de origem, o tamanho do arquivo e o hash SHA-256. Os arquivos brutos ficarão fora do Git por causa do volume.

## Etapa 2 — Inspeção

Ler uma amostra em streaming, contar linhas, identificar campos, medir nulos e listar os valores mais frequentes de `main_category`, `store`, `Brand` e termos de título. Essa inspeção definirá a primeira versão do vocabulário de peças.

## Etapa 3 — Filtragem temática

Aplicar regras versionadas para famílias como `cpu`, `gpu`, `motherboard`, `ram`, `storage`, `power_supply`, `case`, `cooling` e `peripherals`. Produtos sem evidência suficiente serão marcados como `review_required`, em vez de serem eliminados silenciosamente.

## Etapa 4 — Integração e limpeza

Relacionar avaliações e metadados por `parent_asin`, preservar `asin`, normalizar datas e números, tratar listas e dicionários, deduplicar e gerar uma tabela de rejeições. Os dados serão convertidos para Parquet para reduzir custo de leitura e permitir particionamento.

## Etapa 5 — Controle de escala

Ordenar os registros por uma função hash estável de `parent_asin` e selecionar produtos até o corpus atingir a faixa de 800 MB a 1,2 GB. A seleção será repetível com uma semente e uma versão do filtro. O tamanho final será medido tanto em JSONL quanto em Parquet, pois a compressão altera o espaço ocupado.

## Etapa 6 — Análise e modelagem

Produzir estatísticas por família, marca e faixa de preço; comparar nota média e volume de avaliações; analisar termos associados a avaliações positivas e negativas; e treinar um baseline. A validação será temporal para tarefas preditivas e estratificada por produto ou usuário quando o objetivo for classificação.

## Critérios de conclusão da primeira versão

A primeira versão será considerada pronta quando houver: fonte documentada; corpus entre 800 MB e 1,2 GB; dicionário de dados; relatório de qualidade; pelo menos três gráficos exploratórios; baseline reproduzível; e registro do commit do código usado para gerar a camada tratada.
