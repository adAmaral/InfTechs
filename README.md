# InfTechs

## Proposta de projeto: análise de peças de computadores em dados de comércio eletrônico

**Projeto:** InfTechs  
**Tema:** peças e componentes de computadores  
**Metodologia:** CRISP-DM, com correspondência conceitual ao KDD  
**Versão:** proposta inicial para apresentação da ideia

## 1. Pergunta de negócio e de pesquisa

A pergunta central do InfTechs é: **quais características técnicas, sinais de qualidade percebida e condições de mercado ajudam a explicar a avaliação e a atratividade de peças de computador, e é possível utilizar esses dados para recomendar produtos ou estimar a avaliação esperada de um componente?**

A investigação pretende descobrir se atributos como marca, preço, categoria, quantidade de avaliações, nota média, descrição técnica, recência da avaliação, compra verificada e menções positivas ou negativas nas resenhas estão associados à percepção de qualidade dos consumidores. Em uma etapa posterior, o projeto poderá comparar modelos de classificação, regressão ou recomendação para apoiar a escolha de componentes.

A pergunta foi formulada de maneira suficientemente ampla para permitir dois produtos finais complementares. O primeiro será um estudo analítico, com estatísticas comparativas entre categorias de componentes e identificação de padrões de preço, avaliação e popularidade. O segundo poderá ser um protótipo de Machine Learning, com API ou notebook de consulta, capaz de estimar a faixa de avaliação de um produto ou retornar itens semelhantes.

## 2. Motivação e relevância

Mercados de componentes de computador reúnem produtos com alta variedade técnica, forte diferenciação entre marcas e grande quantidade de avaliações textuais. Uma comparação baseada apenas no preço pode favorecer produtos baratos, mas não necessariamente confiáveis; uma comparação baseada apenas na nota média pode ignorar o número de avaliações, a data das compras e a composição dos usuários. O InfTechs pretende transformar essas informações heterogêneas em indicadores comparáveis.

O projeto também é adequado para uma disciplina de dados porque combina dados estruturados e não estruturados. O preço, a nota e a quantidade de avaliações permitem análise estatística, enquanto título, características, descrição e texto das resenhas exigem processamento de linguagem natural. O volume da fonte permite demonstrar técnicas de processamento por lotes, particionamento e armazenamento em formatos analíticos sem depender de carregar todo o conjunto na memória.

## 3. Fonte e estratégia do dataset

A fonte principal proposta é o **Amazon Reviews 2023**, coletado pelo McAuley Lab. A página oficial informa 571,54 milhões de avaliações em 33 domínios, com interações entre maio de 1996 e setembro de 2023, além de metadados de produtos, preços, descrições, categorias, imagens e links entre itens [1]. A categoria **Electronics** possui, segundo a mesma fonte, 43,9 milhões de avaliações, 18,3 milhões de usuários e 1,6 milhão de itens associados a avaliações [1].

Como o objetivo didático é trabalhar com aproximadamente 1 GB, não será necessário baixar todo o domínio Electronics. A proposta é baixar os arquivos de avaliações e metadados da categoria, filtrar registros relacionados a peças e montar um corpus reprodutível por amostragem determinística. O corpus de trabalho terá entre **800 MB e 1,2 GB em JSONL/Parquet**, com a meta operacional de aproximadamente 1 GB. A fonte bruta continuará documentada separadamente, e o subconjunto será produzido por uma regra explícita, evitando uma seleção manual não reproduzível.

A filtragem inicial utilizará título, categorias, marca, características e descrição para identificar termos relacionados a processadores, placas de vídeo, placas-mãe, memória RAM, armazenamento, fontes, gabinetes, refrigeração e periféricos. A lista de termos será revisada após uma amostra exploratória, pois o domínio Electronics também contém celulares, câmeras, televisores e outros produtos que não fazem parte do recorte principal.

