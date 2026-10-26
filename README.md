# ASPIRE
### AI-Driven Software Engineering Intelligence Platform

**An AI-powered unified agent framework for Requirement Intelligence, Repository Intelligence, Quality and Testing Intelligence, and Traceability in Software Development.**

**Research Project:** RP-J26-SE-327

---

## Overview

ASPIRE is a research platform designed to connect software requirements, source-code repositories, quality assurance evidence, and software traceability within a unified workflow.

The platform consists of four cooperating intelligence components that analyze different software engineering artifacts and are designed to share relevant information through a **Unified Software Knowledge Graph (USKG)**.

## Table of Contents

- [System Architecture](#system-architecture)
- [System Components](#system-components)
  - [Component 1: Requirement Intelligence](#component-1-requirement-intelligence)
  - [Component 2: Repository Intelligence](#component-2-repository-intelligence)
  - [Component 3: QA Evidence and Test Adequacy](#component-3-qa-evidence-and-test-adequacy)
  - [Component 4: Traceability Intelligence](#component-4-traceability-intelligence)
- [End-to-End Workflow](#end-to-end-workflow)
- [Unified Software Knowledge Graph](#unified-software-knowledge-graph)
- [Technology Stack](#technology-stack)
- [Datasets](#datasets)
- [Evaluation](#evaluation)
- [Installation and Usage](#installation-and-usage)
- [Limitations](#limitations)
- [References](#references)

---

## System Architecture

ASPIRE integrates four complementary components:

| Component | Responsibility |
|---|---|
| **C1 — Requirement Intelligence** | Converts raw requirements into structured requirements, tasks, user stories, and acceptance criteria. |
| **C2 — Repository Intelligence** | Analyzes repository structure, dependencies, code semantics, and evolution. |
| **C3 — QA Evidence Intelligence** | Assesses whether available testing evidence adequately validates requirement behaviors. |
| **C4 — Traceability Intelligence** | Verifies links between requirements, implementation artifacts, and tests, and monitors changes. |

## System Components

### Component 1: Requirement Intelligence

**Purpose:** Understand software requirements and convert them into structured artifacts.

**Key capabilities**
- Requirement extraction and text preprocessing
- Semantic embedding generation
- Technical task and user story generation
- Acceptance criteria generation
- Ambiguity, duplication, and conflict detection
- Requirement risk assessment
- USKG integration, where implemented

**Technologies:** Llama 3, semantic embeddings, XGBoost, and knowledge graph technologies.

### Component 2: Repository Intelligence

**Purpose:** Analyze software repositories to provide implementation and architecture-related context.

**Key capabilities**
- Source-file and package analysis
- Package dependency extraction
- Dependency graph feature generation
- Semantic code embeddings using GraphCodeBERT
- Repository evolution feature extraction
- Hybrid Repository Intelligence Model (HRIM)
- XGBoost-based proxy prediction
- SHAP-based explanations, where supported

**Technologies:** Python, GraphCodeBERT, XGBoost, SHAP, pandas, NumPy, and scikit-learn.

### Component 3: QA Evidence and Test Adequacy

**Purpose:** Determine whether available validation evidence adequately covers the behaviors specified by requirements.

**Key capabilities**
- Requirement Validation Unit (RVU) extraction
- Expected QA evidence identification
- Manual and automated test evidence processing
- Semantic evidence discovery
- Evidence relevance and adequacy assessment
- Requirement Validation Coverage (RVC)
- Requirement Validation Evidence Score (RVES)
- QA gap identification and recommendations
- Targeted revalidation following relevant changes

**Technologies:** Python, FastAPI, Pydantic, Sentence Transformers, JUnit, Neo4j, and supported testing tools.

### Component 4: Traceability Intelligence

**Purpose:** Establish and continuously verify traceability relationships between requirements and implementation artifacts.

**Key capabilities**
- Requirement-to-code candidate matching
- Semantic similarity analysis
- Candidate trace-link verification
- Trace-link confidence and explanations
- Change monitoring and impact analysis
- Trace-link decay detection
- Traceability completeness assessment
- Notifications for relevant QA revalidation

**Technologies:** Sentence Transformers, CodeBERT, Llama 3, and Neo4j where integrated.

---

## End-to-End Workflow

The intended system workflow is:

1. **Understand requirements** — C1 extracts requirements and generates structured artifacts.
2. **Analyze repositories** — C2 extracts implementation, dependency, semantic, and evolution information.
3. **Assess testing evidence** — C3 evaluates whether tests adequately validate individual requirement behaviors.
4. **Verify traceability** — C4 establishes and monitors relationships between requirements and implementation artifacts.
5. **Connect knowledge** — the USKG is intended to link relevant artifacts across the components.
6. **Respond to changes** — affected trace links and QA evidence can be re-evaluated where the relevant integrations are implemented.

## Unified Software Knowledge Graph

The USKG is the shared knowledge layer intended to connect:

- Requirements, tasks, user stories, and acceptance criteria
- Repositories, packages, code entities, and dependencies
- Requirement Validation Units and QA evidence
- Traceability links, change relationships, and decay information

The actual graph schema and integration status depend on the implemented system.

## Technology Stack

| Area | Technologies |
|---|---|
| AI and machine learning | Llama 3, XGBoost, SHAP |
| Semantic analysis | GraphCodeBERT, CodeBERT, Sentence Transformers |
| Backend and data processing | Python, FastAPI, Pydantic, pandas, NumPy |
| Knowledge graph | Neo4j, Cypher |
| Testing and QA | JUnit, Maven Surefire, k6 or JMeter |
| Frontend | React and visualization libraries, where used |
| Collaboration | Git and GitHub |


## Datasets

- **Spring PetClinic** — shared end-to-end demonstration repository.
- **Defects4J** — Java bug and testing benchmark.
- **Apache Commons-family projects** — repository and traceability research where applicable.
- **Mockito** — repository or testing benchmark where applicable.
- **PURE** — requirement-document analysis.
- **NICE / Augmented PROMISE NFR** — non-functional requirement research.
- **Researcher-curated data** — proposed for evaluating QA evidence adequacy.

## HRIM Repository Dataset
The Repository Intelligent Agent uses the following Java repositories for HRIM feature extraction and experiments

- **Spring PetClinic** - Manageable Java/Spring project and prototype repository.
- **Apache Commons Lang** - Git history, code churn, commit frequency, and developer activity.
- **JabRef** - Large Java application with substantial repository evolution
- **ArgoUML** - Architecture-oriented system for architectural evolution analysis.
- **Apache Lucene** - Modular Java project with extensive history and dependencies.
- **Apache Hadoop** - Large Java ecosystem for scalability and dependency analysis.
- **JUnit 5** - Modular project with testing and software evolution information.
- **Apache Maven** - Multi-module project for dependency and architecture analysis.
- **Apache Kafka** - Large-scale system with complex dependencies and substantial evolution.
- **TEAMMATES** - Open-source Java system relevant to architecture and traceability research.



## Evaluation

| Component | Example evaluation measures |
|---|---|
| C1 | Requirement extraction and classification metrics |
| C2 | Accuracy, precision, recall, F1-score, ROC-AUC, PR-AUC, and ablation analysis where available |
| C3 | RVU extraction, evidence retrieval, adequacy classification, RVC/RVES validation |
| C4 | Trace-link precision, recall, F1-score, and decay-detection accuracy |


## Installation and Usage

1. Clone the project repository.
2. Install the required language runtimes and dependencies.
3. Configure environment variables and external services.
4. Prepare or obtain the required datasets and model artifacts.
5. Start the required component services and frontend.
6. Run the relevant tests and evaluation scripts.


## Limitations

- Some described capabilities may still be under development.
- Cross-component and USKG integrations must be verified before being described as fully operational.
- Proxy labels do not independently establish confirmed architecture drift.
- QA evidence metrics and traceability results require appropriate experimental validation.
- Large language models and semantic embeddings may require significant computational resources.


## References

### Research Papers

1. Guo, D., et al. (2021). *GraphCodeBERT: Pre-training Code Representations with Data Flow.* [Microsoft Research](https://www.microsoft.com/en-us/research/publication/graphcodebert-pre-training-code-representations-with-data-flow/)

2. Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System.* Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. [https://doi.org/10.1145/2939672.2939785](https://doi.org/10.1145/2939672.2939785)

3. Lundberg, S. M., & Lee, S. I. (2017). *A Unified Approach to Interpreting Model Predictions.* [arXiv](https://arxiv.org/abs/1705.07874)

4. Reimers, N., & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* [arXiv](https://arxiv.org/abs/1908.10084)

### Models and Tools

- **GraphCodeBERT:** [Hugging Face Model](https://huggingface.co/microsoft/graphcodebert-base)
- **Llama:** [Official Website](https://www.llama.com/)
- **Hugging Face Transformers:** [Documentation](https://huggingface.co/docs/transformers)
- **XGBoost:** [Documentation](https://xgboost.readthedocs.io/)
- **SHAP:** [Documentation](https://shap.readthedocs.io/)
- **Neo4j:** [Documentation](https://neo4j.com/docs/)
- **FastAPI:** [Documentation](https://fastapi.tiangolo.com/)
- **scikit-learn:** [Documentation](https://scikit-learn.org/stable/)

### Dataset Sources

The datasets and software repositories used for the individual ASPIRE components are documented in the [Datasets](#datasets) section above.

#### Software Repositories

| No. | Repository | Link |
|---:|---|---|
| 1 | Spring PetClinic | [GitHub](https://github.com/spring-projects/spring-petclinic) |
| 2 | Apache Commons Lang | [GitHub](https://github.com/apache/commons-lang) |
| 3 | JabRef | [GitHub](https://github.com/JabRef/jabref) |
| 4 | ArgoUML | [GitHub](https://github.com/argouml-tigris-org/argouml) |
| 5 | Apache Lucene | [GitHub](https://github.com/apache/lucene) |
| 6 | Apache Hadoop | [GitHub](https://github.com/apache/hadoop) |
| 7 | JUnit 5 | [GitHub](https://github.com/junit-team/junit5) |
| 8 | Apache Maven | [GitHub](https://github.com/apache/maven) |
| 9 | Apache Kafka | [GitHub](https://github.com/apache/kafka) |
| 10 | TEAMMATES | [GitHub](https://github.com/TEAMMATES/teammates) |

#### 2. Research and Evaluation Datasets

| No. | Dataset | Source |
|---:|---|---|
| 11 | Defects4J | [GitHub Repository](https://github.com/rjust/defects4j) |
| 12 | PURE Dataset | [Zenodo](https://zenodo.org/records/7118517) |
| 13 | NICE / Augmented PROMISE NFR Dataset | [Zenodo](https://zenodo.org/records/14590935) |




---

**ASPIRE — Connecting requirements, implementation, quality assurance, and traceability.**
