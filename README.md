<h1 align="center">Henrique Messias</h1>

<p align="center">
  <b>Engenheiro de Dados · Arquitetura de Dados no GCP · Streaming e Eventos · Agentes de IA</b><br/>
  Quase 7 anos construindo, sustentando e <b>re-arquitetando</b> plataformas de dados
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Cloud-4285F4?style=flat-square&logo=googlecloud&logoColor=white" />
  <img src="https://img.shields.io/badge/BigQuery-669DF6?style=flat-square&logo=googlebigquery&logoColor=white" />
  <img src="https://img.shields.io/badge/Dataflow_·_Apache_Beam-F26B00?style=flat-square&logo=apache&logoColor=white" />
  <img src="https://img.shields.io/badge/Apache_Airflow-017CEE?style=flat-square&logo=apacheairflow&logoColor=white" />
  <img src="https://img.shields.io/badge/Apache_Kafka-231F20?style=flat-square&logo=apachekafka&logoColor=white" />
  <img src="https://img.shields.io/badge/Confluent-0A0A0A?style=flat-square&logo=confluent&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_ADK-34A853?style=flat-square&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/n8n-EA4B71?style=flat-square&logo=n8n&logoColor=white" />
</p>

---

## Sobre mim

Sou engenheiro de dados e vim do **desenvolvimento backend**, o que molda o jeito como trabalho com dados:
pipelines são software, com dependências explícitas, falhas previsíveis e código versionado.

Passei a maior parte da carreira no **Google Cloud Platform**, em três frentes:

- **Plataformas analíticas:** ELT em arquitetura medalhão, com o processamento dentro do BigQuery.
- **Streaming e eventos:** Pub/Sub, Kafka, Confluent e Azure Event Hubs consumidos pelo Dataflow.
- **Migrações de arquitetura:** tirar plataformas do Greenplum/GemFire e do Databricks/Azure e **redesenhá-las**
  para o GCP, em vez de só mudar os servidores de lugar.

Hoje também desenvolvo **agentes de IA** com o Google ADK e o n8n, e faço **pós-graduação em Processamento de
Linguagem Natural na UFG**.

---

## Migrar não é copiar

A migração mais barata no primeiro mês é o *lift & shift*: levar os mesmos componentes para outra nuvem.
Ela costuma ser a mais cara no primeiro ano, porque leva junto as limitações da arquitetura antiga.
Nas migrações de que participei, o ponto de partida foi outro: **qual é o padrão de acesso, a latência e o
custo que o negócio precisa, e qual serviço gerenciado resolve isso de forma nativa?**

```mermaid
flowchart LR
    subgraph LS["Lift & shift"]
        direction TB
        L1["Mesmo motor, outra infraestrutura"] --> L2["Mesmos gargalos"] --> L3["Custo operacional mantido"]
    end
    subgraph RA["Re-arquitetura (minha abordagem)"]
        direction TB
        R1["Entender padrões de acesso<br/>e requisitos de latência"] --> R2["Escolher o serviço gerenciado<br/>certo para cada responsabilidade"]
        R2 --> R3["Remodelar dados para<br/>o novo motor"] --> R4["Validar paridade<br/>com o legado"]
    end
    LS -.->|"o que eu evito"| RA

    classDef bad fill:#fdecea,stroke:#d93025,color:#1a1a1a
    classDef good fill:#e6f4ea,stroke:#188038,color:#1a1a1a
    class L1,L2,L3 bad
    class R1,R2,R3,R4 good
```

| Pergunta que guia a migração | O que ela muda na prática |
|---|---|
| Como os dados serão **consultados**? | Define o motor: Bigtable para leitura por chave em milissegundos, BigQuery para análise |
| Qual o **gatilho** do processamento? | Troca rotinas por janela de horário por **eventos** (GCS → Pub/Sub → Dataflow) |
| Onde a **transformação** deve viver? | Transformação em SQL versionado (Dataform) e dentro do warehouse (ELT) |
| O que é **operado por mim** e o que é **gerenciado**? | Troca clusters mantidos pelo time por serviços serverless |

