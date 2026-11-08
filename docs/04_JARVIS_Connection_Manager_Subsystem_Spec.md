# JARVIS Connection Manager Subsystem --- Architecture & Implementation Specification

**Project:** JARVIS\
**Subsystem:** Connection Manager\
**Status:** Proposed architecture\
**Baseline:** PRD v0.1 / TRD v0.1 / Implementation Document v0.1\
**Primary goal:** Allow JARVIS to conversationally discover, configure,
authenticate, validate, securely store, activate, monitor, and revoke
integrations without hard-coding a separate onboarding implementation
for every service.

------------------------------------------------------------------------

## 1. Purpose

The Connection Manager is the subsystem responsible for turning a user's
natural-language request such as:

> "JARVIS, connect my GitHub."

into a complete, secure integration setup.

The subsystem must support integrations that authenticate through
different mechanisms, including:

-   API keys
-   Fine-grained personal access tokens
-   OAuth 2.0 / OAuth 2.1-style authorization flows
-   MCP HTTP authorization
-   MCP STDIO credentials supplied through the environment
-   Client ID / client secret
-   Service-specific credentials
-   Browser-based authorization
-   Future authentication mechanisms without redesigning the subsystem

The LLM must not be responsible for storing, transporting, or directly
handling raw secrets.

The Connection Manager should instead provide the LLM with high-level
connection state and safe actions such as:

-   `discover_integration`
-   `start_connection`
-   `get_connection_status`
-   `disconnect_integration`
-   `reconnect_integration`
-   `list_connections`

The actual credentials remain inside the local secure credential store
and are injected only into the component that needs them.

------------------------------------------------------------------------

# 2. Architectural Principles

## 2.1 Generic rather than service-specific

Do not build:

``` text
if service == "github":
    github_setup()
elif service == "gmail":
    gmail_setup()
```

Instead, define an integration manifest describing the service and its
authentication requirements.

The Connection Manager interprets the manifest and selects the
appropriate authentication flow.

------------------------------------------------------------------------

## 2.2 Authentication is not authorization

The subsystem must distinguish:

-   **Authentication:** proving who/what is connecting.
-   **Authorization:** defining what that connection is allowed to
    access or do.

For example, a GitHub fine-grained PAT can be restricted to selected
repositories and specific permissions. GitHub recommends minimum
required permissions and prefers fine-grained PATs where applicable.

------------------------------------------------------------------------

## 2.3 Credentials never belong in the LLM context

Never send raw API keys, PATs, OAuth access tokens, refresh tokens,
client secrets, or passwords to Gemini.

Gemini should receive:

``` text
GitHub connection: CONNECTED
Available capabilities:
- repository_read
- pull_request_read
- issue_read
```

It should never receive:

``` text
github_pat_xxxxxxxxx
```

------------------------------------------------------------------------

## 2.4 User authorization remains explicit

JARVIS can automate the setup process, but it must not bypass a
third-party service's consent screen, MFA, approval, or authorization
boundary.

The user remains responsible for granting access.

------------------------------------------------------------------------

## 2.5 Prefer native OAuth/browser authorization over manual token entry

If a service supports a proper OAuth flow, prefer:

``` text
JARVIS → Browser → Provider authorization → Callback → Secure token storage
```

over asking the user to copy/paste an access token.

Manual secret entry remains necessary for services that require API keys
or PATs.

------------------------------------------------------------------------

## 2.6 Least privilege

The integration should request the minimum permissions needed for the
capabilities the user wants.

If the user asks:

> "Connect GitHub so you can read my PRs."

the connection should not automatically request repository write
permission.

------------------------------------------------------------------------

## 2.7 Local-first security

JARVIS is a Windows-first desktop application.

Credentials should be stored in the operating system's secure credential
mechanism / keyring rather than plaintext files.

The existing TRD already specifies OS keyring usage.

------------------------------------------------------------------------

# 3. Complete Subsystem Architecture

