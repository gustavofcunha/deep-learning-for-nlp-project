# Plano de Implementação Técnico

## Visão Geral das Etapas e Quadro de Status

| Etapa | Descrição Sintética | Módulo / Script | Artefatos Produzidos | Status |
| :--- | :--- | :--- | :--- | :---: |
| **1. Coleta e Particionamento** | Extração de Abstract, Introdução e Conclusão de 13.325 artigos (ACL, NeurIPS, ICML, ICLR 2015-2025) com amostragem estratificada. | `src.coleta` | `data/raw/collected_corpus.jsonl` (13.325 tuplas) | **CONCLUÍDA** |
| **2. Pré-processamento Especializado** | Blindagem contra atalhos (13 etapas: NFKC, des-hifenização, corte de seções, mascaramento `[CITE]`, `[MATH]`, `[URL]`). | `src.preprocessing` | `data/processed/preprocessed_corpus.jsonl` (13.325 tuplas limpas) | **CONCLUÍDA** |
| **3. Geração Sintética e Paridade** | Geração via Qwen 2.5 7B em Kaggle dual T4 + pré-processamento de paridade local e recuperação de metadados. | `data/raw/synthetic_ai.jsonl` + `src.preprocessing` | `data/processed/synthetic_corpus.jsonl` (1.494 tuplas com rótulo 1) | **CONCLUÍDA** |
| **4. Caracterização Linguística** | Análise contrastiva quantitativa (diversidade lexical TTR, morfossintaxe spaCy, densidade NER e n-gramas discriminantes). | `src/features/linguistic_analyzer.py` | Métricas textuais, testes de significância estatística e gráficos de densidade | **PENDENTE** |
| **5. Modelagem e Otimização Optuna** | Fine-tuning de SciBERT / DeBERTa-v3 sobre 2.988 artigos balanceados com 5-fold CV agrupado por `paper_id` e teste cego. | `src/models/trainer.py` | Checkpoint calibrado, relatório de métricas e matriz de confusão | **PENDENTE** |
| **6. Análise Longitudinal Temporal** | Inferência na série temporal 2015-2025 (5.800 artigos), correção de prevalência Rogan-Gladen e bootstrap 95%. | `src/evaluation/longitudinal_analyzer.py` | Série temporal ajustada, curvas de prevalência e intervalos de confiança | **PENDENTE** |
| **7. Notebook Integrado** | Consolidação do fluxo em caderno Jupyter com numeração hierárquica e validação de sintaxe. | `src/pipeline_completo.ipynb` | Caderno executável e auditável | **PENDENTE** |

---

## 1. Coleta, Organização e Armazenamento [CONCLUÍDA]

### 1.1 Decisão Arquitetural: Script vs. Notebook com GPU
* **Decisão:** A coleta é implementada como script Python modular (`src/data/collector.py`) executado em CPU local ou em nuvem sem GPU.
* **Justificativa:** Coleta de dados e parsing de PDFs são operações limitadas por rede e processamento de texto (I/O bound). Executar essa etapa em ambientes com GPU ativa (Kaggle/Colab) desperdiça cotas semanais de GPU e sofre risco de desconexão por inatividade. O script gera diretamente os arquivos JSONL leves (~80 a 120 MB para 8.800 artigos), que são consumidos sem atrito pelas etapas subsequentes.

### 1.2 Fontes de Coleta por Conferência
* **ACL (2015-2025):** Metadados e textos extraídos via repositório oficial da ACL Anthology (biblioteca `acl-anthology` ou dumps TEI-XML) com links diretos para PDFs de acesso aberto.
* **NeurIPS (2015-2025):** Anais de `proceedings.neurips.cc` complementados por OpenReview API (edições recentes) e OpenAlex API.
* **ICML (2015-2025):** Proceedings do PMLR (Proceedings of Machine Learning Research) e OpenReview API.
* **ICLR (2015-2025):** OpenReview API (`openreview-py`) para edições 2018-2025; arXiv / OpenAlex API para edições 2015-2017.

### 1.3 Algoritmo de Amostragem Estratificada
* **Entrada:** Catálogo completo de artigos aceitos em cada par `(conferência, ano)`.
* **Filtros de Qualidade Pré-Amostragem:**
  * Pertencimento à trilha principal (*main track*).
  * Exclusão de workshops, tutoriais, demos e erratas.
  * Presença comprovada das três seções textuais: Abstract $\ge 50$ palavras, Introdução $\ge 200$ palavras, Conclusão $\ge 80$ palavras.
  * Confirmação de idioma inglês via `fasttext` ou `langdetect` com escore $\ge 0.98$.