---

## Principais projetos

### 1. Greenplum + GemFire → GCP: re-arquitetura para baixa latência

> **Desafio:** uma solução de baixa latência sustentada por um data warehouse MPP (Greenplum) e uma grade de
> dados em memória (GemFire). Replicar essa combinação no GCP manteria a complexidade e o custo operacional.

**Antes: infraestrutura dedicada e processamento acoplado**

```mermaid
flowchart LR
    F["Arquivos de origem"] --> GP[("Greenplum<br/>MPP")]
    GP -->|"transformação"| GP
    GP -->|"carga"| GF[("GemFire<br/>cache em memória")]
    GF --> APP["Aplicações consumidoras"]

    classDef legacy fill:#f1f3f4,stroke:#5f6368,color:#1a1a1a
    class F,GP,GF,APP legacy
```

**Depois: event-driven, serverless e com o modelo de dados guiado pela consulta**

```mermaid
flowchart LR
    F["Arquivos<br/>de origem"] -->|"upload"| GCS[("Cloud<br/>Storage")]
    GCS -->|"notificação"| PS{{"Pub/Sub"}}
    PS -->|"assinatura"| DF["<b>Dataflow · streaming</b><br/>1. leitura do arquivo<br/>2. parsing e validação<br/>3. transformação e tipagem<br/>4. montagem do row key"]
    DF -->|"escrita"| BT[("Bigtable")]
    BT -->|"leitura por chave<br/>em ms"| APP["Aplicações<br/>consumidoras"]

    classDef gcp fill:#e8f0fe,stroke:#1a73e8,color:#1a1a1a
    classDef step fill:#fef7e0,stroke:#f9ab00,color:#1a1a1a
    class GCS,PS,BT gcp
    class DF step
```

**Decisões de arquitetura**

| Legado | GCP | Por que não foi um espelho |
|---|---|---|
| Carga agendada no Greenplum | Evento do **GCS** publicado no **Pub/Sub** | O processamento começa quando o dado chega, sem esperar uma janela de horário |
| Transformação dentro do MPP | **Dataflow em streaming** | Escala automaticamente conforme o volume e separa o processamento do armazenamento |
| Cache em memória (GemFire) | **Bigtable** | Leitura de baixa latência e alta vazão sem manter um cluster em memória |
| Modelo relacional | **Row key orientado à consulta** | No Bigtable, o desempenho depende da chave. Ela foi desenhada a partir das consultas esperadas, com índices, famílias de colunas e tipos definidos |

> **Modelagem no Bigtable:** o Bigtable não tem índices secundários nem joins. Por isso, o trabalho de
> modelagem acontece na composição do row key: os campos mais usados como filtro vêm primeiro, e a ordem
> evita concentrar escrita em um único nó (*hotspotting*). Assim, cada consulta vira uma leitura por chave ou
> por intervalo contíguo de chaves.

---

### 2. Databricks + Azure DevOps → GCP: plataforma unificada multi-fonte

> **Desafio:** migrar uma plataforma baseada em Databricks e Azure DevOps para o GCP, mantendo a ingestão
> de fontes de outras nuvens (mensageria no Azure, Confluent e Kafka) e reorganizando onde cada
> responsabilidade vive.

**Antes**

```mermaid
flowchart LR
    SRC["Fontes em lote<br/>e mensageria"] --> DB["Databricks<br/>notebooks e jobs Spark"]
    DB --> LAKE[("Armazenamento<br/>do lakehouse")]
    ADO["Azure DevOps"] -.->|"versionamento<br/>e deploy"| DB

    classDef legacy fill:#f1f3f4,stroke:#5f6368,color:#1a1a1a
    class SRC,DB,LAKE,ADO legacy
```

**Depois**