``` mermaid
flowchart TB

    USER["User"]

    VOICE["Gemini 3.8 Live<br/>Voice + Reasoning + Tool Calling"]

    AGENT["JARVIS Agent Core<br/>Tool / Function Loop"]

    CM_TOOLS["Connection Manager Tools<br/>High-level agent-facing API"]

    CM["Connection Manager<br/>Orchestration Layer"]

    DISCOVERY["Integration Discovery<br/>Registry + Manifest Resolver"]

    MANIFEST["Integration Manifest<br/>Auth + Capabilities + Validation"]

    POLICY["Credential & Permission Policy<br/>Least Privilege + Safety"]

    FLOW["Authentication Flow Engine"]

    OAUTH["OAuth Flow<br/>Browser + Callback + PKCE"]

    APIKEY["API Key Flow<br/>Secure Input Form"]

    PAT["PAT / Token Flow<br/>Secure Input Form"]

    MCP_AUTH["MCP HTTP Authorization<br/>OAuth / Discovery"]

    MCP_STDIO["MCP STDIO Credential Adapter<br/>Environment / Local Config"]

    CUSTOM["Custom Auth Adapter<br/>Provider-specific"]

    UI["Local Connection UI<br/>Ephemeral HTTPS/localhost Page"]

    CALLBACK["OAuth Callback Handler"]

    VALIDATOR["Credential Validator<br/>Provider-specific health check"]

    STORE["Secure Credential Store<br/>Windows Credential Manager / OS Keyring"]

    META["Connection Metadata Store<br/>SQLite"]

    REGISTRY["Active Integration Registry"]

    MCP["MCP Client / Server Connections"]

    API["Direct API Integrations"]

    NATIVE["Native Tool Integrations"]

    HEALTH["Connection Health Monitor"]

    REVOCATION["Disconnect / Revoke Workflow"]

    AUDIT["Audit Log"]

    GITHUB["GitHub"]
    GOOGLE["Google APIs<br/>Gmail / Drive / Calendar"]
    OTHER["Other Services"]
    MCP_SERVERS["Remote / Local MCP Servers"]

    USER -->|"Natural language"| VOICE
    VOICE -->|"Tool call"| AGENT
    AGENT --> CM_TOOLS

    CM_TOOLS --> CM

    CM --> DISCOVERY
    DISCOVERY --> MANIFEST
    MANIFEST --> POLICY
    POLICY --> FLOW

    FLOW -->|"OAuth required"| OAUTH
    FLOW -->|"API key required"| APIKEY
    FLOW -->|"PAT/token required"| PAT
    FLOW -->|"MCP HTTP auth"| MCP_AUTH
    FLOW -->|"MCP STDIO"| MCP_STDIO
    FLOW -->|"Provider-specific"| CUSTOM

    APIKEY --> UI
    PAT --> UI
    CUSTOM --> UI

    OAUTH --> UI
    OAUTH --> CALLBACK
    CALLBACK --> STORE

    MCP_AUTH --> CALLBACK
    MCP_AUTH --> STORE

    UI -->|"Secret / authorization result"| STORE

    FLOW --> VALIDATOR
    STORE --> VALIDATOR

    VALIDATOR -->|"Valid"| REGISTRY
    VALIDATOR -->|"Invalid"| FLOW

    REGISTRY --> MCP
    REGISTRY --> API
    REGISTRY --> NATIVE

    MCP --> MCP_SERVERS
    API --> GITHUB
    API --> GOOGLE
    API --> OTHER

    STORE --> HEALTH
    REGISTRY --> HEALTH

    CM --> META
    CM --> AUDIT
    HEALTH --> AUDIT
    REVOCATION --> STORE
    REVOCATION --> REGISTRY
    REVOCATION --> AUDIT

    CM -->|"Connection status only"| AGENT
    AGENT -->|"Natural language response"| VOICE
    VOICE --> USER
```

------------------------------------------------------------------------

# 4. Major Components

## 4.1 Agent-facing Connection Manager Tools

Gemini must not directly manipulate credentials.

Expose a small, safe set of tools to the agent:

### `discover_integration`

Input:

``` json
{
  "service": "github"
}
```

Output:

``` json
{
  "service": "github",
  "display_name": "GitHub",
  "available": true,
  "authentication_required": true,
  "recommended_auth": "fine_grained_pat",
  "required_permissions": [
    "repo:read",
    "pull_requests:read"
  ]
}
```

The output must never contain an existing secret.

------------------------------------------------------------------------

### `start_connection`

Input:

