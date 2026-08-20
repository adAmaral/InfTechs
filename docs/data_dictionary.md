# Dicionário de dados inicial

Este dicionário descreve o esquema proposto para a camada tratada do projeto InfTechs. Os nomes podem ser ajustados após a inspeção dos arquivos oficiais.

| Campo tratado | Origem | Tipo | Regra de tratamento | Uso analítico |
|---|---|---|---|---|
| `product_id` | `parent_asin` | string | Manter como chave do produto-pai | Integração e agregação |
| `variant_id` | `asin` | string | Manter para rastrear variantes | Auditoria |
| `product_title` | `title` | string | Normalizar espaços e Unicode | NLP e identificação |
| `brand` | `details.Brand` ou `store` | string | Padronizar caixa e nulos | Comparação de marcas |
| `component_family` | Regra derivada | categoria | Classificar por vocabulário revisado | Segmentação |
| `price_usd` | `price` | float | Converter para numérico; valores inválidos como nulo | Faixa e associação |
| `average_rating` | `average_rating` | float | Validar intervalo de 1 a 5 | Descrição do item |
| `rating_number` | `rating_number` | integer | Valores negativos como inválidos | Popularidade |
| `review_rating` | `rating` | float | Validar intervalo de 1 a 5 | Alvo e análise |
| `review_title` | `title` da avaliação | string | Normalizar e preservar original em camada bruta | NLP |
| `review_text` | `text` | string | Remover excesso de espaços; registrar vazio | NLP e sentimento |
| `review_timestamp` | `timestamp` | datetime | Converter Unix para UTC | Análise temporal |
| `verified_purchase` | `verified_purchase` | boolean | Normalizar valores booleanos | Confiabilidade percebida |
| `helpful_votes` | `helpful_votes` | integer | Nulos para zero apenas quando documentado | Utilidade da avaliação |
| `features_text` | `features` | string | Concatenar lista com separador | Extração de especificações |
| `description_text` | `description` | string | Concatenar lista e preservar camada original | NLP |
| `categories_path` | `categories` | string | Serializar hierarquia | Classificação |
| `text_length` | Derivado | integer | Contar caracteres ou tokens | Controle de qualidade |
| `sentiment_score` | Derivado | float | Gerar apenas após definir modelo e idioma | Variável explicativa |
| `price_band` | Derivado | categoria | Quantis calculados no treino | Comparação |

## Regras de qualidade

Os registros inválidos serão enviados para uma tabela de rejeições com motivo, linha de origem e arquivo. Nenhum valor será simplesmente descartado sem contagem. As validações mínimas serão: JSON bem formado, presença de `parent_asin` ou `asin`, nota no intervalo esperado, preço não negativo quando informado, timestamp conversível e ausência de duplicidade na chave composta entre produto, usuário, texto e timestamp.

## Particionamento

A camada Parquet será particionada por `component_family` e ano de `review_timestamp`. Os dados brutos não serão carregados integralmente em memória. A leitura ocorrerá em lotes, com amostragem determinística por hash do identificador do produto até que o tamanho do corpus tratado esteja entre 800 MB e 1,2 GB.