```mermaid
flowchart LR
    subgraph SRC["Fontes"]
        direction TB
        EH{{"Azure Event Hubs"}}
        CF{{"Confluent"}}
        KF{{"Apache Kafka"}}
        BATCH["Fontes em lote"]
    end

    subgraph ING["Ingestão"]
        DF["Dataflow<br/>streaming e lote"]
    end

    subgraph BQ["BigQuery"]
        direction TB
        RAW[("raw<br/>dado como chegou")]
        STG[("staging<br/>limpo e tipado")]
        MART[("modelos<br/>regras de negócio")]
    end

    subgraph DFM["Dataform"]
        direction TB
        SQLX["SQLX versionado"]
        ASSERT["assertions<br/>de qualidade"]
    end

    EH --> DF
    CF --> DF
    KF --> DF
    BATCH --> DF
    DF --> RAW
    RAW --> STG --> MART
    DFM -.->|"orquestra e testa"| STG
    DFM -.-> MART

    classDef msg fill:#fce8f3,stroke:#c5221f,color:#1a1a1a
    classDef gcp fill:#e8f0fe,stroke:#1a73e8,color:#1a1a1a
    classDef dfm fill:#e6f4ea,stroke:#188038,color:#1a1a1a
    class EH,CF,KF,BATCH msg
    class DF,RAW,STG,MART gcp
    class SQLX,ASSERT dfm
```

**Decisões de arquitetura**

| Legado | GCP | Por que não foi um espelho |
|---|---|---|
| Notebooks Spark fazendo ingestão e transformação juntas | **Dataflow** só na ingestão e **Dataform** na transformação | Separa as responsabilidades: o Dataflow move os dados, e o SQL versionado define as regras de negócio |
| Clusters Spark | **BigQuery** como motor de processamento | Deixa de haver cluster para dimensionar, ligar e desligar |
| Lógica de transformação espalhada em notebooks | **Dataform** com dependências explícitas | A linhagem entre as tabelas fica visível, e os testes de qualidade viram parte do pipeline |
| Mensageria consumida dentro do ecossistema Azure | **Dataflow** consumindo Event Hubs, Confluent e Kafka | Uma única camada de ingestão para brokers de nuvens e fornecedores diferentes |

---

### 3. Plataforma de Data Intelligence: 5 anos de sustentação e evolução

> **Contexto:** plataforma que centraliza dados de ERPs, APIs, planilhas e arquivos e os entrega prontos
> para análise. Atuei nela por cinco anos, sustentando a operação e evoluindo a arquitetura.

```mermaid
flowchart LR
    subgraph SRC["Fontes"]
        direction TB
        ERP["ERP"]
        API["APIs REST"]
        XLS["Excel"]
        GS["Google Sheets"]
        SFTP["SFTP"]
    end

    subgraph ORQ["Orquestrador Python (on-premises)"]
        direction TB
        DEP["Grafo de dependências<br/>autossuficiente"]
        EXT["Extração e carga"]
        DEP --> EXT
    end

    subgraph BQ["BigQuery: arquitetura medalhão"]
        direction LR
        BR[("Bronze<br/>bruto, fiel à origem")]
        SV[("Prata<br/>limpo, tipado,<br/>padronizado")]
        GD[("Ouro<br/>modelos de negócio")]
        BR -->|"SQL"| SV -->|"SQL"| GD
    end

    SRC --> EXT
    EXT -->|"carga (ELT)"| BR
    DEP -.->|"dispara transformações<br/>na ordem certa"| SV
    GD --> BI["Dashboards e análises"]

    classDef src fill:#f1f3f4,stroke:#5f6368,color:#1a1a1a
    classDef orq fill:#fef7e0,stroke:#f9ab00,color:#1a1a1a
    classDef bronze fill:#f6e0cc,stroke:#a0522d,color:#1a1a1a
    classDef silver fill:#eceff1,stroke:#78909c,color:#1a1a1a
    classDef gold fill:#fff4c2,stroke:#c9a400,color:#1a1a1a
    class ERP,API,XLS,GS,SFTP src
    class DEP,EXT orq
    class BR bronze
    class SV silver
    class GD gold
```