``` json
{
  "service": "github",
  "requested_capabilities": [
    "repository_read",
    "pull_request_read"
  ]
}
```

Output:

``` json
{
  "connection_id": "conn_123",
  "status": "awaiting_user",
  "next_action": "open_local_connection_page"
}
```

The tool may cause JARVIS to open the local setup UI, but the secret
itself must not be returned to Gemini.

------------------------------------------------------------------------

### `get_connection_status`

Input:

``` json
{
  "service": "github"
}
```

Output:

``` json
{
  "service": "github",
  "status": "connected",
  "capabilities": [
    "repository_read",
    "pull_request_read"
  ],
  "credential_expires_at": "2027-01-01T00:00:00Z"
}
```

Never return:

-   API key
-   PAT
-   access token
-   refresh token
-   client secret

------------------------------------------------------------------------

### `list_connections`

Return only safe metadata:

``` json
[
  {
    "service": "github",
    "status": "connected"
  },
  {
    "service": "google",
    "status": "connected"
  }
]
```

------------------------------------------------------------------------

### `disconnect_integration`

Input:

``` json
{
  "service": "github"
}
```

This should remove local credentials and unregister the active
integration.

If the provider supports remote revocation, the integration may also
initiate provider-side revocation.

Because disconnection can be consequential, the normal JARVIS safety
policy should determine whether confirmation is required.

------------------------------------------------------------------------

# 5. Integration Manifest

Every integration should be described by a machine-readable manifest.

Example:

``` yaml
id: github
name: GitHub
version: "1.0"

description: >
  Access GitHub repositories, issues, pull requests and related resources.

transport:
  type: api
  base_url: https://api.github.com

authentication:
  strategies:

    - id: fine_grained_pat
      type: pat
      preferred: true

      setup:
        provider_url: https://github.com/settings/personal-access-tokens/new
        instructions:
          - Create a fine-grained personal access token.
          - Select the required repository access.
          - Grant only the requested permissions.
          - Copy the generated token.

      fields:
        - id: token
          label: Personal Access Token
          type: secret
          required: true

      validation:
        method: api_request
        endpoint: /user

capabilities:

  - id: repository_read
    permissions:
      - contents:read

  - id: pull_request_read
    permissions:
      - pull_requests:read

tool_provider:
  type: native_api

security:
  secret_storage: os_keyring
```

The manifest is the key abstraction that allows the Connection Manager
to scale.

------------------------------------------------------------------------

# 6. Authentication Strategy Types

The Connection Manager should initially support the following strategy
types.

## 6.1 API Key

Typical flow:

``` text
User request
    ↓
Manifest
    ↓
Explain required API key
    ↓
Open local secure form
    ↓
User enters key
    ↓
Store key
    ↓
Validate
    ↓
Register integration
```

The UI must use a password-style input and must never display the key
after submission.

------------------------------------------------------------------------

## 6.2 Personal Access Token

Example: GitHub.

GitHub currently recommends fine-grained personal access tokens over
classic PATs where applicable, with repository and permission
restrictions.

The Connection Manager should therefore allow the manifest to specify:

-   token creation URL
-   suggested permissions
-   repository scope
-   expiration recommendation
-   validation endpoint
-   provider-specific error handling

The system should not attempt to generate the user's PAT automatically
unless the provider explicitly offers a supported API for doing so.

------------------------------------------------------------------------

## 6.3 OAuth

Typical flow:

``` mermaid
sequenceDiagram
    participant U as User
    participant J as JARVIS
    participant B as Browser
    participant P as OAuth Provider
    participant C as Callback
    participant S as Secure Store

    U->>J: "Connect my Gmail"
    J->>J: Resolve Google integration manifest
    J->>J: Determine OAuth requirements
    J->>B: Open provider authorization URL
    B->>P: Authorization request
    P->>U: Login + consent
    U->>P: Approve
    P->>C: Redirect with authorization code
    C->>J: Receive callback
    J->>P: Exchange code for tokens
    P->>J: Access + refresh token
    J->>S: Store encrypted credentials
    J->>J: Validate connection
    J->>U: "Google is connected"
```

Google's documented OAuth flow uses authorization, a callback containing
an authorization code, and exchange for access/refresh tokens. OAuth
libraries should be preferred over hand-implementing protocol details.

