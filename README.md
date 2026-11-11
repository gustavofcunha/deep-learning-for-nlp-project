# Detecção e Evolução Temporal de Texto Científico Gerado por IA (2015-2025)

## 1. Coleta de Artigos Científicos

Nesta primeira etapa, coletamos e validamos um corpus de **13.325 artigos científicos** cobrindo 11 anos de publicações (2015 a 2025) em 4 conferências de referência em Inteligência Artificial e Processamento de Linguagem Natural.

### Fontes Oficiais de Coleta

Os artigos foram obtidos exclusivamente a partir de repositórios oficiais de acesso aberto:
* **NeurIPS:** Coletados do repositório oficial de anais [NeurIPS Proceedings](https://proceedings.neurips.cc/) (2015 a 2024) e [OpenReview](https://openreview.net/) para faixas recentes.
* **ACL:** Extraídos da [ACL Anthology](https://aclanthology.org/), biblioteca digital oficial de pesquisa em processamento de linguagem natural.
* **ICML:** Coletados dos volumes anuais do [Proceedings of Machine Learning Research (PMLR)](https://proceedings.mlr.press/).
* **ICLR:** Obtidos via [OpenReview API](https://openreview.net/) (2018 a 2025) e [arXiv](https://arxiv.org/) filtrados por data de submissão para as edições inaugurais (2015 a 2017).

### Técnica de Amostragem e Balanceamento

A amostragem foi estruturada em 44 estratos (4 conferências $\times$ 11 anos) divididos em dois horizontes temporais:

1. **Período Pré-2020 ($\le 2019$):** Representa a linha de base histórica humana anterior aos LLMs conversacionais modernos.
   * **Sementes de IA (`seed_discarded`):** 1.500 resumos humanos utilizados para condicionar a geração sintética na etapa seguinte. Os textos originais são estritamente descartados do treinamento dos classificadores para evitar vazamento.
   * **Treino Humano (`human_ground_truth`):** 1.500 artigos humanos reservados para compor o conjunto supervisionado de modelagem (rótulo 0). Em cada estrato individual, o número de sementes é rigorosamente igual ao número de artigos de treino ($N_{\text{seed}} = N_{\text{human}}$), blindando o classificador contra atalhos de ano ou conferência.
   * **Controle Temporal Cego (`human_temporal_blind`):** 2.462 artigos humanos históricos adicionais reservados para auditar a taxa de falsos positivos em um período com taxa esperada de IA nula.
2. **Período Pós-2020 ($\ge 2020$):** Total de **7.863 artigos** sem rotulação (`longitudinal_unlabeled`), mantidos com aproveitamento total para maximizar a densidade amostral e o poder estatístico na mensuração da infiltração de IA ano a ano.

### Engenharia da Coleta

* **Processamento em Fluxo de Memória:** O download dos PDFs é realizado em buffers de memória (`io.BytesIO`) e processado diretamente pelo PyMuPDF, extraindo apenas Abstract, Introdução e Conclusão sem salvar arquivos PDF pesados no disco.
* **Filtros de Qualidade Textual:** Validação de idioma inglês e contagem mínima de palavras (Abstract $\ge 50$, Introdução $\ge 200$, Conclusão $\ge 50$).
* **Resiliência:** Requisições protegidas por recuo exponencial com jitter e persistência atômica linha a linha em JSONL, permitindo retomada imediata sem refazer downloads.
* **Deduplicação:** Verificação por hash SHA-256 de identificador e URL, resultando em 100% de registros únicos.

### Tabelas de Quantitativos

#### Artigos Coletados por Conferência e Ano

| Conferência | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | $\le 2019$ | $\ge 2020$ | Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NeurIPS** | 293 | 380 | 419 | 466 | 480 | 379 | 379 | 381 | 386 | 388 | 48 | **2.038** | **1.961** | **3.999** |
| **ACL** | 160 | 209 | 175 | 223 | 426 | 340 | 323 | 321 | 352 | 347 | 370 | **1.193** | **2.053** | **3.246** |
| **ICML** | 211 | 248 | 335 | 410 | 440 | 362 | 365 | 361 | 373 | 378 | 106 | **1.644** | **1.945** | **3.589** |
| **ICLR** | 40 | 69 | 105 | 168 | 205 | 200 | 317 | 320 | 346 | 357 | 364 | **587** | **1.904** | **2.491** |
| **TOTAL** | **704** | **906** | **1.034** | **1.267** | **1.551** | **1.281** | **1.384** | **1.383** | **1.457** | **1.470** | **888** | **5.462** | **7.863** | **13.325** |

#### Distribuição por Período e Tipo de Proveniência

| Período Temporal | Grupo de Proveniência (`provenance_type`) | Rótulo Supervisionado | Quantidade | Finalidade no Estudo |
| :--- | :--- | :---: | :---: | :--- |
| **Pré-2020 ($\le 2019$)** | `seed_discarded` | `None` | 1.500 | Resumos reais utilizados para gerar textos sintéticos por LLMs; descartados do treino. |
| **Pré-2020 ($\le 2019$)** | `human_ground_truth` | `0` (Humano) | 1.500 | Componente humano balanceado para treino e validação do classificador supervisionado. |
| **Pré-2020 ($\le 2019$)** | `human_temporal_blind` | `0` (Humano) | 2.462 | Grupo de controle histórico cego para auditar taxa de falsos positivos no pré-LLM. |
| **Pós-2020 ($\ge 2020$)** | `longitudinal_unlabeled` | `None` (Não Rotulado) | 7.863 | Série temporal contemporânea para inferência e análise da prevalência de IA ano a ano. |
| **Pré-2020 ($\le 2019$)** (Espelho IA) | `synthetic_ai` | `1` (IA) | 1.494 | Artigos sintéticos gerados via `Qwen/Qwen2.5-7B-Instruct` a partir das sementes; classe positiva na modelagem supervisionada. |
| **Total Global** | | | **14.819** | Corpus consolidado (13.325 artigos coletados + 1.494 artigos sintéticos gerados por IA). |

---

## 2. Pré-processamento Textual Especializado

Na detecção de autoria científica por modelos neurais, elementos estruturais não linguísticos introduzem atalhos espúrios (*shortcut learning*), levando o classificador a memorizar formatações superficiais em vez de aprender o estilo genuíno da prosa [1, 2, 4]. A Etapa 2 aplica uma esteira determinística de higienização e mascaramento sobre os textos extraídos.

### Procedimentos Executados

1. **Des-hifenização Abrangente:** Reconstituição de palavras partidas por quebra de linha de coluna e hifens ASCII ou Unicode (`\b(\w+)\s*[-‐‑⁃]\s*\n\s*(\w+)\b`).
2. **Normalização Unicode (NFKD + NFKC) e Purga de Diacríticos:** Decomposição canônica para desarmar ligaduras tipográficas (`fi`, `fl`, `ff`, `ffi`), purga de caracteres de controle ASCII (`\x00-\x1f`) e remoção de acentos isolados (`´`, `` ` ``, `ˇ`) para recomposição limpa de nomes próprios de autores [2].
3. **Truncamento de Fronteiras de Seção e Expurgo de Conteúdo Vazado:** Identificação e corte automático de listas bibliográficas (`References`, `Bibliography`, `Works Cited`), apêndices e demonstrações (`Appendix`, `Supplementary Material`, `Proofs`) e declarações institucionais (`Impact Statement`, `Broader Impacts`, `Checklist`). Na introdução, trunca o texto exatamente no limiar da Seção 2 ou subsequentes (ex.: `2. Informal statement of the result`, `Related Work`, `Background`).
4. **Remoção de Pseudocódigo e Algoritmos Estruturados:** Expurgo de caixas flutuantes de pseudocódigo (`Algorithm 1: ... 1: Input: ... 7: until meet stopping criterion`), mantendo menções textuais na prosa.
5. **Expurgo de Afiliações, E-mails e URLs de Rodapé:** Remoção completa de notas de rodapé de autoria (`equal contribution`, `work done while`, `corresponding author`), e-mails e linhas de rodapé contendo links numerados para impedir atalhos de contato humano.
6. **Expurgo Integral de Legendas Multilinha:** Remoção de blocos inteiros de legendas de figuras e tabelas (`Figure X:`, `Table X:`) capturados no fluxo de coluna do PDF.
7. **Remoção de Metadados Editoriais e Títulos Repetidos:** Expurgo de rodapés de anais e conferências (`JMLR: W&CP`, `PMLR`, avisos de copyright institucional), numerações de página isoladas e títulos de artigos replicados no topo de cada página.
8. **Desanexação de Índices de Notas de Rodapé:** Remoção de dígitos numéricos sobrescritos colados ao final de palavras antes de pontuações (`available3` $\rightarrow$ `available`, `toolkit1` $\rightarrow$ `toolkit`) sem afetar termos técnicos legítimos como `arg1` ou `arg2`.
9. **Mascaramento Canônico de Atalhos em Múltiplos Estágios:** Substituição de citações narrativas em texto (ex.: "Cunha et al. (2020)", "Chen and Manning (2014)"), variantes tipográficas e de pontuação (`et. al`, `et.al.`, `etal.`), autores com dígitos colados derivados de índices sobrescritos (`4Nallapati et al.`), nomes fragmentados por OCR (`Saatc i et al.`, `Heikkil a et al.`), citações órfãs não abertas resultantes de quebras de rodapés (`et al., 2006; ...)`), citações parentéticas (ex.: "(Devlin et al., 2019)"), numéricas e chaves alfanuméricas pelo token `[CITE]` [4] (preservando intervalos matemáticos contínuos como `[0, 1]`), colapsando repetições contíguas com ponto e vírgula (`[CITE] ; [CITE]` $\rightarrow$ `[CITE]`).
10. **Mascaramento Avançado de Matemática e Otimização:** Substituição de blocos LaTeX, expressões inline (`$...$`), operadores de otimização (`arg min`, `arg max`), equações em texto simples (`Ax + Bz = c`, `ρ > 0`), letras gregas e operadores matemáticos Unicode pelo token `[MATH]`.
11. **Mascaramento Insensível a Maiúsculas de URLs, DOIs, Domínios Diretos e Reconstituição de Protocolos Quebrados:** Separação prévia de termos ou dígitos colados a protocolos (`start1https://` $\rightarrow$ `start1 https://`), reconciliação de protocolos partidos por diagramação de coluna ou quebra de linha (`https: //`, `http : //`, `https : / /` $\rightarrow$ `https://`), detecção abrangente de links, identificadores DOI (`10.\d{4,9}/\S+`), domínios de repositórios e bases sem protocolo explícito (`github.com/...`, `en.wikipedia.org/...`, `wordnet.princeton.edu`), purga de fragmentos órfãos (`http:`, `https:`, `(https:`, `'http(s)://...'`) com preservação de termos legítimos da prosa técnica (ex.: "HTTP traffic"), eliminação de dígitos numéricos de rodapé antecedentes e colapso de múltiplos tokens `[URL]` contíguos.
12. **Padronização de Marcadores de Tópicos (Bullets):** Normalização de marcadores pontuados (`•`, `*`, `▪`) para hífen simples `- `.
13. **Fusão de Linhas Intra-parágrafo e Preservação Estrutural:** Conversão de quebras físicas de linha de coluna do PDF em espaços contínuos dentro de parágrafos, preservação estrita de quebras duplas de parágrafo (`\n\n`) e itens de listas com marcadores (`- `).

### Execução via Linha de Comando

A esteira opera de forma parametrizada via CLI (`src.preprocessing`), suportando tanto o processamento padrão do corpus humano quanto o pré-processamento de paridade dos artigos sintéticos gerados:

```bash
# Execução padrão (Etapa 2: pré-processamento do corpus coletado)
python3 -m src.preprocessing

# Execução de paridade (Etapa 3.5: pré-processamento do corpus sintético)
python3 -m src.preprocessing -i data/raw/synthetic_ai.jsonl -o data/processed/synthetic_corpus.jsonl
```

### Algoritmos e Bibliotecas Utilizadas

* **`unicodedata` (Biblioteca Padrão Python):** Algoritmo de Normalização Canônica NFKC (Unicode Standard Annex #15), realizando a decomposição de compatibilidade seguida pela composição canônica para eliminar artefatos visuais de fontes tipográficas.
* **`re` (Biblioteca Padrão Python):** Autômato determinístico finito de expressões regulares compiladas para varredura e substituição em passada única $O(N)$ por documento.
* **`json` (Biblioteca Padrão Python):** Leitura e escrita atômica em fluxo contínuo (*streaming line-by-line*) sem sobrecarga de memória RAM.

---

## 3. Geração Sintética e Pré-processamento de Paridade

Para viabilizar o treinamento supervisionado de modelos detectores, é necessário parear os textos humanos pré-2020 com textos científicos sintéticos gerados por modelos de linguagem de última geração.

### Arquitetura de Geração em Duas Etapas

1. **Extração de Fatos Técnicos (Prompt 1):** A partir das 1.500 sementes humanas descartadas (`provenance_type: 'seed_discarded'`), um modelo aberto de alta densidade informacional (`Qwen/Qwen2.5-7B-Instruct`) resume o problema técnico, formulações matemáticas centrais, literatura prévia e conclusões empíricas.
2. **Redação Científica Sintética (Prompt 2):** Com base no sumário factual, o modelo redige seções completas (Abstract, Introdução e Conclusão) espelhando a estrutura acadêmica formal, incorporando formulações em LaTeX, citações bibliográficas e links de repositórios.
3. **Descarte das Sementes Humanas:** Os textos originais das sementes são permanentemente excluídos do treinamento do detector para evitar qualquer vazamento de vocabulário ou tema.

### Pré-processamento de Paridade Científica

O arquivo bruto gerado (`data/raw/synthetic_ai.jsonl`) passa localmente pela mesma esteira determinística de pré-processamento aplicada aos artigos humanos (`src.preprocessing`), gerando o corpus `data/processed/synthetic_corpus.jsonl` com 1.494 artigos rotulados com a classe 1 (IA).

* **Blindagem Idêntica:** Neutralização completa de fórmulas (`[MATH]`), citações (`[CITE]`) e links (`[URL]`), impedindo que o classificador aprenda atalhos espúrios.
* **Recuperação de Metadados:** Reconstituição de conferência, ano de publicação e autores da semente original para viabilizar validação cruzada balanceada por estrato.

---

## 4. Cadernos de Execução e Experimentação

Os experimentos interativos, a geração em larga escala com aceleradores de hardware e a esteira ponta a ponta de modelagem e inferência são organizados no diretório [`src/notebooks/`](src/notebooks/):

1. **[`qwen_synthetic_generation.ipynb`](src/notebooks/qwen_synthetic_generation.ipynb):**  
   Caderno parametrizado para geração em lote dos artigos científicos sintéticos espelhados. Projetado para execução em cluster dual Nvidia Tesla T4 (Kaggle ou Google Colab), orquestrando o modelo `Qwen/Qwen2.5-7B-Instruct` via biblioteca `vLLM` com quantização de 4 bits (AWQ) para respeitar limites de memória VRAM. Realiza a extração factual em duas etapas e armazena os registros brutos em `data/raw/synthetic_ai.jsonl`.

2. **[`end_to_end_pipeline.ipynb`](src/notebooks/end_to_end_pipeline.ipynb):**  
   Caderno principal e entregável do projeto. Centraliza todas as fases empíricas em um fluxo executável único:
   * **Seção 1 (Setup & Environment):** Instalação de bibliotecas, sementes determinísticas (`seed = 42`) e inspeção de aceleração por GPU.
   * **Seção 2 (Data Acquisition & Corpus Overview):** Resolução dinâmica de caminhos (compatível com execução local ou download automático das versões comprimidas `.jsonl.gz` direto do GitHub no Google Colab), carregamento das partições e montagem do conjunto balanceado de 2.988 artigos.
   * **Seção 3 (Linguistic Characterization):** Análise contrastiva quantitativa de métricas textuais (diversidade lexical TTR, densidade de entidades nomeadas e padrões morfossintáticos).
   * **Seção 4 (Supervised Modelling & Optuna Tuning):** Treinamento supervisionado com validação cruzada em 5 folds agrupada por artigo e busca bayesiana de hiperparâmetros com Optuna.
   * **Seção 5 (Longitudinal Temporal Analysis):** Avaliação de infiltração na série histórica 2015-2025 com correção estatística de prevalência (Rogan-Gladen) e intervalos de confiança por bootstrap.

---

## 5. Estrutura do Repositório

```text
Projeto-Final-APPNL/
├── data/
│   ├── processed/          # Conjuntos processados e versões comprimidas (.jsonl.gz)
│   └── raw/                # Dados brutos coletados e saídas brutas do LLM
├── spec/
│   └── plan.md             # Especificação e plano técnico detalhado
├── src/
│   ├── coleta/             # Scripts modulares de coleta via scraping e APIs
│   │   ├── collector.py
│   │   └── utils.py
│   ├── notebooks/          # Cadernos Jupyter de experimentação e modelagem
│   │   ├── end_to_end_pipeline.ipynb
│   │   └── qwen_synthetic_generation.ipynb
│   └── preprocessing/      # Esteira determinística de 13 etapas de limpeza
│       ├── __init__.py
│       ├── __main__.py
│       └── preprocessor.py
├── .gitignore              # Regras de exclusão para arquivos pesados e caches
├── AGENTS.md               # Manual de engenharia e governança de desenvolvimento
└── README.md               # Apresentação do projeto e guia para reprodução
```

---

## Referências

[1] Kobak, D., González-Márquez, R., Horvát, E. A., & Kapoor, S. (2024). Delving into ChatGPT usage in academic writing through excess vocabulary. *arXiv preprint arXiv:2406.07016*.

[2] Liang, W., Izzo, M. A., Zhang, Y., Leppert, H., Hou, H., Cheng, X., Zou, J., et al. (2024). Monitoring AI-modified text in the scientific literature. *arXiv preprint arXiv:2403.07183*.

[3] Sadasivan, V. S., Kumar, A., Balasubramanian, S., Wang, W., & Feizi, S. (2023). Can AI-Generated Text be Reliably Detected? *arXiv preprint arXiv:2303.11156*.

[4] Tang, X., et al. (2024). AIGT-SignalBench: Disentangling Shortcut Cues from Generalizable Signals in AI-Generated Text Detection. *Findings of the Association for Computational Linguistics (ACL)*.
