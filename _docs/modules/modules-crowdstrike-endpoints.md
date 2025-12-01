# Technical Requirements: CrowdStrike Endpoints Intelligence Module

This document provides a comprehensive technical breakdown of the CrowdStrike Endpoints intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.crowdstrike.endpoints.py`
*   **Purpose:** This module connects to the CrowdStrike Falcon API, retrieves detailed information about all managed endpoints (hosts), and ingests that data into the Cartography graph.

### Data Flow

The module uses a paginated approach to efficiently retrieve data for a large number of hosts.

```mermaid
graph TD
    A[Start Sync] --> B{Get a list of all host IDs from Falcon API};
    B --> C{Paginate through host IDs (batches of 5000)};
    C --> D{For each batch of IDs, get detailed host data};
    D --> E{Load batch of hosts into Neo4j};
    E --> C;
    C --> F[Neo4j Graph];
    F --> G[End Sync];

    subgraph "Fetch & Load in Batches"
        C
        D
        E
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `falconpy`: The official CrowdStrike Falcon SDK for Python, used for all API interactions.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

1.  **Authentication:** The main `sync_hosts` function receives an `authorization` object, which is an `OAuth2` instance from `falconpy`. This object is expected to be pre-configured with the necessary API client ID and secret and handles the token acquisition and refresh lifecycle automatically.
2.  **Host ID Retrieval (`get_host_ids`):**
    *   An initial API call is made to `QueryDevicesByFilter` to get the first batch of host IDs. By default, the batch size is 5000, which is the maximum allowed by the API.
    *   The response contains a `pagination` object with an `offset`. The code enters a `while` loop that continues as long as a new `offset` is returned, indicating there are more pages of results.
    *   In each loop, a new call is made with the updated `offset` to get the next batch of host IDs.
    *   All retrieved ID lists are collected and returned.
3.  **Host Detail Retrieval (`get_hosts`):**
    *   The main `sync_hosts` function iterates through the lists of host IDs.
    *   For each list, it calls `get_hosts`, which makes a single API call to `GetDeviceDetails`. This endpoint accepts a comma-separated string of up to 5000 IDs, efficiently fetching detailed information for all hosts in the batch.
    *   The `resources` list from the response body, containing a list of host detail dictionaries, is returned.
4.  **Data Loading (`load_host_data`):**
    *   After each batch of host details is retrieved, it is immediately sent to `load_host_data`.
    *   This function uses Cartography's generic `load()` function along with the `CrowdstrikeHostSchema` to write the batch of `:CrowdstrikeHost` nodes to the graph.
    *   This batch-oriented approach is memory-efficient, as it avoids loading all host details into memory at once.

### Dependencies

*   **External:** `falconpy`
*   **Internal (Cartography):**
    *   `cartography.client.core.tx.load`: The generic data loading function.
    *   `cartography.models.crowdstrike.hosts.CrowdstrikeHostSchema`: The data model and schema for `:CrowdstrikeHost` nodes.

---

## 🏛️ Architecture and Structure

### System Integration

This module provides crucial endpoint security data from CrowdStrike. It is a key source for mapping infrastructure assets (like cloud VMs) to their real-world endpoint security posture. By linking `:CrowdstrikeHost` nodes to other assets (e.g., via IP address or hostname), analysts can answer questions like "Show me all critical vulnerabilities on EC2 instances running in production" or "Which of our servers are missing the CrowdStrike agent?"

### Internal Components

*   **Top-Level Orchestrator:**
    *   `sync_hosts()`: The main entry point that orchestrates the entire get and load process.
*   **Data Fetching:**
    *   `get_host_ids()`: Paginates through the `QueryDevicesByFilter` endpoint to get all host IDs.
    *   `get_hosts()`: Fetches detailed information for a given list of host IDs.
*   **Data Loading:**
    *   `load_host_data()`: Prepares and executes the load operation for a batch of hosts.

**Note:** A key design feature is the lack of a separate top-level `cleanup` function. The `load()` function with the `CrowdstrikeHostSchema` implicitly handles the attachment of the `lastupdated` tag. A separate, generic graph cleanup job (not defined in this module) is responsible for removing nodes that are no longer present.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync_hosts(neo4j_session: neo4j.Session, update_tag: int, authorization: OAuth2)`
*   **Description:** Orchestrates the complete discovery and synchronization of CrowdStrike hosts.
*   **Side Effects:**
    *   Writes `:CrowdstrikeHost` nodes for all discovered endpoints.
    *   Sets the `lastupdated` property on the nodes to the current `update_tag`.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`update_tag`**: The timestamp for the sync run. (Required)
*   **`authorization`**: A `falconpy.OAuth2` object that has been initialized with valid CrowdStrike API credentials (client ID and client secret). (Required)

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** The module relies on the underlying `falconpy` SDK to handle API errors. If an API call fails, the SDK will typically raise an exception, which will halt the sync for this module. There is a warning log if the initial query for host IDs returns no results.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Full Endpoint Inventory**
    *   **Scenario:** A security analyst needs a complete inventory of all systems with the CrowdStrike Falcon agent installed.
    *   **Integration:** A direct query on the nodes created by this module.
        ```cypher
        MATCH (h:CrowdstrikeHost)
        RETURN h.hostname, h.os_version, h.local_ip, h.last_seen
        ```

*   **Use Case 2: Correlate Cloud Assets with Endpoint Agents**
    *   **Scenario:** An infrastructure owner wants to identify all AWS EC2 instances that are also monitored by CrowdStrike.
    *   **Integration:** This requires linking the data from this module with data from the AWS EC2 module, typically by matching IP addresses.
        ```cypher
        MATCH (e:EC2Instance)-[:HAS_INTERFACE]->(ni:NetworkInterface)-[:ASSOCIATED_WITH]->(pip:PublicIp)
        MATCH (h:CrowdstrikeHost) WHERE pip.ip = h.external_ip
        RETURN e.id, e.instanceid, h.hostname, h.agent_version
        ```

*   **Use Case 3: Find Endpoints with Out-of-Date Agents**
    *   **Scenario:** A security team wants to ensure the Falcon agent is kept up-to-date across the fleet.
    *   **Integration:** The `agent_version` property can be compared against the latest known version.
        ```cypher
        MATCH (h:CrowdstrikeHost)
        WHERE h.agent_version <> '7.01.23456' // Replace with the current agent version
        RETURN h.hostname, h.agent_version, h.os_version
        ```