------------------------------------------------------------------------

# 7. MCP Authentication

MCP must not be treated as a single authentication mechanism.

The Connection Manager should distinguish:

## 7.1 MCP HTTP transport

For HTTP-based MCP servers, support the MCP authorization flow.

The current MCP authorization specification defines OAuth-based
authorization for HTTP transports, including authorization-server
discovery, protected-resource metadata, resource indicators,
bearer-token use, token validation, and PKCE.

The Connection Manager should therefore implement an MCP-specific
authentication adapter rather than treating an MCP server as a generic
API-key form.

------------------------------------------------------------------------

## 7.2 MCP STDIO transport

STDIO MCP servers should not automatically be forced through the HTTP
OAuth flow.

The MCP authorization specification states that STDIO implementations
should instead retrieve credentials from the environment.

Therefore, the Connection Manager should support secure environment
injection / process configuration for STDIO integrations.

Example:

``` text
Connection Manager
      ↓
Secure Store
      ↓
Prepare child process environment
      ↓
MCP STDIO server
```

The raw credential should never be placed into persistent plaintext
configuration if it can be avoided.

------------------------------------------------------------------------

# 8. Local Connection UI

The UI is intentionally simple.

It should not be a full dashboard in the first implementation.

Example:

``` text
┌──────────────────────────────────────────────┐
│              Connect GitHub                  │
├──────────────────────────────────────────────┤
│                                              │
│  JARVIS needs a GitHub credential to        │
│  access your repositories.                   │
│                                              │
│  Required access:                             │
│    ✓ Repository read                         │
│    ✓ Pull request read                       │
│                                              │
│  [ Open GitHub Token Page ]                  │
│                                              │
│  Personal Access Token                       │
│  ┌────────────────────────────────────────┐  │
│  │ •••••••••••••••••••••••••••••••••••  │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  [ Connect ]             [ Cancel ]          │
│                                              │
└──────────────────────────────────────────────┘
```

Requirements:

-   local-only
-   short-lived session
-   random connection/session identifier
-   CSRF protection where applicable
-   no credential values in URL parameters
-   no secrets in HTML source
-   no secrets in browser local storage
-   no secrets in application logs
-   auto-expire abandoned sessions
-   destroy secret input after successful submission
-   HTTPS where practical; localhost is acceptable for local OAuth
    callback flows
-   show exactly what permissions are being requested

------------------------------------------------------------------------

# 9. Credential Storage

Use the OS keyring / secure credential store.

The database should store metadata only.

### Secure store

``` text
credential:
    service = github
    account = default
    secret = <encrypted credential>
```

### SQLite metadata

``` text
connections
------------
id
service_id
display_name
auth_strategy
status
created_at
updated_at
expires_at
last_validated_at
capabilities
credential_reference
```

Never store raw secrets in SQLite.

Never store raw secrets in:

-   YAML
-   JSON
-   `.env`
-   source code
-   Git
-   logs
-   audit events
-   telemetry
-   Gemini conversation history

------------------------------------------------------------------------

# 10. Connection Lifecycle

Every connection should have an explicit lifecycle.

``` mermaid
stateDiagram-v2
    [*] --> Discovered

    Discovered --> AwaitingUser: start_connection
    AwaitingUser --> Authenticating: user begins auth
    Authenticating --> Validating: credentials received
    Validating --> Connected: validation succeeds
    Validating --> Invalid: validation fails

    Invalid --> AwaitingUser: retry
    Connected --> Expiring: expiry detected
    Expiring --> ReauthRequired: refresh unavailable
    Expiring --> Connected: refresh succeeds

    Connected --> Disconnected: disconnect
    ReauthRequired --> Authenticating: reauthorize
    Disconnected --> [*]
```

------------------------------------------------------------------------

# 11. Credential Validation

Every authentication strategy should provide a validation method.

Examples:

``` text
GitHub PAT
    → GET /user

Google OAuth
    → token validation + permitted API request

API key
    → provider-specific authenticated health endpoint

MCP OAuth
    → authenticated MCP initialization/request
```

Validation must answer:

1.  Is the credential valid?
2.  Is it expired?
3.  Does it have sufficient permissions?
4.  Can the intended integration actually operate?
5.  What capabilities are available?

