# Technical Requirements: Azure Storage Intelligence Module

This document provides a comprehensive technical breakdown of the Azure Storage intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this hierarchical module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.azure.storage.py`
*   **Purpose:** This module is responsible for discovering and modeling Azure Storage Accounts and the various data services they contain. It supports Blob, File, Queue, and Table storage, providing a hierarchical view from the account down to the individual containers, shares, queues, and tables.

### Data Flow

The module executes a three-level hierarchical sync. It starts by discovering all Storage Accounts, then the storage services enabled within them, and finally the data containers (blobs, files, etc.) within each service.

```mermaid
graph TD
    A[Start Sync] --> B{List Storage Accounts};
    B --> C{Load AzureStorageAccount nodes};
    C --> D{List Storage Services (Blob, File, Queue, Table) within each Account};
    D --> E{Load Service nodes (e.g., AzureStorageBlobService)};
    E --> F{List Data Containers (e.g., Blob Containers) within each Service};
    F --> G{Load Data Container nodes (e.g., AzureStorageBlobContainer)};
    G --> H[Neo4j Graph];
    H --> I[End Sync];

    subgraph "L1: Account Level"
        B
        C
    end

    subgraph "L2: Service Level"
        D
        E
    end

    subgraph "L3: Container Level"
        F
        G
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `azure-mgmt-storage`: The Azure SDK for Python, used to interact with the Azure Storage management plane.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

The sync is a three-stage process orchestrated by the main `sync()` function:

1.  **Account-Level Sync:**
    *   `get_storage_account_list()`: Fetches all Storage Accounts within the subscription.
    *   `load_storage_account_data()`: Ingests the accounts as `:AzureStorageAccount` nodes, linking them to their parent `:AzureSubscription`.

2.  **Service-Level Sync (`sync_storage_account_details`):**
    *   The `get_storage_account_details()` generator function iterates through each Storage Account and makes API calls to discover which storage services are active (e.g., `get_blob_services()`, `get_queue_services()`).
    *   `load_storage_account_details()` gathers this data and calls `_load_*_services()` functions (e.g., `_load_blob_services()`) to ingest the services as nodes (e.g., `:AzureStorageBlobService`) and create a `[:USES]` relationship from the parent `:AzureStorageAccount`.

3.  **Container-Level Sync (`sync_*_services_details`):**
    *   This final stage dives into each service. Functions like `sync_blob_services_details()` orchestrate the process for their respective service type.
    *   `get_*_services_details()` generators iterate through the service nodes and make API calls to list the containers within them (e.g., `get_blob_containers()`, `get_queues()`).
    *   `load_*_services_details()` gathers the container data and calls the final loader functions (e.g., `_load_blob_containers()`) to ingest the container nodes (e.g., `:AzureStorageBlobContainer`) and create a `[:CONTAINS]` relationship from the parent service node.

4.  **Cleanup:** A single, comprehensive cleanup job, `cleanup_azure_storage_accounts`, is run at the very end. This job is configured to remove any node in the entire storage hierarchy that was not updated during the sync, ensuring that the graph reflects the current state.

### Dependencies

*   **External:** `azure-mgmt-storage`, `neo4j-driver`
*   **Internal (Cartography):**
    *   `.util.credentials.Credentials`: The object holding Azure credentials.
    *   `cartography.util.run_cleanup_job`: Used for the final cleanup operation.

---

## 🏛️ Architecture and Structure

### System Integration

This module provides the foundational inventory for Azure Storage. The granular, hierarchical data it produces is essential for security and cost analysis. For example, by identifying blob containers with public access, it provides critical security visibility. The `:AzureStorageAccount` nodes serve as anchors for other modules, such as those that might analyze network rules or diagnostic settings associated with the account.

### Internal Components

The module is structured as a series of nested `sync -> get -> load` pipelines, one for each level of the storage hierarchy.

*   **Top-Level Orchestrator:**
    *   `sync()`: The main entry point.
*   **Account-Level Functions:**
    *   `get_storage_account_list`, `load_storage_account_data`
*   **Service-Level Functions:**
    *   `sync_storage_account_details` (orchestrator)
    *   `get_storage_account_details` (data fetching generator)
    *   `load_storage_account_details` (loading orchestrator)
    *   `_load_blob_services`, `_load_file_services`, etc.
*   **Container-Level Functions:**
    *   `sync_blob_services_details`, `sync_file_services_details`, etc. (orchestrators)
    *   `get_blob_containers`, `get_shares`, etc. (data fetching)
    *   `_load_blob_containers`, `_load_shares`, etc. (loading)
*   **Cleanup:**
    *   `cleanup_azure_storage_accounts()`: A single function to clean up the entire tree of synced storage resources.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync(neo4j_session: neo4j.Session, credentials: Credentials, subscription_id: str, sync_tag: int, common_job_parameters: Dict)`
*   **Description:** Orchestrates the complete, hierarchical discovery and synchronization of Azure Storage Accounts and their nested services and containers for a given subscription.
*   **Side Effects:**
    *   Writes a large, multi-level hierarchy of nodes and relationships to the graph.
    *   Runs a comprehensive cleanup job that may delete any stale node within the Azure Storage hierarchy.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`credentials`**: An Azure `Credentials` object. (Required)
*   **`subscription_id`**: The ID of the Azure subscription to scan. (Required)
*   **`sync_tag`**: An `int` timestamp for versioning.
*   **`common_job_parameters`**: A `Dict` for cleanup jobs.
*   **Input Sources:** Called by the main Azure sync orchestrator.

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** All data fetching functions (`get_*`) are wrapped in robust `try...except` blocks that catch `ClientAuthenticationError`, `ResourceNotFoundError`, and `HttpResponseError`. This ensures that API call failures (e.g., due to permissions) do not crash the sync, allowing it to continue with other resources.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Detect Publicly Accessible Blob Containers**
    *   **Scenario:** A security analyst needs to find all blob containers that are configured to allow public access, as this could lead to unintended data exposure.
    *   **Integration:** The `publicaccess` property on the `:AzureStorageBlobContainer` node is synced specifically for this purpose.
        ```cypher
        MATCH (sa:AzureStorageAccount)-[:USES]->(bs:AzureStorageBlobService)-[:CONTAINS]->(bc:AzureStorageBlobContainer)
        WHERE bc.publicaccess IN ['Blob', 'Container']
        RETURN sa.name, bc.name, bc.publicaccess
        ```

*   **Use Case 2: Inventory Storage Accounts Not Using HTTPS**
    *   **Scenario:** An administrator wants to enforce that all storage accounts require HTTPS traffic. They need a list of accounts that do not have this setting enabled.
    *   **Integration:** A simple property check on the `:AzureStorageAccount` node is sufficient.
        ```cypher
        MATCH (sa:AzureStorageAccount)
        WHERE sa.supportshttpstrafficonly = false
        RETURN sa.id, sa.name
        ```

*   **Use Case 3: Map the Full Hierarchy of a Storage Account**
    *   **Scenario:** A developer needs to see all the storage resources (queues, tables, etc.) contained within a specific storage account.
    *   **Integration:** The clear, hierarchical relationships (`:USES`, `:CONTAINS`) allow for easy traversal from the account down to its containers.
        ```cypher
        MATCH path = (sa:AzureStorageAccount {name: 'mycoolappstorage'})-[:USES]->(service)-[:CONTAINS]->(container)
        RETURN path
        ```
