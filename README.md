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
| **Total Global** | | | **13.325** | Corpus científico completo e particionado. |

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

### Algoritmos e Bibliotecas Utilizadas

* **`unicodedata` (Biblioteca Padrão Python):** Algoritmo de Normalização Canônica NFKC (Unicode Standard Annex #15), realizando a decomposição de compatibilidade seguida pela composição canônica para eliminar artefatos visuais de fontes tipográficas.
* **`re` (Biblioteca Padrão Python):** Autômato determinístico finito de expressões regulares compiladas para varredura e substituição em passada única $O(N)$ por documento.
* **`json` (Biblioteca Padrão Python):** Leitura e escrita atômica em fluxo contínuo (*streaming line-by-line*) sem sobrecarga de memória RAM.

---

## Referências

[1] Kobak, D., González-Márquez, R., Horvát, E. A., & Kapoor, S. (2024). Delving into ChatGPT usage in academic writing through excess vocabulary. *arXiv preprint arXiv:2406.07016*.

[2] Liang, W., Izzo, M. A., Zhang, Y., Leppert, H., Hou, H., Cheng, X., Zou, J., et al. (2024). Monitoring AI-modified text in the scientific literature. *arXiv preprint arXiv:2403.07183*.

[3] Sadasivan, V. S., Kumar, A., Balasubramanian, S., Wang, W., & Feizi, S. (2023). Can AI-Generated Text be Reliably Detected? *arXiv preprint arXiv:2303.11156*.

[4] Tang, X., et al. (2024). AIGT-SignalBench: Disentangling Shortcut Cues from Generalizable Signals in AI-Generated Text Detection. *Findings of the Association for Computational Linguistics (ACL)*.