Do not consider a credential "connected" merely because it has the
correct format.

------------------------------------------------------------------------

# 12. Capability Discovery

After authentication, the Connection Manager should determine what the
integration can actually do.

Example:

``` json
{
  "service": "github",
  "capabilities": {
    "repository_read": true,
    "repository_write": false,
    "pull_request_read": true,
    "pull_request_write": false,
    "issues_read": true,
    "issues_write": false
  }
}
```

This capability set should be passed to the Tool Registry.

Gemini should see the resulting tools, not the raw credential.

------------------------------------------------------------------------

# 13. Integration With the Existing Tool Registry

The Connection Manager must integrate with the TRD's Tool Registry.

``` text
                    Tool Registry
                         │
              ┌──────────┴──────────┐
              │                     │
       Native Tools            Connected Tools
                                    │
                         ┌──────────┼──────────┐
                         │          │          │
                       GitHub     Gmail      Drive
                         │          │          │
                    Connection  Connection Connection
                     Manager      Manager    Manager
```

When a connection becomes active:

``` text
Connection Manager
      ↓
Credential available
      ↓
Integration initialized
      ↓
Tools registered
      ↓
Tool schemas exposed to Gemini
```

When disconnected:

``` text
Connection Manager
      ↓
Credential removed
      ↓
Integration shutdown
      ↓
Tools removed from registry
```

------------------------------------------------------------------------

# 14. Natural-Language Connection Workflow

Example:

### User

> "JARVIS, connect my GitHub."

### Agent

Calls:

``` text
discover_integration("github")
```

### Connection Manager

Returns:

``` text
GitHub supports:
- fine-grained PAT
- OAuth / other supported methods

For the requested GitHub capabilities, fine-grained PAT is suitable.
```

### JARVIS

Speaks:

> "GitHub requires a fine-grained personal access token for this
> connection. I'll open the GitHub token page and then give you a secure
> field to enter it."

### Connection Manager

Opens local UI.

### User

Pastes token.

### Connection Manager

``` text
Receive
  ↓
Secure memory
  ↓
Validate
  ↓
Store in OS keyring
  ↓
Register GitHub integration
  ↓
Expose tools
```

### JARVIS

> "GitHub is connected."

------------------------------------------------------------------------

# 15. Failure Handling

The Connection Manager must provide useful failures.

Examples:

### Invalid token

``` text
GitHub authentication failed.
The token was rejected.
Please generate a new token or check its permissions.
```

### Insufficient permission

``` text
GitHub is connected, but this token cannot access pull requests.
I need pull-request read permission to perform that operation.
```

### Expired OAuth token

``` text
Your Google authorization has expired.
Would you like me to reconnect Google?
```

### OAuth denied

``` text
Google authorization was cancelled.
Nothing was stored.
```

### MCP server unavailable

``` text
The MCP server is configured but currently unreachable.
The credential was not deleted.
```

------------------------------------------------------------------------

# 16. Security Requirements

These requirements are mandatory.

## Secrets

-   Never send raw secrets to Gemini.
-   Never put secrets into model prompts.
-   Never write secrets to normal application logs.
-   Never store secrets in SQLite.
-   Never commit secrets to Git.
-   Never put secrets in URL query parameters.
-   Never expose secrets through error messages.
-   Never include secrets in screenshots.
-   Never put secrets into audit events.

## UI

-   Secret fields must use password/secret input controls.
-   Connection pages must be short-lived.
-   Connection sessions must use random identifiers.
-   Abandoned sessions must expire.
-   Credentials must be cleared from memory after storage when
    practical.

## Network

-   OAuth endpoints must use HTTPS except permitted localhost
    development callbacks.
-   Validate OAuth state.
-   Implement PKCE for applicable authorization-code flows.
-   Validate redirect URIs.
-   Validate token audience where required.
-   Do not blindly forward tokens between services.

The MCP specification explicitly requires secure token handling,
audience validation, HTTPS for authorization endpoints, localhost/HTTPS
redirect URIs, and PKCE for the authorization-code flow.

------------------------------------------------------------------------

# 17. Audit Logging

The audit log may record:

``` text
2026-10-03 20:10
User initiated GitHub connection

2026-10-03 20:11
GitHub credential validation succeeded

2026-10-03 20:11
GitHub integration activated
```

