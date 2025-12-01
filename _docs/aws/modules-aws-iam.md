# Technical Requirements: AWS IAM Intelligence Module

This document provides a comprehensive technical breakdown of the AWS Identity and Access Management (IAM) intelligence module within Cartography. It is intended for developers who need to understand, integrate, and maintain this complex but critical module.

## 🏗️ Overview and Implementation Details

### Module Name and Purpose

*   **Module Name:** `cartography.intel.aws.iam.py`
*   **Purpose:** This module is responsible for syncing a comprehensive model of an AWS account's IAM landscape. It ingests users, groups, roles, policies (both managed and inline), and the relationships between them. It also models trust relationships (AssumeRole policies) and user access keys.

### Data Flow

The module performs a series of targeted syncs for each IAM entity type. It fetches entities, then their attached policies, transforms the policy documents, and loads the entire structure into the graph. A final sync step computes effective access based on the loaded data.

```mermaid
graph TD
    A[Start Sync] --> B{IAM API};
    B --> C[List Users/Groups/Roles];
    C --> D[Get Inline & Attached Policies];
    D --> E{Transform Policies & Statements};
    E --> F[Load Principals (User, Group, Role)];
    F --> G[Load Policies & Statements];
    G --> H[Load Relationships];
    H --> I[Sync AssumeRole];
    I --> J[Neo4j Graph];
    J --> K[End Sync];

    subgraph "1. Extract & Transform"
        B
        C
        D
        E
    end

    subgraph "2. Load & Analyze"
        F
        G
        H
        I
    end
```

### Technology Stack

*   **Programming Language:** Python
*   **Core Libraries:**
    *   `boto3`: The AWS SDK for Python, used extensively to query the IAM API.
    *   `neo4j`: The official Python driver for Neo4j.

### Core Logic/Algorithm

The sync is orchestrated by the main `sync()` function, which calls a series of sub-sync functions in a specific order:

1.  **Sync Principals (`sync_users`, `sync_groups`, `sync_roles`):**
    *   For each principal type, it lists all entities (e.g., `list_users`).
    *   It loads these entities as `:AWSUser`, `:AWSGroup`, and `:AWSRole` nodes, all of which are also labeled `:AWSPrincipal`.
    *   For each principal, it then fetches both their **inline** policies and their **attached managed** policies.
2.  **Sync Policies (`load_policy_data`):**
    *   The raw JSON policy documents are transformed. The `transform_policy_data` function ensures statements are in a list format and generates unique IDs for each policy and statement.
    *   `load_policy_data` `MERGE`s `:AWSPolicy` nodes and connects them to their parent principal with a `[:POLICY]` relationship.
    *   `load_policy_statements` then `MERGE`s `:AWSPolicyStatement` nodes for each statement in the policy and connects them to the parent `:AWSPolicy` with a `[:STATEMENT]` relationship.
3.  **Sync Group Memberships (`sync_group_memberships`):**
    *   It queries the graph to get the list of synced groups.
    *   For each group, it calls `get_group_membership_data` to find its member users.
    *   It creates a `[:MEMBER_AWS_GROUP]` relationship from each `:AWSUser` to the `:AWSGroup`.
4.  **Sync AssumeRole Relationships (`sync_assumerole_relationships`):**
    *   This is a critical analysis step. It first loads the trust policies for all roles.
    *   Then, it queries the graph to find potential `(source:AWSPrincipal)` -> `(target:AWSRole)` trust relationships.
    *   For each potential relationship, it fetches the *source* principal's IAM policies and checks if they contain an `sts:AssumeRole` permission that applies to the *target* role's ARN.
    *   If access is allowed, it creates an `[:STS_ASSUMEROLE_ALLOW]` relationship, making the trust relationship explicit in the graph.
5.  **Sync Access Keys (`sync_user_access_keys`):**
    *   Queries the graph for all users.
    *   For each user, calls `get_account_access_key_data` to fetch their access keys and, importantly, the last used information for each key.
    *   Loads this data as `:AccountAccessKey` nodes linked to the `:AWSUser`.
6.  **Cleanup:** Numerous cleanup jobs are run throughout the process to remove stale principals, policies, relationships, and keys.

### Dependencies

*   **External:** `boto3`, `neo4j-driver`
*   **Internal (Cartography):**
    *   `cartography.intel.aws.permission_relationships`: Contains the logic (`principal_allowed_on_resource`) for the `sts:AssumeRole` analysis.
    *   `cartography.util.run_cleanup_job`: Used for all cleanup operations.

---

## 🏛️ Architecture and Structure

### System Integration

The IAM module is arguably the most important module for AWS security analysis. It provides the "who" and "what" of permissions. Its output is fundamental for nearly every other AWS module, which often need to determine what IAM principals have access to their resources (e.g., "who can read this S3 bucket?"). The `sync_assumerole_relationships` function is a powerful example of in-graph analysis, turning raw data (policy documents) into explicit, queryable relationships.

