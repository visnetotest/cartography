# Product Requirements Document: Cartography

## 1. Document Overview

This document provides a detailed overview of the software product "Cartography." It is intended for developers, product managers, and other stakeholders to understand the product's functionality, architecture, and user needs. The information in this document is inferred from the source code and may require further clarification.

## 2. Objective

The primary objective of Cartography is to provide a unified view of a technical infrastructure by mapping assets and their relationships. This allows for better visibility, security analysis, and understanding of complex environments.

## 3. Scope

**Included:**

*   Ingestion of asset data from various cloud providers (AWS, GCP, Azure) and other services (Okta, Kubernetes, etc.).
*   Modeling of assets and their relationships in a graph database (Neo4j).
*   A command-line interface (CLI) for interacting with the system.
*   Analysis jobs to identify potential security risks and misconfigurations.

**Excluded:**

*   A graphical user interface (GUI) for visualizing the graph data. (Assumption: The project seems to focus on the backend and data ingestion, with visualization likely handled by external tools like Neo4j Bloom).
*   Real-time monitoring of infrastructure changes. (Assumption: Cartography appears to run in discrete "sync" jobs).

## 4. User Personas and Use Cases

### Personas

*   **Security Engineer:** Responsible for identifying and mitigating security risks in the infrastructure. Needs to understand asset relationships, identify attack paths, and find misconfigurations.
*   **DevOps Engineer:** Responsible for managing and maintaining the cloud infrastructure. Needs to understand the impact of changes, identify dependencies, and troubleshoot issues.
*   **Cloud Infrastructure Engineer:** Responsible for designing and implementing the cloud infrastructure. Needs a tool to visualize and document the current state of the environment.

### Use Cases

*   **Use Case 1: Identify Publicly Exposed EC2 Instances**
    1.  A Security Engineer runs a Cartography sync to ingest the latest AWS data.
    2.  The engineer runs a pre-defined analysis job to find all EC2 instances with a public IP address and an open security group.
    3.  The output is a list of potentially exposed instances, which the engineer can then investigate further.

*   **Use Case 2: Understand the Blast Radius of a Compromised User**
    1.  A Security Engineer is investigating a potentially compromised Okta user.
    2.  The engineer queries the Cartography graph to find all the resources that the user has access to, including AWS roles, GCP projects, and Kubernetes pods.
    3.  This helps the engineer understand the potential impact of the compromise and prioritize remediation efforts.

## 5. Functional Requirements

| Requirement                                                                                                                                                                                            | Input                                                                                                                                                         | Output                                                                                                        | Inferred/Assumed |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------- |
| **Ingest AWS Data:** The system must be able to ingest asset data from AWS, including EC2 instances, S3 buckets, IAM roles, and more.                                                                 | AWS credentials with appropriate permissions.                                                                                                                  | AWS assets and their relationships are stored in the Neo4j database.                                          | Inferred         |
| **Ingest GCP Data:** The system must be to ingest asset data from GCP, including Compute Engine instances, Cloud Storage buckets, and IAM policies.                                                     | GCP credentials with appropriate permissions.                                                                                                                 | GCP assets and their relationships are stored in the Neo4j database.                                          | Inferred         |
| **Ingest Azure Data:** The system must be able to ingest asset data from Azure, including Virtual Machines, Storage Accounts, and Azure AD users.                                                      | Azure credentials with appropriate permissions.                                                                                                               | Azure assets and their relationships are stored in the Neo4j database.                                        | Inferred         |
| **Run Analysis Jobs:** The system must be able to run pre-defined analysis jobs to identify specific patterns or risks in the graph data.                                                                | A configured analysis job.                                                                                                                                    | A report or list of nodes that match the analysis criteria.                                                   | Inferred         |
| **Drift Detection:** The system must be able to detect drift between the desired state of the infrastructure and the actual state as represented in the graph. (Based on the `driftdetect` module). | A "shortcut" file defining the desired state.                                                                                                                 | A report of any deviations from the desired state.                                                            | Inferred         |

## 6. Non-Functional Requirements

*   **Performance:** The data ingestion process should be efficient and complete within a reasonable timeframe, even for large environments. (Assumption: The use of a graph database like Neo4j suggests that query performance is a key consideration).
*   **Scalability:** The system should be able to handle a large number of assets and relationships without significant degradation in performance. The modular architecture allows for scaling by adding more ingestion modules.
*   **Security:** The system requires access to sensitive credentials for various cloud providers. These credentials must be handled securely. The tool itself can be used to identify security vulnerabilities.
*   **Maintainability:** The codebase is well-structured and modular, which should make it relatively easy to maintain and extend. The use of a consistent plugin-style architecture for the `intel` modules is a good practice.
*   **Usability:** The primary interface is a CLI, which is suitable for the target audience of engineers. However, the lack of a GUI may limit its usability for less technical users.

## 7. Technical Specifications

### Technology Stack

*   **Programming Language:** Python 3.10
*   **Database:** Neo4j
*   **Key Libraries:**
    *   `boto3` (for AWS)
    *   `google-api-python-client` (for GCP)
    *   `oci` (for Oracle Cloud Infrastructure)
    *   `okta`
    *   `marshmallow` (for data serialization)
*   **Containerization:** Docker

### Architecture

Cartography uses a modular, plugin-based architecture. The core application is responsible for orchestrating the data ingestion process, which is handled by individual "intel" modules. Each intel module is responsible for connecting to a specific data source (e.g., AWS, GCP), retrieving asset data, and loading it into the Neo4j database. The data is modeled as a graph, with assets as nodes and their relationships as edges.

### Key Components

*   **`cartography.sync`:** The main entry point for running a sync job.
*   **`cartography.intel`:** The parent directory for all the intel modules. Each subdirectory corresponds to a different data source.
*   **`cartography.graph`:** Contains the logic for interacting with the Neo4j database.
*   **`cartography.driftdetect`:** A module for detecting drift in the infrastructure.
*   **`cartography.cli`:** The command-line interface.

## 8. Risks and Assumptions

### Risks

*   **Credential Management:** The system requires access to a large number of sensitive credentials. A compromise of the Cartography instance could have a significant impact.
*   **API Changes:** The ingestion modules are tightly coupled to the APIs of the various cloud providers. Any changes to these APIs could break the ingestion process.
*   **Scalability:** While the architecture is modular, the performance of the Neo4j database could become a bottleneck for very large environments.

### Assumptions

*   It is assumed that the primary users of Cartography are technical users who are comfortable with the command line and graph databases.
*   It is assumed that the visualization of the graph data is handled by external tools, such as Neo4j Bloom.
*   It is assumed that the `driftdetect` feature is used to compare the current state of the infrastructure with a desired state defined in a configuration file.

## 9. Dependencies

*   **External Services:**
    *   AWS
    *   GCP
    *   Azure
    *   Okta
    *   Oracle Cloud Infrastructure
    *   And many others as indicated by the `intel` modules.
*   **Libraries:** See the `pyproject.toml` file for a complete list of Python dependencies.
*   **Infrastructure:** Requires a running Neo4j instance.

## 10. Timeline and Milestones

This information is not available from the source code.

## 11. Appendix

N/A