It must never record:

``` text
PAT = github_pat_xxxxxxxxx
```

Audit events should contain metadata, not secrets.

------------------------------------------------------------------------

# 18. Permission Model

Connection permissions and action permissions are separate.

Example:

``` text
GitHub credential:
    repository_read
    pull_request_read

JARVIS action:
    read pull requests → allowed
    create pull request → denied
```

Even if a credential has write permissions, the JARVIS Safety Gate still
applies to potentially consequential actions.

Therefore:

``` text
Provider permissions
        +
JARVIS capability permissions
        +
JARVIS safety tier
        =
actual allowed action
```

------------------------------------------------------------------------

# 19. Discovery Model

The initial implementation should use a local integration registry.

Example:

``` text
integrations/
    github.yaml
    google.yaml
    filesystem-mcp.yaml
    browser-mcp.yaml
```

Later, this can evolve into:

``` text
Local Registry
      +
Remote Registry
      +
User-provided Integration Manifest
```

The system should eventually allow a user to say:

> "Connect this MCP server."

and provide its server URL/configuration.

The Connection Manager should inspect its metadata and determine its
supported authentication flow where the protocol permits discovery.

------------------------------------------------------------------------

# 20. Suggested Python Package Structure

``` text
src/jarvis/
│
├── connections/
│   ├── __init__.py
│   ├── manager.py
│   ├── models.py
│   ├── registry.py
│   ├── manifests.py
│   ├── lifecycle.py
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── api_key.py
│   │   ├── pat.py
│   │   ├── oauth.py
│   │   ├── mcp_oauth.py
│   │   ├── mcp_stdio.py
│   │   └── custom.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── keyring.py
│   │   └── metadata.py
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── provider_checks.py
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── sessions.py
│   │   └── templates/
│   │
│   └── providers/
│       ├── github.py
│       ├── google.py
│       └── mcp.py
```

The exact framework for the local UI can be selected during
implementation, but it should remain lightweight and local-first.

------------------------------------------------------------------------

# 21. Core Interfaces

## IntegrationProvider

``` python
class IntegrationProvider(Protocol):
    id: str

    def manifest(self) -> IntegrationManifest:
        ...

    async def validate(
        self,
        credential_ref: CredentialReference
    ) -> ValidationResult:
        ...

    async def activate(
        self,
        credential_ref: CredentialReference
    ) -> ActivatedIntegration:
        ...

    async def deactivate(self) -> None:
        ...
```

------------------------------------------------------------------------

## AuthStrategy

``` python
class AuthStrategy(Protocol):
    id: str

    async def start(
        self,
        request: ConnectionRequest
    ) -> AuthSession:
        ...

    async def complete(
        self,
        session: AuthSession
    ) -> CredentialReference:
        ...

    async def cancel(
        self,
        session: AuthSession
    ) -> None:
        ...
```

------------------------------------------------------------------------

## CredentialStore

``` python
class CredentialStore(Protocol):

    async def store(
        self,
        reference: CredentialReference,
        secret: SecretValue
    ) -> None:
        ...

    async def retrieve(
        self,
        reference: CredentialReference
    ) -> SecretValue:
        ...

    async def delete(
        self,
        reference: CredentialReference
    ) -> None:
        ...
```

The implementation must use the OS keyring / secure credential
mechanism.

------------------------------------------------------------------------

# 22. Implementation Order

This order is important.

## Phase 1 --- Data Model

Implement:

-   `IntegrationManifest`
-   `AuthStrategy`
-   `Connection`
-   `CredentialReference`
-   `Capability`
-   `ConnectionStatus`
-   `ValidationResult`

Do not implement provider-specific logic yet.

### Exit condition

Unit tests can create, serialize, validate, and persist connection
metadata without storing any raw secret.

------------------------------------------------------------------------

## Phase 2 --- Secure Credential Store

Implement:

-   OS keyring integration
-   credential references
-   store/retrieve/delete
-   metadata separation

### Exit condition

A test credential can be stored and retrieved from the secure store
while SQLite contains only a reference.

------------------------------------------------------------------------

## Phase 3 --- Local Connection UI

Implement:

-   local server
-   secure session IDs
-   secret input field
-   submit/cancel
-   expiration
-   success/error states

