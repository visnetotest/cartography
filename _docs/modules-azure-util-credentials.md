# Technical Requirements: Azure Credentials Utility

This document provides a technical breakdown of the Azure Credentials utility within Cartography. It is intended for developers who need to understand how Cartography handles Azure authentication and token management.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.azure.util.credentials.py`
*   **Purpose:** This utility module provides a standardized way to authenticate to Azure and to manage the resulting credential objects. It supports two main authentication methods: via the Azure CLI and via a Service Principal. It defines a `Credentials` class that acts as a container for different token types and a `Authenticator` class that handles the logic of obtaining these credentials.

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `azure-identity`: The modern Azure SDK library for handling authentication.
    *   `azure-common`: Older Azure SDK library, used for its CLI profile integration.
    *   `adal`: A legacy Azure AD authentication library. Used here for its token refresh capabilities.
    *   `requests`: Used as a last resort to determine the tenant ID.

### Core Classes and Logic

#### `Authenticator` Class

This class is the entry point for authentication.

*   **`authenticate_cli()`:**
    *   This is the primary method for local development and user-based authentication.
    *   It uses `get_azure_cli_credentials` to obtain two sets of credentials based on the logged-in CLI user:
        1.  **ARM Credentials:** For interacting with the standard Azure Resource Manager (ARM) API (`management.azure.com`).
        2.  **Azure AD Graph Credentials:** For interacting with the legacy Azure Active Directory Graph API (`graph.windows.net`), which is still required for some operations.
    *   It also retrieves the current user's identity (email address) from the CLI profile.
    *   It packages all of this information into a `Credentials` object and returns it.
*   **`authenticate_sp()`:**
    *   This is the method for service principal-based (non-interactive) authentication, typically used in automated environments.
    *   It takes a `tenant_id`, `client_id`, and `client_secret` as input.
    *   It uses `ClientSecretCredential` to generate both ARM and Azure AD Graph credentials.
    *   It packages this into a `Credentials` object and returns it.

#### `Credentials` Class

This class is a simple data container and utility for managing the tokens obtained by the `Authenticator`.

*   **`__init__()`:** Stores the ARM credentials, AAD Graph credentials, tenant ID, and the current user's identity.
*   **`get_tenant_id()`:** A robust method for determining the tenant ID. It tries, in order:
    1.  The `tenant_id` stored on the object itself.
    2.  The `tenant_id` embedded within the AAD Graph token.
    3.  As a last resort, it makes an authenticated call to the ARM API (`/tenants`) to discover the tenant ID.
*   **`get_credentials(resource)`:** A method to retrieve a potentially refreshed token. It was designed to handle token refreshes but is now less critical as the underlying `azure-identity` library handles this more transparently.
*   **`get_fresh_credentials()` and `refresh_credential()`:** These methods contain legacy logic using the `adal` library to manually check if a token is about to expire and, if so, refresh it. This was necessary with older Azure SDKs but is largely superseded by the automatic token management in `azure-identity`.

---

## 🏛️ Architecture and Structure

### System Integration

This utility is central to the entire Azure intelligence sync process. The main Azure orchestrator calls the `Authenticator` once at the beginning of a sync run. The resulting `Credentials` object is then passed down to every single Azure intelligence module (e.g., `compute`, `storage`, `sql`).

Each module then uses the credentials stored in this object to initialize its own API client (e.g., `ComputeManagementClient`, `StorageManagementClient`) and make authenticated calls to the Azure APIs.

```mermaid
graph TD
    A[Azure Sync Start] --> B[Authenticator.authenticate_cli/sp];
    B --> C(Credentials Object);
    C --> D[Compute Module];
    C --> E[Storage Module];
    C --> F[SQL Module];

    D --> G{ComputeManagementClient(credentials)};
    E --> H{StorageManagementClient(credentials)};
    F --> I{SqlManagementClient(credentials)};

    G --> J[Make ARM API Calls];
    H --> J;
    I --> J;
```

### Internal Components

*   `Authenticator` class: The factory for creating `Credentials` objects.
*   `Credentials` class: The container for holding and managing authentication tokens.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Primary Entry Points:**
    *   `Authenticator().authenticate_cli()`
    *   `Authenticator().authenticate_sp(tenant_id, client_id, client_secret)`
*   **Return Value:** An instance of the `Credentials` class.
*   **Description:** These methods provide the authenticated `Credentials` object necessary for all subsequent Azure API interactions.

### B. Input Specification

*   **`authenticate_cli()`**: No parameters. Relies on an active Azure CLI login session (`az login`).
*   **`authenticate_sp()`**:
    *   `tenant_id`: The ID of the Azure Tenant. (Required)
    *   `client_id`: The Application (client) ID of the Service Principal. (Required)
    *   `client_secret`: The client secret for the Service Principal. (Required)

### C. Output Specification

*   **Output Data Structure:** A `Credentials` object containing multiple token objects and metadata.
*   **Error Handling:** The authentication methods are wrapped in a `try...except HttpResponseError`. They specifically look for a common `AdalError` that occurs when a user tries to authenticate with a personal Microsoft Account (like `@outlook.com`), which is not supported. In this case, it logs a user-friendly error message before re-raising the exception.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Authenticate as a Local User**
    *   **Scenario:** A developer is running a Cartography sync from their workstation.
    *   **Integration:** The developer runs `az login`. The Cartography sync process calls `Authenticator().authenticate_cli()`, which picks up the CLI session and returns a valid `Credentials` object.

*   **Use Case 2: Authenticate in a CI/CD Pipeline**
    *   **Scenario:** A Cartography sync is configured to run automatically in a GitHub Action or Jenkins job.
    *   **Integration:** The CI/CD pipeline is configured with a Service Principal's tenant ID, client ID, and client secret as environment variables. The sync process calls `Authenticator().authenticate_sp(...)` with these values, returning a valid `Credentials` object.

*   **Use Case 3: Provide Credentials to an Intel Module**
    *   **Scenario:** The Azure Compute module needs to list all virtual machines.
    *   **Integration:** The module's `get_client()` function receives the `Credentials` object, extracts the ARM token (`credentials.arm_credentials`), and uses it to initialize the `ComputeManagementClient`, enabling it to make authenticated API requests.