* **Sorteio:** Amostragem aleatória simples uniforme sem reposição com `seed = 42`.
  * **Pré-2020 (2015-2019, 20 estratos):** até 350 artigos por estrato = 7.000 artigos.
    * 75 por estrato $\times$ 20 = 1.500 sementes ($S_{\text{seed}}$).
    * 75 por estrato $\times$ 20 = 1.500 controle humano para modelagem ($S_{\text{human}}$).
    * 200 por estrato $\times$ 20 = 4.000 controle humano blindado para análise temporal ($S_{\text{temporal}}$).
  * **Pós-2020 (2020-2025, 24 estratos):** 200 artigos por estrato = 4.800 artigos para análise temporal (800 por ano).
* **Volume Global Coletado:** 11.800 artigos ($7.000 + 4.800$).
* **Saída:** Arquivo bruto unificado `data/raw/collected_corpus.jsonl`.

### 1.4 Políticas de Acesso, Taxas Limite (Rate Limits) e Etiqueta por Fonte
Para garantir conformidade com os termos de serviço e evitar bloqueios de IP (HTTP 429 / Too Many Requests):
1. **OpenReview API (`openreview-py` v2):**
   * *Endpoint:* `api2.openreview.net`.
   * *Políticas e Limites:* O cliente oficial `openreview-py` possui configuração nativa de retentativa em nível de transporte (`urllib3.util.retry.Retry`) para códigos HTTP 429, 500, 502, 503 e 504, respeitando o cabeçalho `Retry-After`.
   * *Prática de Coleta:* Realizar consultas em lote via `client.get_all_notes` para puxar os metadados de uma edição inteira em uma única sessão paginada. Para o download dos 200 PDFs selecionados, impor intervalo de 0.5 a 1.0 segundo entre requisições.
2. **ACL Anthology (`aclanthology.org`):**
   * *Metadados:* Utilização do repositório/dump oficial (`acl-org/acl-anthology` no GitHub ou pacote Python `acl-anthology-py`), que fornece os metadados em XML/BibTeX localmente, consumindo zero chamadas de API externa para descoberta de artigos.
   * *Download de PDFs:* Acesso aos PDFs com cabeçalho `User-Agent` institucional identificado, no máximo 2 requisições concorrentes e atraso de 0.5 segundo entre downloads.
3. **PMLR (ICML) e NeurIPS Proceedings (`proceedings.neurips.cc`):**
   * *Estratégia:* A página índice de cada volume anual (ex: PMLR volume 119 para ICML 2020) é requisitada uma única vez para mapeamento completo de títulos e links. O download dos 200 PDFs sorteados opera com intervalo de cortesia de 0.5 segundo por artigo.
4. **OpenAlex API (Fallback Institucional):**
   * *Política Atual:* Uso de chave gratuita de API (*API Key*), que eleva o teto diário para 100.000 créditos (lookups individuais custam 0 créditos) com velocidade máxima de 100 requisições por segundo.
   * *Prática:* Paginação estruturada com `per_page=100`, filtro com operador OR (`|`) e inclusão de e-mail institucional no cabeçalho `User-Agent`.

### 1.5 Protocolo de Resiliência para Execução Noturna Ininterrupta
Para viabilizar a execução local autônoma e segura ao longo de uma noite (duração de 2 a 3 horas):
1. **Persistência Imediata e Retomada Automática (*Checkpoint / Resume*):**
   * Cada artigo coletado e validado é gravado imediatamente com `append` no arquivo `data/raw/collected_corpus.jsonl`.
   * Um índice em memória de `paper_id` já coletados é verificado antes de qualquer requisição. Se houver queda de conexão ou reinicialização, o script recomeça instantaneamente a partir do ponto exato onde parou, sem refazer downloads prévios.
2. **Recuo Exponencial com Jitter (*Exponential Backoff*):**
   * Qualquer falha transitória de rede (Timeout, ConnectionReset ou HTTP 429/503) aciona tentativa automática com tempo de espera crescente:
     $$t_{\text{espera}} = \min(60, 2^{\text{tentativa}} + \text{jitter}(0, 1))$$
   * Limite de 5 tentativas por documento. Em caso de falha persistente, o erro é catalogado em `data/raw/failed_downloads.log` e o pipeline segue para o próximo artigo sem interromper a execução global.
