# Technical Requirements: CrowdStrike Utility Module

This document provides a technical breakdown of the CrowdStrike utility module within Cartography. It is intended for developers who need to understand how Cartography handles authentication to the CrowdStrike Falcon API.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.crowdstrike.util.py`
*   **Purpose:** This is a simple helper module that centralizes the process of creating an authentication object for the CrowdStrike Falcon API. It provides a single function to generate the necessary `OAuth2` object used by all other CrowdStrike intelligence modules.

### Data Flow

The data flow is extremely simple: client credentials go in, and a ready-to-use authentication object comes out.

```mermaid
graph TD
    A[Client ID, Client Secret, API URL] --> B{get_authorization()};
    B --> C[falconpy.OAuth2 Auth Object];
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `falconpy`: The official CrowdStrike Falcon SDK for Python.

### Core Logic/Algorithm

The module contains a single function, `get_authorization()`:

1.  It accepts a `client_id`, `client_secret`, and the base `api_url` for the CrowdStrike environment.
2.  It instantiates the `falconpy.oauth2.OAuth2` class.
3.  It passes the credentials and URL to the class constructor.
4.  The `OAuth2` object itself handles the logic of requesting, storing, and automatically refreshing the OAuth2 bearer token required for all subsequent API calls.
5.  The function returns the initialized `OAuth2` object.

---

## 🏛️ Architecture and Structure

### System Integration

This utility is the first step for any CrowdStrike-related intelligence sync. A top-level orchestrator (e.g., the main `cartography` sync function) calls `util.get_authorization()` to create the authentication object. This object is then passed as the `authorization` parameter to the other CrowdStrike sync functions like `endpoints.sync_hosts()` and `spotlight.sync_vulnerabilities()`. Those functions, in turn, pass the object to their specific `falconpy` API clients (`Hosts`, `Spotlight_Vulnerabilities`, etc.).

```mermaid
graph TD
    A[Start CrowdStrike Sync] --> B(util.get_authorization);
    B --> C{OAuth2 Object};
    C --> D[endpoints.sync_hosts(authorization=OAuth2)];
    C --> E[spotlight.sync_vulnerabilities(authorization=OAuth2)];

    D --> F{Hosts(auth_object=OAuth2)};
    E --> G{Spotlight_Vulnerabilities(auth_object=OAuth2)};

    F --> H[Make API Calls];
    G --> H;
```

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `get_authorization(client_id: str, client_secret: str, api_url: str) -> OAuth2`
*   **Description:** Creates and returns an OAuth2 authorization object for use with the `falconpy` SDK.
*   **Side Effects:** When a method is first called on an API client using this object, it will make an API call to the CrowdStrike authentication endpoint to retrieve a bearer token.

### B. Input Specification

*   **`client_id`**: The client ID for the CrowdStrike API key. (Required)
*   **`client_secret`**: The client secret for the CrowdStrike API key. (Required)
*   **`api_url`**: The base URL for the CrowdStrike API (e.g., `https://api.crowdstrike.com`). (Required)

### C. Output Specification

*   **Output Data Structure:** Returns an instance of `falconpy.oauth2.OAuth2`.
*   **Error Handling:** The function itself does not perform error handling. If the credentials are invalid, an error will be raised by the `falconpy` SDK when the object is first used to make an API call.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Initialize a CrowdStrike Sync Job**
    *   **Scenario:** The main Cartography process is configured to sync CrowdStrike data.
    *   **Integration:** The main process calls this utility function first to get the auth object, which is then passed to the other CrowdStrike modules.
        ```python
        // Simplified example of how the sync is orchestrated

        import cartography.intel.crowdstrike.endpoints as endpoints
        import cartography.intel.crowdstrike.spotlight as spotlight
        import cartography.intel.crowdstrike.util as util

        # --- Main sync function ---
        # Get credentials from config
        CLIENT_ID = "..."
        CLIENT_SECRET = "..."
        API_URL = "https://api.crowdstrike.com"

        # 1. Get the auth object from the utility module
        authorization = util.get_authorization(CLIENT_ID, CLIENT_SECRET, API_URL)

        # 2. Pass the auth object to the other modules
        endpoints.sync_hosts(neo4j_session, update_tag, authorization)
        spotlight.sync_vulnerabilities(neo4j_session, update_tag, authorization)
        ```
