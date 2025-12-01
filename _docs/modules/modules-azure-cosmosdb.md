# Technical Requirements: Azure Cosmos DB Intelligence Module

This document provides a comprehensive technical breakdown of the Azure Cosmos DB intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this large and hierarchical module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.azure.cosmosdb.py`
*   **Purpose:** This module performs a deep and comprehensive sync of Azure Cosmos DB assets. It starts with the top-level database accounts and drills down into the specific data-plane resources they contain, supporting multiple Cosmos DB APIs (SQL, Cassandra, MongoDB, and Table).

### Data Flow

The module executes a multi-layered, hierarchical sync. It begins by discovering all Cosmos DB accounts in a subscription, then recursively discovers the database resources within each account, and finally the containers/tables within each database.

```mermaid
graph TD
    A[Start Sync] --> B{List Database Accounts};
    B --> C{Load AzureCosmosDBAccount nodes};
    C --> D{Sync Account Sub-Resources (Locations, CORS, etc.)};
    C --> E{List Databases/Keyspaces/Tables within each Account};
    E --> F{Load Database nodes (SQL, Mongo, Cassandra)};
    F --> G{List Containers/Collections/Tables within each Database};
    G --> H{Load Container nodes (SQL, Mongo, Cassandra)};
    H --> I[Neo4j Graph];
    I --> J[End Sync];

    subgraph "L1: Account Level"
        B
        C
        D
    end

    subgraph "L2: Database Level"
        E
        F
    end

    subgraph "L3: Container Level"
        G
        H
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `azure-mgmt-cosmosdb`: The Azure SDK for Python, used to interact with the Cosmos DB management plane.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

The sync is a multi-stage process orchestrated by the main `sync()` function:

1.  **Account-Level Sync:**
    *   `get_database_account_list()`: Fetches all Cosmos DB accounts.
    *   `transform_database_account_data()`: Pre-processes the account data, for example, by flattening the IP rules into a simple list.
    *   `load_database_account_data()`: Ingests the `:AzureCosmosDBAccount` nodes.
    *   `sync_database_account_data_resources()`: A helper orchestrator that loads the account's direct sub-resources, which are modeled as separate nodes. This includes `:AzureCosmosDBLocation` (with `CAN_WRITE_FROM`/`CAN_READ_FROM` relationships), `:AzureCosmosDBCorsPolicy`, `:AzureCDBPrivateEndpointConnection`, etc.

2.  **Database-Level Sync (`sync_database_account_details`):**
    *   This function begins the dive into the data plane. It iterates through the list of already-ingested accounts.
    *   For each account, it makes parallel API calls to list the different types of database resources it might contain: `get_sql_databases()`, `get_cassandra_keyspaces()`, `get_mongodb_databases()`, `get_table_resources()`.
    *   The results are gathered and loaded by `_load_sql_databases()`, `_load_cassandra_keyspaces()`, etc. These functions create nodes like `:AzureCosmosDBSqlDatabase` and connect them to their parent `:AzureCosmosDBAccount` with a `[:CONTAINS]` relationship.

3.  **Container-Level Sync (`sync_*_details`):**
    *   After the database-level nodes are created, a final layer of sync functions is called (e.g., `sync_sql_database_details`).
    *   These functions iterate through the newly created database nodes.
    *   For each database, they make API calls to list the containers within them (e.g., `get_sql_containers()`, `get_cassandra_tables()`, `get_mongodb_collections()`).
    *   This final layer of data is then loaded, creating nodes like `:AzureCosmosDBSqlContainer` and linking them to their parent database node with another `[:CONTAINS]` relationship.

4.  **Cleanup:** Cleanup jobs are run at the end of each logical sync stage (e.g., after all accounts are processed, after all SQL containers are processed) to ensure stale nodes at each level of the hierarchy are removed.

### Dependencies

*   **External:** `azure-mgmt-cosmosdb`, `neo4j-driver`
*   **Internal (Cartography):**
    *   `.util.credentials.Credentials`: The object holding Azure credentials.
    *   `cartography.util.run_cleanup_job`: Used for all cleanup operations.

---

## 🏛️ Architecture and Structure

### System Integration