3. **Processamento em Fluxo (*Streaming Memory Pipeline*):**
   * Cada PDF é baixado em buffer de memória (`io.BytesIO`), processado instantaneamente pelo PyMuPDF para extração das três seções, persistido no arquivo JSONL e liberado da memória RAM.
   * Essa prática evita o acúmulo de dezenas de gigabytes de arquivos temporários, mantendo o consumo total de armazenamento do projeto abaixo de 100 MB no SSD.
4. **Gerenciamento de Energia do Sistema Operacional:**
   * Desativação da suspensão automática por inatividade no sistema operacional durante a execução, permitindo o desligamento da tela enquanto a CPU mantém o script ativo.

---

## 2. Pré-processamento Textual Especializado [CONCLUÍDA]

### 2.1 Justificativa Baseada na Literatura
Na detecção de autoria científica (Kobak et al., 2024; Liang et al., 2024), elementos estruturais não linguísticos causam atalhos espúrios (*shortcut learning*):
* **Citações bibliográficas:** Autores humanos citam trabalhos reais de anos anteriores com formatos canônicos, enquanto LLMs alucinam chaves de citação ou adotam sintaxes uniformes.
* **Fórmulas matemáticas:** Sintaxe LaTeX gera ruído severo de tokenização e anomalias de perplexidade que não representam o estilo da prosa.
* **Cabeçalhos de conferência:** PDFs contêm notas de rodapé ou cabeçalhos com o nome da conferência e o ano (ex: "ICLR 2017"), vazando o ano de publicação para o classificador.
* **Notas de Afiliação e E-mails de Autoria:** E-mails institucionais e notas de rodapé de afiliação (ex: `*Equal contribution`, `†Work done while at...`, `liuzy@tsinghua.edu.cn`) presentes na primeira página humana não existem em textos sintéticos gerados por LLM.
* **Legendas de Figuras e Tabelas (Captions):** Textos extraídos de PDFs com duas colunas frequentemente intercalam legendas (`Figure 1: ...`, `Table 2: ...`) no meio do fluxo de texto da introdução. Textos gerados por LLM a partir de resumos não incluem legendas embutidas. A literatura recomenda o expurgo completo dessas legendas para evitar atalhos superficiais.
* **Ligaduras Tipográficas do PDF:** Caracteres compostos em tipografia LaTeX (como `fi`, `fl`, `ff`, `ffi`) geram tokens desconhecidos (`[UNK]`) ou fragmentações anômalas em tokenizers padrão caso não sejam normalizados para a forma canônica NFKC.
* **Marcadores de Tópicos e Itens (Bullets):** Divergências na representação de bullets Unicode (`•`, `\u25cf`, `-`, `*`) podem criar correlações superficiais exploráveis por redes neurais.

