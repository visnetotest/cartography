# Technical Requirements: Azure SQL Intelligence Module

This document provides a comprehensive technical breakdown of the Azure SQL intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this hierarchical module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.azure.sql.py`
*   **Purpose:** This module performs an in-depth sync of Azure SQL resources. It discovers the top-level SQL Servers and then drills down to ingest a wide array of associated resources, including the databases themselves, failover groups, elastic pools, administrative settings, and database-specific configurations like threat policies and encryption.

### Data Flow

The module executes a multi-layered sync, starting with servers and recursively discovering the resources they contain. The process is heavily dependent on this hierarchy, as child resources are discovered using information from their parents.

```mermaid
graph TD
    A[Start Sync] --> B{List SQL Servers};
    B --> C{Load AzureSQLServer nodes};
    C --> D{List Server-Level Resources (DNS Aliases, AD Admins, Failover Groups, Databases, etc.)};
    D --> E{Load Server-Level child nodes (e.g., AzureFailoverGroup, AzureElasticPool)};
    D --> F{Load AzureSQLDatabase nodes};
    F --> G{List Database-Level Resources (Replication Links, Threat Policies, TDE)};
    G --> H{Load Database-Level child nodes (e.g., AzureReplicationLink, AzureTransparentDataEncryption)};
    H --> I[Neo4j Graph];
    I --> J[End Sync];

    subgraph "L1: Server Level"
        B
        C
    end

    subgraph "L2: Database Level"
        D
        E
        F
    end

    subgraph "L3: Database-Child Level"
        G
        H
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `azure-mgmt-sql`: The Azure SDK for Python, used to interact with the Azure SQL management plane.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

The sync is a three-stage hierarchical process orchestrated by the main `sync()` function:

1.  **Server-Level Sync:**
    *   `get_server_list()`: Fetches all Azure SQL Server instances in the subscription.
    *   `load_server_data()`: Ingests the servers as `:AzureSQLServer` nodes, linked to the parent `:AzureSubscription`.

2.  **Server-Child-Level Sync (`sync_server_details`):**
    *   This stage begins the deep dive. The `get_server_details()` generator function iterates through each server and makes a series of API calls to get its direct child and associated resources. This includes:
        *   DNS Aliases (`:AzureServerDNSAlias`)
        *   Azure AD Administrators (`:AzureServerADAdministrator`)
        *   Recoverable and Restorable Dropped Databases
        *   Failover Groups (`:AzureFailoverGroup`)
        *   Elastic Pools (`:AzureElasticPool`)
        *   **SQL Databases (`:AzureSQLDatabase`)**
    *   `load_server_details()` collects all this data and calls a series of `_load_*` functions (e.g., `_load_failover_groups`, `_load_databases`) to ingest these resources as nodes, creating relationships back to their parent `:AzureSQLServer`.

3.  **Database-Child-Level Sync (`sync_database_details`):**
    *   After the `:AzureSQLDatabase` nodes have been created, this final stage begins.
    *   The `get_database_details()` generator iterates through each database and fetches its specific configurations:
        *   Replication Links (`:AzureReplicationLink`)
        *   Threat Detection Policies (`:AzureDatabaseThreatDetectionPolicy`)
        *   Restore Points (`:AzureRestorePoint`)
        *   Transparent Data Encryption status (`:AzureTransparentDataEncryption`)
    *   `load_database_details()` collects this data and calls the final set of `_load_*` functions to ingest these configuration nodes, creating relationships to their parent `:AzureSQLDatabase`.

4.  **Cleanup:** A single `cleanup_azure_sql_servers` job is run at the end. This job is configured to traverse the entire `:AzureSQLServer` hierarchy, removing any node in the tree that was not touched during the current sync run.

### Dependencies

*   **External:** `azure-mgmt-sql`, `neo4j-driver`
*   **Internal (Cartography):**
    *   `.util.credentials.Credentials`: The object holding Azure credentials.
    *   `cartography.util.run_cleanup_job`: Used for the final cleanup operation.

