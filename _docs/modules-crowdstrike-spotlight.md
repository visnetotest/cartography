# Technical Requirements: CrowdStrike Spotlight Intelligence Module

This document provides a comprehensive technical breakdown of the CrowdStrike Spotlight intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.crowdstrike.spotlight.py`
*   **Purpose:** This module extends the CrowdStrike intelligence by connecting to the Falcon API's Spotlight service. It retrieves detailed information about all vulnerabilities identified on managed endpoints and ingests this data, along with associated CVE information, into the Cartography graph.

### Data Flow

The module fetches vulnerability data in batches, processes it, and loads it into Neo4j in a two-phase process (vulnerabilities, then CVEs).

```mermaid
graph TD
    A[Start Sync] --> B{Get all open vulnerability IDs from Falcon API};
    B --> C{Paginate through vuln IDs (batches of 400)};
    C --> D{For each batch, get detailed vulnerability data};
    D --> E{Transform data: Separate Vulns and CVEs};
    E --> F{Load SpotlightVulnerability nodes & link to CrowdstrikeHost};
    F --> G{Load CVE nodes & link to SpotlightVulnerability};
    G --> C;
    C --> H[Neo4j Graph];
    H --> I[End Sync];

    subgraph "Fetch, Process, & Load in Batches"
        C
        D
        E
        F
        G
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `falconpy`: The official CrowdStrike Falcon SDK for Python, used for all API interactions.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

1.  **Authentication:** The `sync_vulnerabilities` function receives a pre-configured `falconpy.OAuth2` object, which handles the API authentication lifecycle.
2.  **Vulnerability ID Retrieval (`get_spotlight_vulnerability_ids`):**
    *   An API call is made to `queryVulnerabilities` with a filter `status:!"closed"` to retrieve only currently open vulnerabilities.
    *   The API results are paginated using an `after` token. The function loops, making calls with the `after` token until no more results are returned, collecting vulnerability IDs in batches of 400.
3.  **Vulnerability Detail Retrieval (`get_spotlight_vulnerabilities`):**
    *   The main sync function iterates through the batches of IDs.
    *   For each batch, it calls `getVulnerabilities` to fetch the full details for all vulnerabilities in that batch.
4.  **Data Loading (`load_vulnerability_data` and `_load_cves`):**
    *   **Transformation:** The raw data for each vulnerability is processed. A flattened `vuln` object is created, and the nested `cve` object is extracted into a separate list (`cves`). A back-reference (`vuln_id`) is added to the CVE object to maintain the relationship during the load phase.
    *   **Phase 1: Load Vulnerabilities:** A Cypher query is executed to `UNWIND` the batch of processed `vuln` objects. For each one, it:
        1.  `MERGE`s a `:SpotlightVulnerability` node.
        2.  `MATCH`es the corresponding `:CrowdstrikeHost` node (ingested by the `endpoints` module) on the agent ID (`aid`).
        3.  `MERGE`s a `[:HAS_VULNERABILITY]` relationship from the host to the vulnerability.
    *   **Phase 2: Load CVEs:** The `_load_cves` function is called with the extracted list of CVEs. A second Cypher query is executed to `UNWIND` this list. For each CVE, it:
        1.  `MERGE`s a `(:CVE:CrowdstrikeFinding)` node using the CVE identifier (e.g., `CVE-2021-44228`).
        2.  `MATCH`es the parent `:SpotlightVulnerability` using the `vuln_id` that was added during transformation.
        3.  `MERGE`s a `[:HAS_CVE]` relationship from the vulnerability to the CVE node.

### Dependencies

*   **External:** `falconpy`
*   **Internal (Cartography):** This module depends on the `crowdstrike.endpoints` module having already run and created `:CrowdstrikeHost` nodes.

---

## 🏛️ Architecture and Structure

### System Integration

This module creates a detailed graph of host-level vulnerabilities. It builds directly upon the host inventory created by the `endpoints` module. The resulting data model allows for complex queries that connect high-level CVEs to the specific hosts and applications they affect.

The graph model is as follows:
`(:CrowdstrikeHost)-[:HAS_VULNERABILITY]->(:SpotlightVulnerability)-[:HAS_CVE]->(:CVE:CrowdstrikeFinding)`

### Internal Components

*   **Top-Level Orchestrator:**
    *   `sync_vulnerabilities()`: The entry point that orchestrates the get and load process.
*   **Data Fetching:**
    *   `get_spotlight_vulnerability_ids()`: Paginates through the `queryVulnerabilities` endpoint.
    *   `get_spotlight_vulnerabilities()`: Fetches details for a given list of vulnerability IDs.
*   **Data Loading:**
    *   `load_vulnerability_data()`: Transforms the raw API data and loads the `:SpotlightVulnerability` nodes and their relationships to hosts.
    *   `_load_cves()`: A helper function to load the `:CVE` nodes and their relationships to vulnerabilities.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync_vulnerabilities(neo4j_session: neo4j.Session, update_tag: int, authorization: OAuth2)`
*   **Description:** Orchestrates the complete discovery and synchronization of CrowdStrike Spotlight vulnerabilities.
*   **Side Effects:**
    *   Writes `:SpotlightVulnerability` nodes.
    *   Writes `:CVE:CrowdstrikeFinding` nodes.
    *   Creates `[:HAS_VULNERABILITY]` and `[:HAS_CVE]` relationships.
    *   Sets the `lastupdated` property on all created/updated nodes and relationships.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`update_tag`**: The timestamp for the sync run. (Required)
*   **`authorization`**: A `falconpy.OAuth2` object initialized with valid CrowdStrike API credentials. (Required)

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** Relies on the `falconpy` SDK to handle API errors. A warning is logged if the initial query returns no vulnerabilities.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Find All Hosts with a Critical Vulnerability**
    *   **Scenario:** A major vulnerability (e.g., Log4Shell) is announced, and a security analyst needs to immediately find all affected hosts.
    *   **Integration:** A query that traverses from the CVE to the affected hosts.
        ```cypher
        MATCH (c:CVE {id: 'CVE-2021-44228'})<-[:HAS_CVE]-(v:SpotlightVulnerability)<-[:HAS_VULNERABILITY]-(h:CrowdstrikeHost)
        RETURN h.hostname, h.os_version, v.app_product_name_version, v.status
        ```

*   **Use Case 2: Prioritize Remediation by Host**
    *   **Scenario:** An infrastructure owner wants to identify which of their servers has the most severe vulnerabilities to prioritize patching.
    *   **Integration:** Group vulnerabilities by host and score, then order the results.
        ```cypher
        MATCH (h:CrowdstrikeHost)-[:HAS_VULNERABILITY]->(v:SpotlightVulnerability)-[:HAS_CVE]->(c:CVE)
        RETURN h.hostname, c.base_severity AS severity, count(v) AS vulnerability_count
        ORDER BY h.hostname, severity DESC
        ```

*   **Use Case 3: List Vulnerable Software Products**
    *   **Scenario:** A security team wants to understand which software products are introducing the most risk into their environment.
    *   **Integration:** A query that aggregates vulnerabilities by the vulnerable application.
        ```cypher
        MATCH (v:SpotlightVulnerability)
        WHERE v.app_product_name_version IS NOT NULL
        RETURN v.app_product_name_version AS vulnerable_product, count(*) AS open_vulnerabilities
        ORDER BY open_vulnerabilities DESC
        LIMIT 20
        ```