This module provides a deep and detailed inventory of an organization's Cosmos DB usage. Its hierarchical approach to data modeling—from the subscription down to the individual container—is a key feature, allowing for precise and contextual queries. The information is self-contained but can be correlated with other data, for example, by linking `:AzureCDBPrivateEndpointConnection` nodes to the broader virtual network data synced by other modules.

### Internal Components

The module is structured as a series of nested `sync -> get -> transform -> load -> cleanup` pipelines.

*   **Top-Level Orchestrator:**
    *   `sync()`: The main entry point.
*   **Account-Level Functions:**
    *   `get_database_account_list`, `load_database_account_data`, `sync_database_account_data_resources`, `cleanup_azure_database_accounts`
*   **Database-Level Functions:**
    *   `sync_database_account_details` (orchestrator)
    *   `get_sql_databases`, `get_cassandra_keyspaces`, etc.
    *   `_load_sql_databases`, `_load_cassandra_keyspaces`, etc.
*   **Container-Level Functions:**
    *   `sync_sql_database_details`, `sync_cassandra_keyspace_details`, etc. (orchestrators)
    *   `get_sql_containers`, `get_cassandra_tables`, etc.
    *   `_load_sql_containers`, `_load_cassandra_tables`, etc.
    *   `cleanup_sql_database_details`, `cleanup_cassandra_keyspace_details`, etc.

This nested structure ensures that parent resources are in the graph before child resources are queried, and that cleanup jobs run in the correct order (from the bottom up).

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync(neo4j_session: neo4j.Session, credentials: Credentials, subscription_id: str, sync_tag: int, common_job_parameters: Dict)`
*   **Description:** Orchestrates the complete, hierarchical discovery and synchronization of Azure Cosmos DB accounts and their sub-resources for a given subscription.
*   **Side Effects:**
    *   Writes a large, multi-level hierarchy of nodes and relationships to the graph.
    *   Runs cleanup jobs at each level to remove stale data.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`credentials`**: An Azure `Credentials` object. (Required)
*   **`subscription_id`**: The ID of the Azure subscription to scan. (Required)
*   **`sync_tag`**: An `int` timestamp for versioning. (Required)
*   **`common_job_parameters`**: A `Dict` for cleanup jobs. (Required)
*   **Input Sources:** Called by the main Azure sync orchestrator.

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** All `get_*` functions are wrapped in `try...except` blocks that catch `ClientAuthenticationError`, `ResourceNotFoundError`, and the general `HttpResponseError`. This robust error handling prevents the entire sync from failing if a single API call fails (e.g., due to insufficient permissions on a specific resource) and allows the process to continue with other resources.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Find Publicly Exposed Cosmos DB Accounts**
    *   **Scenario:** A security team wants to identify all Cosmos DB accounts that allow public network access and do not have any IP range filters applied.
    *   **Integration:** The properties on the `:AzureCosmosDBAccount` node make this query straightforward.
        ```cypher
        MATCH (a:AzureCosmosDBAccount)
        WHERE a.publicnetworkaccess = 'Enabled' AND size(a.ipranges) = 0
        RETURN a.id, a.name, a.resourcegroup
        ```

*   **Use Case 2: Full Hierarchy Mapping**
    *   **Scenario:** A developer needs to understand the full path to a specific MongoDB collection, including its parent database and account.
    *   **Integration:** The clear `CONTAINS` relationships allow for easy traversal of the entire resource hierarchy.
        ```cypher
        MATCH path = (sub:AzureSubscription)-[:RESOURCE]->(acc:AzureCosmosDBAccount)-[:CONTAINS]->(db:AzureCosmosDBMongoDBDatabase)-[:CONTAINS]->(coll:AzureCosmosDBMongoDBCollection)
        WHERE coll.name = 'myAppCollection'
        RETURN path
        ```

*   **Use Case 3: Audit Multi-Region Write Configurations**
    *   **Scenario:** A reliability engineer wants to verify that all production Cosmos DB accounts have multiple write locations enabled for high availability.
    *   **Integration:** This is a simple property check on the account node, and can be correlated with the write locations.
        ```cypher
        MATCH (a:AzureCosmosDBAccount)
        WHERE a.multiplewritelocations = false
        RETURN a.id, a.name
        ```