---

## 🏛️ Architecture and Structure

### System Integration

This module provides a detailed inventory of an organization's relational database posture in Azure. The hierarchical data model is a key feature, allowing analysts to query at any level, from high-level server configurations down to specific database encryption settings. The `:AzureServerADAdministrator` nodes can be correlated with Azure AD principal data from other modules to build a complete picture of database access.

### Internal Components

The module is structured as a nested `sync -> get -> load` pipeline.

*   **Top-Level Orchestrator:**
    *   `sync()`: The main entry point.
*   **Server-Level Functions:**
    *   `get_server_list`, `load_server_data`
*   **Server-Child-Level Functions:**
    *   `sync_server_details` (orchestrator)
    *   `get_server_details` (generator for data fetching)
    *   `load_server_details` (orchestrator for loading)
    *   Multiple `_load_*` functions for each resource type.
*   **Database-Child-Level Functions:**
    *   `sync_database_details` (orchestrator)
    *   `get_database_details` (generator for data fetching)
    *   `load_database_details` (orchestrator for loading)
    *   Multiple `_load_*` functions for each configuration type.
*   **Cleanup:**
    *   `cleanup_azure_sql_servers()`: A single function to clean up the entire tree of synced resources.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync(neo4j_session: neo4j.Session, credentials: Credentials, subscription_id: str, sync_tag: int, common_job_parameters: Dict)`
*   **Description:** Orchestrates the complete, hierarchical discovery and synchronization of Azure SQL Servers and their sub-resources for a given subscription.
*   **Side Effects:**
    *   Writes a large, multi-level hierarchy of nodes and relationships to the graph.
    *   Runs a comprehensive cleanup job that may delete any stale node within the Azure SQL hierarchy.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`credentials`**: An Azure `Credentials` object. (Required)
*   **`subscription_id`**: The ID of the Azure subscription to scan. (Required)
*   **`sync_tag`**: An `int` timestamp for versioning.
*   **`common_job_parameters`**: A `Dict` for cleanup jobs.
*   **Input Sources:** Called by the main Azure sync orchestrator.

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** All `get_*` functions are wrapped in robust `try...except` blocks that catch `ClientAuthenticationError`, `ResourceNotFoundError`, `HttpResponseError`, and `CloudError`. This prevents the entire sync from failing due to permissions issues or if a resource is simply not present, allowing the sync to continue gracefully.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Audit Database Encryption**
    *   **Scenario:** A compliance officer needs to verify that all production SQL databases have Transparent Data Encryption (TDE) enabled.
    *   **Integration:** The module syncs a dedicated `:AzureTransparentDataEncryption` node for each database, which includes its status.
        ```cypher
        MATCH (db:AzureSQLDatabase)-[:CONTAINS]->(tde:AzureTransparentDataEncryption)
        WHERE tde.status <> 'Enabled'
        RETURN db.id, db.name
        ```

*   **Use Case 2: Identify SQL Server Administrators**
    *   **Scenario:** A security team wants to list all users and groups that are designated as Active Directory administrators on any SQL server.
    *   **Integration:** The `ADMINISTERED_BY` relationship provides a direct link between servers and their admins.
        ```cypher
        MATCH (server:AzureSQLServer)-[:ADMINISTERED_BY]->(admin:AzureServerADAdministrator)
        RETURN server.name, admin.login, admin.administratortype
        ```

*   **Use Case 3: Map Database Replication**
    *   **Scenario:** A reliability engineer needs to review the replication topology for a critical database, including its partners and replication state.
    *   **Integration:** The `:AzureReplicationLink` node and its properties provide a detailed picture of the replication setup.
        ```cypher
        MATCH (db:AzureSQLDatabase {name: 'my-critical-db'})-[:CONTAINS]->(link:AzureReplicationLink)
        RETURN link.name, link.partnerserver, link.partnerrole, link.role, link.state
        ```