| Camada | Conteúdo | Finalidade | Escala esperada |
|---|---|---|---|
| Fonte bruta | Avaliações e metadados da categoria Electronics | Preservar a origem e permitir reprocessamento | Muito superior a 1 GB |
| Subconjunto filtrado | Produtos e avaliações associados a peças de computador | Análise temática do InfTechs | Definido por regra de filtragem |
| Corpus de trabalho | Registros JSONL/Parquet amostrados por hash de `parent_asin` | Garantir processamento viável e próximo de 1 GB | 0,8–1,2 GB |
| Tabelas analíticas | Produto, avaliação, categoria, marca e agregações temporais | Modelagem, visualização e API | Menor que a fonte bruta |

A versão anterior do repositório UCSD também pode ser usada como plano alternativo ou conjunto de validação histórica. Ela reúne avaliações, metadados, preços, marcas, categorias e relações entre produtos, e disponibiliza arquivos por categoria [2] [3]. Essa alternativa é útil para testes rápidos e reprodução de trabalhos anteriores, mas o Amazon Reviews 2023 será a fonte principal por ser mais recente e mais rica.

## 4. Mapeamento inicial dos dados

Os arquivos da fonte são registros **JSONL**, isto é, um objeto JSON por linha. Os dados de avaliação incluem `rating`, `title`, `text`, `asin`, `parent_asin`, `user_id`, `timestamp`, `verified_purchase` e `helpful_votes`. Os metadados dos itens incluem `main_category`, `title`, `average_rating`, `rating_number`, `features`, `description`, `price`, `store`, `categories`, `details` e `parent_asin` [1].

A chave de integração recomendada é `parent_asin`, porque variantes de cor, tamanho ou estilo podem compartilhar o mesmo produto-pai. O identificador `asin` será mantido para rastrear a variante original, mas as agregações de produto devem ser avaliadas preferencialmente no nível de `parent_asin`.

| Entidade | Campos principais | Tipo inicial | Tratamento previsto |
|---|---|---|---|
| Produto | `parent_asin`, `title`, `price`, `average_rating`, `rating_number`, `store`, `details` | JSON, texto, numérico e dicionário | Normalizar nomes, preço, marca, categoria e atributos técnicos |
| Avaliação | `asin`, `parent_asin`, `user_id`, `rating`, `title`, `text`, `timestamp`, `verified_purchase`, `helpful_votes` | JSON, texto, data, booleano e numérico | Remover duplicatas, converter datas e normalizar texto |
| Categoria | `main_category`, `categories` | Texto e lista hierárquica | Mapear para famílias de componentes |
| Características | `features`, `description`, `details` | Listas e dicionários | Explodir campos, extrair unidades e criar variáveis técnicas |
| Relação | `bought_together` e links relacionados, quando disponíveis | Lista de identificadores | Construir grafo opcional de coocorrência e recomendação |

## 5. Desafios técnicos e esforço esperado

O maior esforço deverá ocorrer na **preparação dos dados**, e não no treinamento do primeiro modelo. Os arquivos JSONL têm campos aninhados, listas de características, dicionários de detalhes e texto livre. Será necessário ler os arquivos em fluxo ou em lotes, validar linhas malformadas, registrar erros e evitar a conversão integral para uma estrutura que exceda a memória disponível.

Outro desafio é a definição do universo de “peças de computador”. A categoria Electronics é ampla, de modo que um filtro por palavras pode gerar falsos positivos e falsos negativos. O projeto deverá manter uma tabela de termos, regras e exemplos revisados manualmente. Também será necessário separar produtos completos, acessórios e componentes, bem como tratar variantes que compartilham `parent_asin`.

Os preços não devem ser interpretados como uma série temporal completa: na fonte de metadados, o campo `price` representa o preço disponível no momento da coleta do produto, enquanto o tempo está detalhado nas interações de avaliação [1]. Assim, o projeto poderá estudar associação entre preço observado e avaliações, mas não deverá afirmar que possui histórico diário de preços sem uma fonte adicional de snapshots. Caso a equipe queira previsão de preços, deverá complementar o corpus com coleta periódica autorizada ou uma base histórica específica.

## 6. Fluxo metodológico baseado no CRISP-DM

### 6.1 Compreensão do negócio

