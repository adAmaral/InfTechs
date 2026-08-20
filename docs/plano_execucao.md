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

## Etapa 7 — Publicação dos relatórios

A camada final do InfTechs será uma landing page pública construída como dashboard analítico. Ela exibirá métricas por família, evolução temporal das avaliações, preço médio observado e uma tabela de equivalências com filtros por família, marca e faixa de preço.

## Etapa 8 — Pareamento e estimativa de inflação observada

Para comparar preços antigos e recentes, os produtos serão pareados por identificador do produto quando possível. Quando o identificador não estiver disponível em todos os snapshots, será usada uma chave composta auditável com família, marca e atributos técnicos normalizados. A variação será calculada pela fórmula `((preço atual - preço antigo) / preço antigo) × 100`. A média ou mediana das variações dos itens pareados será apresentada como estimativa de inflação observada sobre os produtos, e não como índice oficial de inflação.

## Etapa 9 — Snapshots e atualização periódica

Cada processamento gerará um snapshot contendo a versão do dataset, data de geração, contagens, métricas por família e comparações de produtos. O job periódico validará um artefato JSON produzido pelo pipeline, persistirá uma nova versão no banco e deixará as versões anteriores disponíveis para auditoria. A landing page sempre consultará o snapshot mais recente com status `ready`.

## Etapa 10 — Governança da atualização

A atualização automática deverá registrar a origem `Amazon Reviews 2023`, o hash ou identificador do lote, o período coberto e as limitações de preço. Caso não existam snapshots históricos suficientes, o painel deverá informar que a comparação temporal está indisponível, sem preencher valores estimados artificialmente.

## Etapa 11 — Persistência das observações históricas

Além do artefato analítico externo, o sistema web mantém uma tabela de observações históricas de preço. O pipeline pode inserir registros com versão do dataset, produto, família, marca, data de observação e preço. O job periódico usa essas observações persistidas como fonte principal quando a URL de relatório não está configurada, calcula os pares antigo–atual e grava o snapshot de forma idempotente por `dataset_version`.