### Internal Components

*   **Main Entry Point:**
    *   `sync()`: The top-level orchestrator.
*   **Sub-Sync Functions:**
    *   `sync_users()`, `sync_groups()`, `sync_roles()`, `sync_group_memberships()`, `sync_user_access_keys()`: Orchestrate the sync for a specific part of IAM.
    *   `sync_assumerole_relationships()`: The in-graph analysis function for trust relationships.
*   **Data Fetching (`get_*`):**
    *   A large number of functions that use both `boto3.client` and `boto3.resource` to fetch data (e.g., `get_user_list_data`, `get_role_managed_policy_data`).
*   **Data Loading (`load_*`):**
    *   Functions responsible for executing Cypher queries to load principals, policies, statements, and relationships (e.g., `load_users`, `load_policy_data`).
*   **Data Transformation:**
    *   `transform_policy_data()`, `_transform_policy_statements()`: Functions that normalize the complex IAM policy JSON into a structure suitable for graph ingestion.

---

## 🔗 External Interfaces and Contracts

### A. Public Interface (API)

*   **Main Entry Point:** `sync(neo4j_session: neo4j.Session, boto3_session: boto3.session.Session, regions: List[str], current_aws_account_id: str, update_tag: int, common_job_parameters: Dict)`
*   **Description:** Orchestrates the complete discovery and synchronization of IAM entities and their permissions for a given AWS account.
*   **Side Effects:**
    *   Writes a large and complex set of nodes and relationships to the graph, including `:AWSPrincipal`, `:AWSUser`, `:AWSGroup`, `:AWSRole`, `:AWSPolicy`, `:AWSPolicyStatement`, and `:AccountAccessKey`.
    *   Creates numerous relationship types, including `:RESOURCE`, `:POLICY`, `:STATEMENT`, `:MEMBER_AWS_GROUP`, and the analytically-derived `:STS_ASSUMEROLE_ALLOW`.
    *   Runs multiple cleanup jobs.

### B. Input Specification

*   **`neo4j_session`**: An active `neo4j.Session` object. (Required)
*   **`boto3_session`**: An active `boto3.session.Session` object. (Required)
*   **`regions`**: A `List[str]`. IAM is a global service, so this is not used for API calls but is passed through for consistency. (Required)
*   **`current_aws_account_id`**: The 12-digit ID of the AWS account. (Required)
*   **`update_tag`**: An `int` timestamp for versioning. (Required)
*   **`common_job_parameters`**: A `Dict` for cleanup jobs. (Required)
*   **Input Sources:** Called by the main AWS sync orchestrator.

### C. Output Specification

*   **Output Data Structure:** Returns `None`. Its output is the state change in the Neo4j database.
*   **Error Handling:** The `get_*` functions include `try...except NoSuchEntityException` blocks to handle cases where an IAM entity is deleted during the sync, preventing crashes.

---

## 🎯 Use Cases and Scenarios

*   **Use Case 1: Analyze Effective Permissions**
    *   **Scenario:** A security engineer needs to know if a specific user (`my-user`) can perform a specific action (`s3:GetObject`) on a specific resource (`my-bucket`).
    *   **Integration:** The graph created by this module allows for a powerful effective permissions query. This involves traversing from the user to their groups, to their policies, and to the statements within those policies, checking for allows and denies.
        ```cypher
        // Simplified example - a full query is much more complex
        MATCH (u:AWSUser{name: 'my-user'})-[:MEMBER_AWS_GROUP*0..]->(p:AWSPrincipal)
        MATCH (p)-[:POLICY]->(policy)-[:STATEMENT]->(stmt)
        WHERE 's3:GetObject' IN stmt.action AND stmt.effect = 'Allow'
        RETURN p.arn, policy.name
        ```

*   **Use Case 2: Discover Role Chaining (Privilege Escalation)**
    *   **Scenario:** An auditor wants to find potential privilege escalation paths where a user can assume a role, which can then assume another, more powerful role.
    *   **Integration:** The `:STS_ASSUMEROLE_ALLOW` relationship is perfect for this. One can query for chains of these relationships.
        ```cypher
        MATCH path = (p1:AWSPrincipal)-[:STS_ASSUMEROLE_ALLOW*]->(p2:AWSRole)
        WHERE p1 <> p2
        RETURN path
        ```

*   **Use Case 3: Find Stale or Unused Access Keys**
    *   **Scenario:** A security administrator wants to enforce a policy of rotating or deleting access keys that have not been used in over 90 days.
    *   **Integration:** The `lastuseddate` property on the `:AccountAccessKey` node makes this trivial.
        ```cypher
        MATCH (u:AWSUser)-[:AWS_ACCESS_KEY]->(k:AccountAccessKey)
        WHERE k.lastuseddate < (timestamp() - (90 * 24 * 3600 * 1000)) // 90 days in milliseconds
        RETURN u.name, k.accesskeyid, k.lastuseddate
        ```