O objetivo é apoiar a comparação de peças de computador e compreender quais sinais estão associados à qualidade percebida. O critério de sucesso inicial será produzir uma base documentada, reproduzível e suficientemente grande para gerar comparações por categoria, marca e faixa de preço. Para o modelo, serão consideradas metas como desempenho superior a um baseline simples e interpretação dos fatores mais relevantes.

### 6.2 Compreensão dos dados

Nesta fase serão baixados os arquivos oficiais, catalogados os tamanhos e formatos e examinadas amostras por categoria. A equipe medirá valores ausentes, duplicidades, cardinalidade de produtos, distribuição de notas e cobertura de preços. Também será feita uma análise exploratória para verificar se os termos de peças selecionam efetivamente o domínio de interesse.

### 6.3 Preparação dos dados

A preparação compreenderá leitura em streaming, validação de JSON, deduplicação por identificador e texto, tratamento de nulos, conversão de timestamps, padronização de moeda e unidades, normalização textual, integração entre avaliações e metadados e criação do corpus de aproximadamente 1 GB. O resultado será salvo preferencialmente em Parquet particionado por família de componente e ano, acompanhado de um dicionário de dados.

As variáveis derivadas incluirão faixa de preço, idade da avaliação, tamanho do texto, polaridade ou sentimento, proporção de compras verificadas, taxa de votos úteis, densidade de atributos técnicos e indicadores de popularidade. Para evitar vazamento de informação, a avaliação do produto não deverá ser calculada usando o próprio registro que está sendo previsto.

### 6.4 Modelagem

O primeiro modelo será um baseline interpretável, como regressão logística para classificar avaliação positiva e regressão linear ou árvore de decisão para estimar uma nota agregada. Em seguida, serão comparados modelos como Random Forest, Gradient Boosting e, se o volume computacional permitir, um modelo textual baseado em TF-IDF. Para recomendação, a equipe poderá utilizar similaridade de cosseno entre vetores de características e texto.

A divisão será temporal quando a tarefa envolver previsão: avaliações mais antigas serão usadas no treinamento e as mais recentes no teste. Para classificação sem horizonte temporal, será utilizada divisão estratificada por produto ou usuário, evitando que variantes do mesmo produto apareçam de forma indevida nos conjuntos de treino e teste.

### 6.5 Avaliação

A avaliação combinará métricas técnicas e utilidade prática. Para classificação serão usadas acurácia balanceada, precisão, revocação, F1 e matriz de confusão. Para regressão serão usadas MAE e RMSE. Para recomendação serão usadas Precision@K, Recall@K e NDCG@K. A equipe também verificará desempenho por família de componente, faixa de preço e quantidade de avaliações, pois um resultado médio pode esconder desigualdades entre segmentos.

A avaliação final responderá à pergunta original: os atributos disponíveis realmente ajudam a comparar os componentes? O modelo será considerado útil apenas se superar o baseline, apresentar desempenho consistente em categorias distintas e permitir interpretação dos fatores mais importantes.

### 6.6 Implantação

O produto mínimo será um relatório ou dashboard com comparações de preço, nota, popularidade e sentimento. Como extensão, será disponibilizada uma API que recebe identificadores ou atributos de um componente e retorna estatísticas, previsão ou produtos semelhantes. A implantação deverá incluir versionamento do dataset processado, registro da versão do código, documentação de limitações e monitoramento de mudanças na distribuição dos dados.

A escolha do CRISP-DM é coerente com as referências fornecidas porque a metodologia conecta a compreensão do problema, a compreensão e preparação dos dados, a modelagem, a avaliação e a disponibilização do conhecimento. O KDD será utilizado como referência conceitual para explicar a transformação de dados brutos em padrões interpretáveis; o CRISP-DM será o roteiro operacional do projeto [4] [5].

## 7. Entregas previstas