**O orquestrador: hierarquia de dependências autossuficiente**

Em vez de agendar cada processo num horário fixo, cada etapa **declara de quais outras depende**. O próprio
orquestrador resolve a ordem de execução a partir desse grafo:

```mermaid
flowchart TD
    A["Extração ERP"] --> D["Prata: vendas"]
    B["Extração API"] --> D
    C["Extração SFTP"] --> E["Prata: estoque"]
    D --> F["Ouro: indicadores comerciais"]
    E --> F
    F --> G["Atualização de relatórios"]

    X["Extração Sheets"] -->|"falhou"| Y["Prata: metas"]
    Y -.->|"bloqueado, não roda<br/>com dado incompleto"| Z["Ouro: metas vs. realizado"]

    classDef ok fill:#e6f4ea,stroke:#188038,color:#1a1a1a
    classDef fail fill:#fdecea,stroke:#d93025,color:#1a1a1a
    class A,B,C,D,E,F,G ok
    class X,Y,Z fail
```

<sub>Diagrama ilustrativo: os nomes das etapas são exemplos.</sub>

- **Uma etapa só roda quando todas as dependências terminaram com sucesso.**
- **Uma falha fica contida no ramo em que aconteceu:** os ramos independentes seguem normalmente, e nada é
  calculado com dado incompleto.
- **Todo o processamento pesado acontece no BigQuery (ELT).** O servidor on-premises só coordena, extrai e
  carrega, então não vira gargalo de processamento.

| Camada | Conteúdo | Objetivo |
|---|---|---|
| **Bronze** | Dados como chegaram da origem | Rastreabilidade e reprocessamento sem voltar à fonte |
| **Prata** | Dados limpos, tipados e padronizados | Uma base confiável e reutilizável entre áreas |
| **Ouro** | Modelos e indicadores de negócio | Consumo direto em dashboards e análises |

---

## IA, agentes e PLN

Minha pós em **Processamento de Linguagem Natural (UFG)** e a experiência com dados se juntam na construção
de **agentes de IA**: com o **Google ADK** e o **n8n**, conecto LLMs a dados confiáveis e a ferramentas reais.

### Projeto pessoal: [Segundo Cérebro](./segundo-cerebro)

Pipeline que transforma vídeos longos em notas pesquisáveis no Obsidian e responde perguntas sobre todo o
conteúdo via RAG.

```mermaid
flowchart LR
    V["Vídeo ou URL"] -->|"ffmpeg / yt-dlp"| AU["Áudio"]
    AU -->|"Whisper"| TR["Transcrição"]
    TR -->|"Claude"| NT["Nota .md<br/>no vault do Obsidian"]
    NT --> IDX[("Índice vetorial<br/>Chroma")]
    Q["Pergunta"] --> RAG["ask.py · RAG"]
    IDX --> RAG
    RAG --> R["Resposta com<br/>fontes"]

    classDef ai fill:#f3e8fd,stroke:#8430ce,color:#1a1a1a
    class TR,NT,RAG ai
```

---

## Stack

| Área | Ferramentas |
|---|---|
| **Linguagem** | Python, SQL |
| **Orquestração** | Apache Airflow (Cloud Composer), Cloud Scheduler, Dataform, orquestração própria em Python |
| **Processamento** | Dataflow (Apache Beam), BigQuery, Dataform |
| **Armazenamento** | BigQuery, Bigtable, Cloud SQL, Cloud Storage |
| **Mensageria e streaming** | Pub/Sub, Apache Kafka, Confluent, Azure Event Hubs |
| **Migrações de origem** | Greenplum, GemFire, Databricks, Azure DevOps |
| **IA** | Google ADK, n8n, LLMs, RAG, PLN |
| **Padrões de arquitetura** | Medalhão, ELT, event-driven, streaming de baixa latência, modelagem orientada à consulta |
