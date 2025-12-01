# Technical Requirements: Azure Subscription Intelligence Module

This document provides a comprehensive technical breakdown of the Azure Subscription intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this foundational module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.azure.subscription.py`
*   **Purpose:** This module is responsible for ingesting information about Azure Subscriptions. It creates the top-level `:AzureSubscription` nodes within the graph, which serve as the root anchor for nearly all other Azure resources. It also ensures the parent `:AzureTenant` node exists and is linked.

### Data Flow

The module's data flow is simple. It takes a pre-fetched list of subscription objects and loads them into the graph, ensuring they are connected to the correct tenant.

```mermaid
graph TD
    A[Start Sync] --> B{Subscription Data (pre-fetched)};
    B --> C{Load AzureTenant & AzureSubscription nodes};
    C --> D[Create Tenant-to-Subscription relationship];
    D --> E[Neo4j Graph];
    E --> F[End Sync];

    subgraph "Load"
        C
        D
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `azure-mgmt-resource`: The Azure SDK for Python, used here for its subscription client to fetch subscription data.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

The module's `sync()` function is very direct:

1.  **`load_azure_subscriptions()`:** This is the core function. It iterates through a list of subscription dictionaries passed into the `sync` function.
    *   For each subscription, it executes a Cypher query that performs a series of `MERGE` operations:
        1.  `MERGE` an `:AzureTenant` node using the provided `tenant_id`.
        2.  `MERGE` an `:AzureSubscription` node using the subscription's unique ID.
        3.  `MERGE` a `[:RESOURCE]` relationship from the `:AzureTenant` to the `:AzureSubscription`.
    *   The properties of the subscription (display name, state, etc.) are set on the `:AzureSubscription` node.
2.  **`cleanup()`:** After loading, a cleanup job is run to remove any `:AzureSubscription` nodes that were not touched during the current sync, ensuring that deleted or inaccessible subscriptions are removed from the graph.

**Note on Data Fetching:** This module contains helper functions (`get_all_azure_subscriptions`, `get_current_azure_subscription`) for retrieving subscription data from Azure. However, the main `sync()` function expects the list of subscriptions to be passed in from a higher-level orchestrator. This design allows the main Azure sync logic to fetch the list of subscriptions once and pass it to all other modules that need it, avoiding redundant API calls.

### Dependencies

*   **External:** `azure-mgmt-resource`, `neo4j-driver`
*   **Internal (Cartography):**
    *   `.util.credentials.Credentials`: The object holding Azure credentials.
    *   `cartography.util.run_cleanup_job`: For the cleanup operation.

---

## 🏛️ Architecture and Structure

### System Integration

This is a foundational, high-priority module for Azure ingestion. It establishes the top-level asset nodes to which all other Azure resources will be connected. Nearly every other Azure intelligence module depends on the `:AzureSubscription` nodes created by this sync job to properly anchor their own discovered resources within the graph.

### Internal Components

*   **Main Entry Point:**
    *   `sync()`: Orchestrates the load and cleanup operations.
*   **Data Fetching (Helpers):**
    *   `get_all_azure_subscriptions()`, `get_current_azure_subscription()`: Functions to retrieve subscription information from Azure. Not directly used by the `sync` function itself.
*   **Data Loading:**
    *   `load_azure_subscriptions()`: Contains the Cypher query to load tenants and subscriptions into Neo4j.
*   **Cleanup:**
    *   `cleanup()`: Calls the generic cleanup job runner with the specific job file for subscriptions.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync(neo4j_session: neo4j.Session, tenant_id: str, subscriptions: List[Dict], update_tag: int, common_job_parameters: Dict)`
*   **Description:** Ingests a list of Azure subscriptions into the graph, linking them to a specified tenant.
*   **Side Effects:**
    *   Writes/updates `:AzureTenant` and `:AzureSubscription` nodes.
    *   Creates/updates `[:RESOURCE]` relationships between them.
    *   Runs a cleanup job, which may delete stale `:AzureSubscription` nodes and their relationships to the tenant.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`tenant_id`**: The ID of the Azure Tenant that owns the subscriptions. (Required)
*   **`subscriptions`**: A `List[Dict]` where each dictionary represents an Azure subscription. This data is expected to be provided by the caller. (Required)
*   **`update_tag`**: An `int` timestamp for versioning the sync run. (Required)
*   **`common_job_parameters`**: A `Dict` containing metadata for the cleanup job. (Required)
*   **Input Sources:** Called by the main Azure sync orchestrator.

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** The `get_*` helper functions contain `try...except HttpResponseError` blocks to handle cases where the provided credentials do not have access to any subscriptions, preventing crashes and logging an informative error.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Enumerate All Monitored Subscriptions**
    *   **Scenario:** An administrator wants a simple list of all Azure subscriptions that are currently being monitored by Cartography for a specific tenant.
    *   **Integration:** This is a direct query on the nodes created by this module.
        ```cypher
        MATCH (t:AzureTenant {id: 'your-tenant-id'})-[:RESOURCE]->(s:AzureSubscription)
        RETURN s.name, s.id, s.state
        ```

*   **Use Case 2: Provide an Anchor for Resource Inventory**
    *   **Scenario:** A security analyst needs to find all virtual machines within a subscription that has a specific name (e.g., "Production").
    *   **Integration:** The `:AzureSubscription` node serves as the starting point for the query, which then traverses to other resource types created by different modules.
        ```cypher
        MATCH (s:AzureSubscription {name: 'Production')-[:RESOURCE]->(vm:AzureVirtualMachine)
        RETURN vm.name, vm.id, vm.location
        ```