### 2.2 Pipeline de Limpeza e Normalização
O módulo `src/preprocessing/preprocessor.py` executa a seguinte cadeia determinística:
1. **Des-hifenização Abrangente:** Reconstituição de palavras partidas ao final de linha por hifens ASCII ou Unicode (`-‐‑⁃`) com tolerância a espaços marginais (`\b(\w+)\s*[-‐‑⁃]\s*\n\s*(\w+)\b` $\rightarrow$ `$1$2`).
2. **Normalização Canônica Unicode (NFKD + NFKC) e Purga de Diacríticos Isolados:** Decomposição canônica NFKD seguida de recomposição NFKC, eliminação de caracteres de controle ASCII (`\x00-\x1f`), remoção de acentos tipográficos isolados (`´`, `` ` ``, `ˇ`) para recomposição limpa de nomes próprios com diacríticos (ex.: `Guzm´an` $\rightarrow$ `Guzman`, `Kol´aˇr` $\rightarrow$ `Kolar`), desarme de ligaduras tipográficas (`fi`, `fl`, `ff`, `ffi`, `ffl`) e conversão de aspas e travessões em formas padrão.
3. **Truncamento de Fronteiras de Seção e Expurgo de Conteúdo Vazado (`sanitize_section_boundaries`):**
   * **Corte de Seções Finais e Metadados Pós-Artigo:** Identificação e truncamento imediato de listas bibliográficas completas (`References`, `Bibliography`, `Literature Cited`, `Works Cited`), apêndices e demonstrações matemáticas (`Appendix`, `Appendices`, `Supplementary Material`, `Technical Appendix`, `Proofs`) e declarações institucionais pós-texto (`Impact Statement`, `Broader Impacts`, `Ethical Considerations`, `Checklist`).
   * **Detecção de Transição para o Corpo do Artigo:** Truncamento da introdução no limiar exato em que ocorre a transição para a Seção 2 ou subsequentes (detectando cabeçalhos numerados como `2. Informal statement of the result`, seções canônicas como `Related Work`, `Background`, `Methodology`, ou títulos em Title Case após 200 palavras de preâmbulo).
4. **Remoção de Pseudocódigo e Algoritmos Estruturados (`remove_algorithm_pseudocode`):** Expurgo de caixas flutuantes de pseudocódigo (`Algorithm 1: ... 1: Input: ... 7: until meet stopping criterion`) capturadas no fluxo de coluna do PDF, preservando referências textuais legítimas na prosa analítica (ex.: "As described in Algorithm 2").
5. **Expurgo de Notas de Afiliação, E-mails e URLs de Rodapé:** Remoção de e-mails (`\b[\w\.-]+@[\w\.-]+\.\w+\b`), declarações de rodapé de autoria (`equal contribution`, `work done while`, `corresponding author`, `electronic address`) e linhas residuais de rodapé contendo URLs associadas a índices numéricos (`^\s*\d+[\.:\s]*https?://`).
6. **Expurgo Integral de Legendas Multilinha de Figuras e Tabelas (Captions):** Remoção completa de blocos inteiros de legendas de figuras e tabelas que ocupam várias linhas no fluxo do PDF (`(?im)^\s*(?:figure|fig\.|table|tab\.)\s+\d+[:\.][\s\S]*?(?:\.\s*(?:\n|$)|(?=\n\s*\n|\Z))`), impedindo que resíduos visuais permaneçam no texto.
7. **Remoção de Cabeçalhos de Conferência, Rodapés Editoriais e Títulos Repetidos:** Expurgo de avisos editoriais e de direitos autorais de periódicos e anais (`JMLR: W&CP`, `PMLR`, `Learning, Lille, France`, `Copyright \d{4} by the author(s)`), notas de submissão ("Under review as a conference paper"), numerações de página isoladas, e títulos de artigos replicados no topo de cada página como cabeçalho de corrida.
8. **Desanexação de Índices de Notas de Rodapé (`clean_footnotes`):** Remoção de dígitos numéricos sobrescritos grudados no final de vocábulos regulares antes de pontuações (`\b([a-z]{4,})[1-9](?=[,\.\s\)]|$)`), restaurando palavras como `available3` $\rightarrow$ `available` e `toolkit1` $\rightarrow$ `toolkit` sem afetar termos técnicos legítimos como `arg1` ou `arg2`.
9. **Mascaramento Canônico de Citações em Múltiplos Estágios e Colapso de Repetições:**
   * **Citações Narrativas (`\citet`):** Mascaramento de variantes autor-ano em texto (`Sobrenome et al. (Ano)`, `Sobrenome et al. [Num]`, `Sobrenome e Sobrenome (Ano)`, `Autor (Ano)` e possessivos `Sobrenome et al.'s (Ano)`), protegido por lista de exclusão sintática para substantivos comuns não autores (`Figure (1)`, `Table (2)`, `January (2020)`).
   * **Citações Parentéticas (`\citep`):** Mascaramento de blocos com anos e autores (`(Sobrenome et al., Ano; Autor, Ano)`), citações unclosed quebradas por quebras de tabela e expressões residuais (`(see [CITE])`).
   * **Normalização de Variantes Tipográficas de `et al.`:** Cobertura de variações ortográficas e de pontuação (`et. al`, `et.al.`, `etal.`), autores com dígitos colados derivados de índices sobrescritos (`4Nallapati et al.`), nomes fragmentados por OCR (`Saatc i et al.`, `Heikkil a et al.`), citações órfãs não abertas resultantes de quebras de rodapés (`et al., 2006; ...)`), e `et al.` residual ao final de enumerações de citações (`[CITE] et al.`).
   * **Citações Numéricas em Colchetes (IEEE):** `[1]`, `[1, 2]`, `[1-5]`, preservando intervalos matemáticos contínuos como `[0, 1]` e `[-1, 1]`.
   * **Chaves Alfanuméricas:** `[Devlin+19]`, `[CGS15]`.
   * **Colapso de Citações Consecutivas com Ponto e Vírgula:** Condensação de sequências extensas de citações contíguas (`[CITE] ; [CITE] ; [CITE]`) em um único token canônico `[CITE]`.
10. **Mascaramento Avançado de Fórmulas e Operadores Matemáticos:** Substituição de blocos LaTeX, expressões inline (`\$...\$`), operadores de otimização (`arg min`, `arg max`), equações em texto simples (`Ax + Bz = c`, `ρ > 0`, `α = 1`), comandos estruturais, números de equações isolados em linha única e caracteres do bloco grego e operadores matemáticos Unicode (`∈`, `≤`, `≥`, `∑`, `∏`, `ρ`, `α`, etc.) pelo token `[MATH]`.
11. **Mascaramento Insensível a Maiúsculas de URLs, DOIs, Domínios Diretos e Reconstituição de Protocolos Quebrados:**
   * **Descolamento de Prefixos Grudados:** Separação prévia de palavras ou dígitos numéricos colados a protocolos de internet (`start1https://` $\rightarrow$ `start1 https://`, `4https://` $\rightarrow$ `4 https://`).
   * **Reconstituição de Protocolos Espaçados ou Partidos:** Recomposição de protocolos fragmentados por espaçamentos acidentais de diagramação de coluna ou OCR (`https: //`, `http : //`, `https : / /` $\rightarrow$ `https://`) e reconciliação de protocolos partidos por quebras de linha físicas (`(https?://|ftp://|www\.)\s*\n\s*`).
   * **Varredura Canônica de Links e Identificadores Digitais:** Detecção e substituição de URLs completas, protocolos e identificadores digitais DOI (`10.\d{4,9}/\S+`) pelo token `[URL]`.
   * **Detecção de Domínios Diretos e Repositórios:** Mascaramento de endereços diretos de projetos, repositórios de código e bases de dados abertas mesmo sem protocolo explícito (ex.: `github.com/...`, `en.wikipedia.org/...`, `wordnet.princeton.edu`, `arxiv.org`).
   * **Purga de Fragmentos Órfãos e Preservação de Vocábulos da Prosa:** Expurgo de fragmentos residuais de protocolo (`http:`, `https:`, `(https:`, `'http(s)://...'`), mantendo estritamente preservados termos técnicos legítimos do texto (ex.: "HTTP traffic").
   * **Remoção de Dígitos de Rodapé Antecedentes e Colapso de Tokens:** Descarte de números de notas de rodapé isolados imediatamente anteriores ao link mascarado e condensação de múltiplos tokens contíguos (`[URL] [URL]` $\rightarrow$ `[URL]`).
12. **Padronização de Marcadores de Tópicos (Bullets):** Normalização de marcadores pontuados (`•`, `*`, `▪`) para hífen simples `- `.
13. **Fusão de Linhas Intra-parágrafo (*Line Unwrapping*) e Preservação de Estrutura:** Conversão de todas as quebras físicas de linha de coluna do PDF em espaços simples contínuos dentro de parágrafos, preservando estritamente quebras duplas de parágrafo (`\n\n`) e itens de listas (`\n- `).

---

## 3. Geração Sintética com Qwen 2.5 e Descarte de Sementes [CONCLUÍDA]

### 3.1 Modelo Selecionado
* **Modelo Oficial:** `Qwen/Qwen2.5-7B-Instruct` (família de pesos abertos de alta escala da Alibaba).
* **Justificativa Técnica:** Estado da arte entre modelos abertos para raciocínio técnico, seguimento estrito de diretrizes acadêmicas, densidade informacional e domínio de terminologia científica formal em língua inglesa.

### 3.2 Ambiente de Execução Oficial e Otimizações em Kaggle 2x T4
A geração sintética das 1.500 sementes será executada oficialmente em ambiente **Kaggle Notebook** equipado com **GPU dual Nvidia Tesla T4 (2x 16 GB, total de 32 GB VRAM)**.

Para viabilizar a inferência em lote (*batch inference*) de alta velocidade sem estouro de memória (*Out of Memory - OOM*), a execução emprega o motor **vLLM** com as seguintes configurações obrigatórias para a arquitetura Turing (compute capability 7.5):
* **Paralelismo de Tensores (`tensor_parallel_size=2`):** Distribui os pesos do modelo (cerca de 15 GB em float16) uniformemente entre as duas GPUs T4 (`cuda:0` e `cuda:1`), alocando ~7,5 GB de pesos por placa e liberando mais de 7 GB de VRAM em cada GPU para o pool de blocos de atenção (*PagedAttention KV-cache*).
* **Precisão Numérica (`dtype="float16"`):** GPUs T4 não possuem suporte nativo de hardware para bfloat16; o uso de float16 garante estabilidade matemática e compatibilidade total com os Tensor Cores da arquitetura Turing.
* **Execução em Modo Eager (`enforce_eager=True`):** Obrigatório na arquitetura T4 para evitar que o vLLM tente capturar grafos CUDA (*CUDA graphs*), o que causa estouros súbitos de memória e congelamento de processos em GPUs de gerações anteriores.
* **Utilização de Memória (`gpu_memory_utilization=0.90`):** Reserva 10% da VRAM para picos de memória e buffers auxiliares do PyTorch.
* **Janela de Contexto (`max_model_len=4096`):** Fornece espaço suficiente para acomodar a leitura das seções humanas originais e a emissão do texto sintético completo.
* **Parâmetros de Amostragem (*SamplingParams*):**
  * `temperature=0.7`: Equilíbrio ótimo entre criatividade acadêmica e rigor factual.
  * `top_p=0.8`: Amostragem por núcleo (*nucleus sampling*) para corte de cauda de baixa probabilidade.
  * `repetition_penalty=1.05`: Inibição de frases circulares ou jargões repetitivos.
  * `max_tokens=1500`: Teto suficiente para a redação completa das três seções.
* **Throughput e Tempo Estimado:** Com processamento contínuo em lote (*continuous batching*), a velocidade média estimada atinge de 150 a 250 tokens por segundo no cluster dual T4, concluindo a síntese das 1.500 sementes em **45 a 60 minutos** de execução contínua.

### 3.3 Revisão de Literatura em Engenharia de Prompts para Texto Científico Pareado
Na literatura de detecção de IA acadêmica (Liang et al., 2024; Tang et al., 2024; Hans et al., 2024; Verma et al., 2024), a metodologia padrão para construir conjuntos de dados de treinamento contrastivos é a **geração pareada de espelhos sintéticos** (*paired synthetic mirrors*):
1. **Isolamento de Estilo vs. Conteúdo:** Se os textos humanos abordarem tópicos de 2015 e os textos de IA abordarem tópicos arbitrários de 2024, o classificador aprenderá a classificar o tema da pesquisa em vez da autoria linguística. Para blindar o classificador contra atalhos temáticos, cada texto sintético deve ser gerado a partir do conteúdo técnico de uma semente humana específica, preservando o escopo semântico, o problema e as descobertas.
2. **Decomposição em Duas Etapas (*Fact-to-Text*):** Conforme demonstrado por Madaan et al. (2023) e Liang et al. (2024), solicitar diretamente que um modelo "reescreva" um artigo causa memorização direta de frases humanas. A abordagem ideal decompõe o fluxo em:
   * **Etapa 1:** Extração pura de proposições e fatos técnicos essenciais (destilando a substância científica em tópicos estruturados).
   * **Etapa 2:** Redação autônoma a partir exclusivamente do resumo factual da Etapa 1, forçando a LLM a gerar sua própria sintaxe, escolhas lexicais e conectivos estilísticos característicos.

### 3.4 Especificação dos Prompts Oficiais

#### Prompt 1: Extração de Fatos Técnicos (Technical Fact Extraction)

* **System Prompt:**
  ```text
  You are an expert scientific analyst specializing in machine learning and computational linguistics. Your task is to analyze the provided sections of a scientific paper and extract its core technical facts into a concise, factual JSON structure. Do not include introductory filler, conversational pleasantries, or stylistic evaluations.
  ```

* **User Prompt Template:**
  ```text
  Extract the core technical substance from the scientific paper sections below into a structured JSON object.

  [INPUT SECTIONS]
  Title: {title}
  Abstract: {abstract}
  Introduction: {introduction}
  Conclusion: {conclusion}

  [OUTPUT FORMAT]
  Output strictly a valid JSON object matching this schema:
  {
    "problem_statement": "The core research question and technical challenge addressed.",
    "core_methodology": "The key proposed model, theoretical framework, and formal mathematical mechanisms (loss functions, objective formulations, equations, and variable notations in LaTeX $...$).",
    "empirical_findings": "The quantitative benchmarks, experimental evidence, datasets, and verified results.",
    "related_work_and_baselines": "Key prior methods, seminal foundational works, and baseline models cited in the text (including author names, years, or benchmark references).",
    "resources_and_urls": "Any public code repository links, open-source URLs, or project artifacts mentioned.",
    "main_conclusions": "The concluding takeaways, practical implications, and future research avenues."
  }
  ```

#### Prompt 2: Redação Sintética Especializada (Scientific Mirror Drafting)

* **System Prompt:**
  ```text
  You are an expert AI researcher drafting a top-tier peer-reviewed academic conference paper (such as NeurIPS, ICML, ACL, or ICLR). Using strictly the provided technical facts, write three complete, formal, and authoritative scientific paper sections: Abstract, Introduction, and Conclusion.
  Maintain rigorous academic style, formal scientific prose, natural paragraph transitions, and clear structural continuity. Output strictly a valid JSON object containing the exact keys "abstract", "introduction", and "conclusion".
  ```

* **User Prompt Template:**
  ```text
  Using exclusively the technical facts provided below, write a new, complete, and formal academic paper comprising an Abstract, Introduction, and Conclusion.

  [TECHNICAL FACTS]
  Problem: {problem_statement}
  Methodology & Math: {core_methodology}
  Prior Literature & Baselines: {related_work_and_baselines}
  Findings: {empirical_findings}
  Resources & URLs: {resources_and_urls}
  Conclusions: {main_conclusions}

  [SECTION REQUIREMENTS]
  1. abstract: A dense, self-contained summary (100 to 200 words) framing the challenge, the proposed innovation, key mathematical notations if applicable, and principal empirical results.
  2. introduction: A comprehensive introduction (500 to 900 words) contextualizing the domain, formalizing the challenge, actively citing prior literature and baseline methods from the factual summary using standard academic citation style (both narrative, e.g., Author et al. (Year), and parenthetical, e.g., (Author et al., Year)), mathematically formalizing the proposed methodology (incorporating standard inline LaTeX $...$ formulations, objective or loss functions, and variable definitions from the methodology facts), mentioning resource or repository links where applicable, and ending with an explicit itemized contribution list (- We propose... - We demonstrate...).
  3. conclusion: A formal closing section (100 to 200 words) summarizing principal insights, noting practical boundaries, and outlining future directions.

  [OUTPUT FORMAT]
  Output strictly a valid JSON object:
  {
    "abstract": "...",
    "introduction": "...",
    "conclusion": "..."
  }
  ```

### 3.5 Fluxo de Dados e Pré-processamento de Paridade
Para assegurar integridade metodológica e reprodutibilidade:
1. **Geração no Kaggle:** O notebook no Kaggle consome as sementes extraídas de `data/raw/collected_corpus.jsonl` (onde `provenance_type == 'seed_discarded'`), executa os prompts em lote via vLLM e salva os textos sintéticos brutos gerados em `data/raw/synthetic_ai.jsonl` (1.494 artigos gerados).
2. **Isolamento de Pré-processamento:** O pré-processamento de paridade **não é executado dentro do notebook Kaggle**.
3. **Higienização Determinística Local:** O arquivo bruto gerado é transferido para o repositório local e submetido ao mesmo script padronizado de pré-processamento de forma parametrizada:
   ```bash
   python3 -m src.preprocessing -i data/raw/synthetic_ai.jsonl -o data/processed/synthetic_corpus.jsonl
   ```
4. **Recuperação de Metadados e Paridade Científica Estrita:** O script recupera automaticamente a conferência (`conference`), o ano de publicação (`publication_year`), os autores e metadados estruturais a partir das sementes descartadas de referência, assegurando que tanto os textos humanos quanto os textos sintéticos passem com exatidão pela mesma esteira de des-hifenização, normalização Unicode NFKC, expurgo de e-mails/legendas e mascaramento de atalhos (`[CITE]`, `[MATH]`, `[URL]`), eliminando discrepâncias acidentais entre ambientes.
5. **Preservação e Quarentena das Sementes (`seed_discarded`):** Os textos humanos originais das sementes permanecem catalogados em `data/raw/collected_corpus.jsonl` com `provenance_type = 'seed_discarded'` e `label = None`. Eles são estritamente excluídos do treinamento, validação e teste dos modelos classificadores, servindo unicamente para auditoria de proveniência científica.

* **Saída:** Arquivo sintético bruto `data/raw/synthetic_ai.jsonl` e arquivo sintético pré-processado `data/processed/synthetic_corpus.jsonl` (1.494 artigos com rótulo $1$).

---

## 4. Caracterização Linguística Contrastiva [PENDENTE]

Executada pelo módulo `src/features/linguistic_analyzer.py` sobre o conjunto balanceado de 2.988 artigos (1.494 $S_{\text{human}}$ vs. 1.494 $S_{\text{synthetic}}$):
1. **Diversidade Lexical:** Cálculo de Type-Token Ratio (TTR), Root TTR ($TTR_{\text{root}} = \frac{V}{\sqrt{N}}$) e Densidade Lexical (proporção de substantivos, verbos, adjetivos e advérbios).
2. **Morfossintaxe via spaCy (`en_core_web_sm`):** Frequência normalizada por 1.000 palavras de:
   * Voz passiva analítica vs. ativa.
   * Advérbios modais e termos enfáticos.
   * Conjunções subordinativas e coordenativas.
3. **Densidade de Entidades Nomeadas (NER):** Proporção de tokens rotulados como `PERSON`, `ORG`, `GPE` e `DATE`.
4. **N-gramas Discriminantes e Palavras de Excesso:**
   * Extração de unigramas, bigramas e trigramas.
   * Ranqueamento via Informação Mútua (Mutual Information) para isolar termos com assimetria estatística desproporcional na classe IA.
* **Saída:** Tabelas de sumário estatístico e gráficos comparativos de densidade de distribuição.

---

## 5. Treinamento do Modelo com CV e Otimização com Optuna [PENDENTE]

### 5.1 Estratégia de Particionamento
* Corpus de 2.988 instâncias particionado por `paper_id`:
  * **Treino (70% = 2.092 instâncias):** 1.046 Humanos, 1.046 IA.
  * **Validação (15% = 448 instâncias):** 224 Humanos, 224 IA, para busca de hiperparâmetros e calibração.
  * **Teste Cego Blindado (15% = 448 instâncias):** 224 Humanos, 224 IA, isolado durante toda a fase de tuning.

### 5.2 Otimização de Hiperparâmetros via Optuna
* **Validação Cruzada:** 5-Fold Stratified Cross-Validation agrupada estritamente por `paper_id`.
* **Métrica Objetivo:** Média do F1-Score Macro nos folds de validação:
  $$F1_{\text{Macro}} = \frac{F1_{\text{Humano}} + F1_{\text{IA}}}{2}$$
* **Espaço de Busca do Optuna:**
  * Modelo base: SciBERT (`allenai/scibert_scivocab_uncased`) ou DeBERTa-v3 (`microsoft/deberta-v3-base`).
  * Taxa de aprendizado (`learning_rate`): amostrada em escala logarítmica entre $1 \times 10^{-5}$ e $5 \times 10^{-5}$.
  * Decaimento de peso (`weight_decay`): uniforme entre 0.01 e 0.1.
  * Aquecimento linear (`warmup_ratio`): uniforme entre 0.05 e 0.15.
  * Dropout da cabeça linear: uniforme entre 0.1 e 0.25.
  * Número de épocas: 3 a 5 (com parada antecipada).

### 5.3 Calibração de Probabilidades e Avaliação Final
* Ajuste de *Temperature Scaling* ou *Platt Scaling* nos logits dos folds de validação.
* Avaliação final do checkpoint calibrado no Teste Cego Blindado (448 artigos):
  * F1-Score Macro, Acurácia, AUC-ROC e Precisão.
  * Matriz de confusão com monitoramento da taxa de falsos positivos ($FPR \le 0.02$).

---

## 6. Análise Longitudinal Temporal (2015 a 2025) [PENDENTE]

Executada pelo módulo `src/evaluation/longitudinal_analyzer.py`:
1. **Inferência no Corpus Temporal (5.800 artigos):**
   * **2015 a 2019:** Os 1.000 artigos de $S_{\text{temporal}}$ (200 artigos/ano: 50 por conferência), que o classificador nunca viu em nenhuma etapa de treino ou calibração.
   * **2020 a 2025:** Os 4.800 artigos contemporâneos coletados sob amostragem estratificada (800 artigos/ano: 200 por conferência).
2. **Correção de Prevalência (Rogan-Gladen):** Ajuste da proporção observada $\hat{P}_{\text{bruta}}$ considerando a sensibilidade ($Se$) e especificidade ($Sp$) do modelo de teste:
   $$P_{\text{ajustada}} = \frac{\hat{P}_{\text{bruta}} + Sp - 1}{Se + Sp - 1}$$
3. **Incerteza Estatística via Bootstrap:** Geração de 1.000 réplicas de reamostragem não paramétrica por ano e por conferência para traçar intervalos de confiança de 95%.
4. **Verificação de Hipótese:** Avaliação do comportamento da curva ano a ano, validando a taxa base de controle pré-2020 e quantificando o salto a partir de 2023.

---

## 7. Notebook Python Integrado [PENDENTE]

* **Localização:** `src/pipeline_completo.ipynb`.
* **Padrões de Construção:**
  * Célula de cabeçalho inicial com título do projeto, identificação acadêmica e declaração de integridade.
  * Numeração hierárquica no comentário da primeira linha de cada célula de código (`#CELL S.C - BRIEF DESCRIPTION IN 1 SENTENCE`).
  * Centralização estrita de dependências (`%pip install`) e declarações `import` na Seção 1.
  * Validação prévia de sintaxe e compilação de todas as células via AST.