### Exit condition

A fake API-key integration can collect a secret and deliver it to the
Connection Manager without exposing it to the agent.

------------------------------------------------------------------------

## Phase 4 --- Generic API-Key Authentication

Implement:

``` text
API-key manifest
        ↓
UI
        ↓
secure storage
        ↓
validation
        ↓
activation
```

### Exit condition

A fake provider can be fully connected using only a manifest and generic
API-key strategy.

This proves that provider-specific onboarding is not hard-coded into the
UI.

------------------------------------------------------------------------

## Phase 5 --- Generic PAT Authentication

Implement:

-   PAT secret field
-   provider setup instructions
-   provider URL
-   optional permission display
-   validation callback

### Exit condition

GitHub can be represented through a manifest + provider validator rather
than custom UI code.

GitHub's current documentation should be used when defining its
recommended token type and permission model.

------------------------------------------------------------------------

## Phase 6 --- OAuth Engine

Implement:

-   authorization URL generation
-   state
-   PKCE
-   callback endpoint
-   authorization-code exchange
-   access token handling
-   refresh token storage
-   token refresh
-   expiration
-   revocation where supported

### Exit condition

A real OAuth provider can be connected without exposing its access or
refresh tokens to Gemini.

------------------------------------------------------------------------

## Phase 7 --- MCP HTTP Authentication

Implement:

-   protected-resource metadata discovery
-   authorization-server discovery
-   OAuth authorization
-   PKCE
-   resource parameter handling
-   bearer token handling
-   token audience validation
-   MCP connection activation

### Exit condition

A compatible remote MCP server can be discovered, authorized, connected,
and exposed through the Tool Registry.

------------------------------------------------------------------------

## Phase 8 --- MCP STDIO Authentication

Implement:

-   environment-based credentials
-   secure process environment construction
-   no plaintext credential persistence
-   child-process lifecycle

### Exit condition

A local MCP STDIO server can be started with credentials retrieved from
the secure store.

------------------------------------------------------------------------

## Phase 9 --- Integration With Tool Registry

Connect:

``` text
Connection Manager
       ↓
Tool Registry
       ↓
Gemini 3.8 Live
```

Implement dynamic registration and removal.

### Exit condition

Connecting GitHub causes GitHub tools to become available to the agent;
disconnecting GitHub removes them.

------------------------------------------------------------------------

## Phase 10 --- Natural-Language Control

Expose the safe Connection Manager tools to Gemini:

-   discover integration
-   start connection
-   get status
-   list connections
-   disconnect
-   reconnect

### Exit condition

The complete flow works:

> "Connect GitHub."

without a hard-coded GitHub conversation handler.

------------------------------------------------------------------------

## Phase 11 --- Health + Reauthentication

Implement:

-   token expiration detection
-   OAuth refresh
-   failed validation detection
-   reconnect flow
-   connection health state
-   user notifications

### Exit condition

An expired credential causes JARVIS to request reauthorization instead
of silently failing.

------------------------------------------------------------------------

## Phase 12 --- Security Hardening

Perform:

-   secret-leak tests
-   log inspection
-   prompt-injection tests
-   malformed manifest tests
-   malicious redirect tests
-   invalid OAuth state tests
-   CSRF tests
-   credential-store permission tests
-   connection-session expiration tests
-   tool-disconnect tests

### Exit condition

No raw credentials appear in:

-   prompts
-   logs
-   SQLite
-   audit events
-   URLs
-   screenshots
-   error messages

------------------------------------------------------------------------

# 23. Example End-to-End Scenarios

## Scenario A --- GitHub

``` text
User:
"Connect GitHub."

JARVIS:
Discovers GitHub.

Connection Manager:
Selects fine-grained PAT strategy.

JARVIS:
Explains required permissions.

UI:
Collects PAT.

Connection Manager:
Stores PAT securely.

Validator:
Calls GitHub.

Tool Registry:
Registers GitHub tools.

JARVIS:
"GitHub is connected."
```

------------------------------------------------------------------------

## Scenario B --- Google

``` text
User:
"Connect my Gmail."

JARVIS:
Discovers Google OAuth.

Browser:
Opens Google authorization.

User:
Signs in and approves.

Callback:
Receives authorization code.

Connection Manager:
Exchanges code for tokens.

Secure Store:
Stores refresh token.

Tool Registry:
Registers Gmail tools.

JARVIS:
"Gmail is connected."
```