| Entrega | Descrição | Evidência de conclusão |
|---|---|---|
| Documento de proposta | Pergunta, objetivos, fonte, escopo e metodologia | Markdown versionado |
| Dicionário de dados | Campos, tipos, regras e transformações | Tabela de dados documentada |
| Pipeline de preparação | Download controlado, filtragem, limpeza e particionamento | Código reproduzível |
| Análise exploratória | Estatísticas, gráficos e comparação entre componentes | Notebook ou relatório |
| Modelo inicial | Baseline e modelo comparativo | Métricas e matriz de erros |
| Produto final | Dashboard, API ou relatório analítico | Demonstração e documentação |

## 8. Limitações, ética e reprodutibilidade

A base representa avaliações de uma plataforma específica e não deve ser tratada como uma pesquisa probabilística de todos os consumidores. O preço observado pode não ser atual, a cobertura das avaliações é desigual e o texto pode conter linguagem subjetiva. Identificadores de usuários serão tratados como chaves técnicas, sem tentativa de reidentificação ou análise de atributos pessoais.

A equipe deve respeitar as condições de uso e a documentação da fonte, citar os autores e evitar redistribuir dados brutos quando isso não for permitido. O repositório deverá armazenar código, esquemas, amostras pequenas e hashes, mas não necessariamente os arquivos brutos de grande porte. A extração deve ser feita de fontes públicas e documentadas, sem contornar mecanismos de autenticação ou restrições técnicas.

## Referências

[1]: https://amazon-reviews-2023.github.io/ "Amazon Reviews'23 — McAuley Lab"

[2]: https://cseweb.ucsd.edu/~jmcauley/datasets/amazon/links.html "Amazon product data — Julian McAuley, UCSD"

[3]: https://snap.stanford.edu/data/amazon/productGraph/ "Amazon product data — Stanford Network Analysis Project"

[4]: https://www.datascience-pm.com/crisp-dm-2/ "What is CRISP-DM? — Data Science PM"

[5]: https://arxiv.org/abs/2403.03952 "Bridging Language and Items for Retrieval and Recommendation — Hou et al."

[6]: https://github.com/hyp1231/AmazonReviews2023 "Repositório do Amazon Reviews 2023"

## Referências compartilhadas pela disciplina

- Azevedo, Ana; Santos, Manuel Filipe. *KDD, SEMMA and CRISP-DM: A Parallel Overview*. IADIS, 2008. Arquivo compartilhado no projeto.
- Ferreira, Júlio César; Rosa, Carla Regina Mazia; Steiner, Maria Teresinha Ars. *Knowledge Discovery in Database e Data Mining: uma contribuição bibliométrica*. ENEGEP, 2018. Arquivo compartilhado no projeto.

## 9. Landing page pública e atualização dos relatórios

O InfTechs passou a incluir uma landing page pública de relatórios analíticos. A interface apresenta indicadores por família de componente, gráficos de notas e volume de avaliações, tabela filtrável de peças equivalentes e comparação entre preço antigo e preço atual quando existem snapshots históricos do mesmo produto.

A atualização é organizada em snapshots versionados. Cada snapshot registra a versão do dataset, a fonte, a data de geração, a quantidade de produtos e avaliações processados, as métricas por família e as comparações de produtos pareados. Um job periódico reprocessa o artefato analítico publicado pelo pipeline e grava uma nova versão no banco de dados, permitindo acompanhar mudanças entre execuções.

A fonte continua sendo explicitamente o **Amazon Reviews 2023**. A comparação de preços só pode ser considerada temporal quando há pelo menos duas observações do mesmo produto ou de uma equivalência definida por família e marca. O campo de preço isolado da fonte é um snapshot e não representa, sozinho, um histórico de inflação. Por isso, o painel usa a expressão **variação de preço observada** ou **estimativa de inflação sobre os produtos pareados**, sem apresentá-la como índice oficial de inflação.

A landing page segue o CRISP-DM: compreensão do negócio para definir a comparação; compreensão dos dados para mapear avaliações e metadados; preparação para limpar e parear produtos; modelagem para calcular métricas; avaliação para verificar consistência; e implantação para disponibilizar os relatórios públicos. Os documentos, o pipeline e os snapshots devem ser versionados com a data e a versão do dataset usada em cada atualização.