------------------------------------------------------------------------

## Scenario C --- Remote MCP

``` text
User:
"Connect this MCP server."

JARVIS:
Reads server configuration.

Connection Manager:
Discovers authentication requirements.

If OAuth:
    perform MCP OAuth flow.

If API key:
    open secure API-key form.

If another supported mechanism:
    select corresponding adapter.

Connection Manager:
Validates.

Tool Registry:
Registers MCP tools.
```

------------------------------------------------------------------------

# 24. What the LLM Should and Should Not Know

## Gemini SHOULD know

-   integration name
-   connection status
-   available capabilities
-   authentication required/not required
-   safe user-facing instructions
-   whether the connection needs attention
-   which tools are currently available

## Gemini SHOULD NOT know

-   API keys
-   PAT values
-   OAuth access tokens
-   OAuth refresh tokens
-   client secrets
-   passwords
-   secret environment variables
-   raw credential-store values

The model is the reasoning layer, not the credential vault.

------------------------------------------------------------------------

# 25. Definition of Done

The Connection Manager subsystem is complete when all of the following
are true:

-   [ ] Generic integration manifests exist.
-   [ ] Authentication strategies are pluggable.
-   [ ] API-key authentication works.
-   [ ] PAT authentication works.
-   [ ] OAuth works with state + PKCE where applicable.
-   [ ] MCP HTTP authorization works according to the MCP authorization
    specification.
-   [ ] MCP STDIO credentials can be supplied securely.
-   [ ] Credentials are stored in the OS secure credential store.
-   [ ] SQLite contains metadata only.
-   [ ] Gemini never receives raw credentials.
-   [ ] Local connection UI works.
-   [ ] Credentials are validated before activation.
-   [ ] Capabilities are discovered/recorded.
-   [ ] Tool Registry dynamically activates integrations.
-   [ ] Disconnect removes access from the Tool Registry.
-   [ ] Reauthentication works.
-   [ ] Expired credentials are handled.
-   [ ] Audit logs contain no secrets.
-   [ ] Security tests cover credential leakage and OAuth attack cases.
-   [ ] A new integration can be added primarily by creating a
    manifest + provider adapter, rather than modifying the Connection
    Manager core.

------------------------------------------------------------------------

# 26. Important Design Goal

The strongest test of this subsystem is:

> **Can an AI coding agent add a new integration without modifying the
> Connection Manager's core architecture?**

Ideally:

``` text
Add integration
      ↓
Create manifest
      ↓
Choose existing auth strategy
      ↓
Implement provider validator if necessary
      ↓
Register provider
      ↓
Done
```

If adding every new service requires a new custom authentication page
and a new branch in `ConnectionManager`, the abstraction has failed.

------------------------------------------------------------------------

# 27. External Technical References

The following sources should be consulted during implementation and kept
current:

-   Model Context Protocol authorization specification:
    https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization

-   Google OAuth 2.0 for web server applications:
    https://developers.google.com/identity/protocols/oauth2/web-server

-   Google OAuth 2.0 overview:
    https://developers.google.com/identity/protocols/oauth2

-   GitHub personal access tokens:
    https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

-   GitHub fine-grained PAT permissions:
    https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens

-   GitHub credential types:
    https://docs.github.com/en/organizations/managing-programmatic-access-to-your-organization/github-credential-types

------------------------------------------------------------------------

# 28. Final Architecture Principle

The Connection Manager should make integrations feel like **capabilities
that JARVIS can acquire**, rather than features that have to be manually
programmed into JARVIS.

The intended experience is:

``` text
"JARVIS, connect X."

        ↓

Discover X

        ↓

Understand X's authentication requirements

        ↓

Explain what the user must authorize/provide

        ↓

Launch the appropriate secure setup flow

        ↓

Receive credential / authorization

        ↓

Securely store it

        ↓

Validate it

        ↓

Discover capabilities

        ↓

Activate tools

        ↓

Make tools available to Gemini

        ↓

"X is connected."
```

This architecture keeps the agent conversational while keeping
credentials outside the model and keeps the integration layer
extensible.
