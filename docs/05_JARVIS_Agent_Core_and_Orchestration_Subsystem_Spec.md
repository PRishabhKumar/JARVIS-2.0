# JARVIS Agent Core, Cognitive Architecture, and Task Orchestration Subsystem

**Document type:** Architecture and implementation specification  
**Audience:** Human developers and agentic coding tools such as Antigravity, Codex, Claude Code, Cursor, or equivalent systems  
**Target platform:** Local-first Windows personal assistant  
**Primary language:** Python 3.12+  
**Status:** Implementation baseline  
**Companion specification:** JARVIS Connection Manager and PC Control Subsystems Specification

---

# 1. Purpose

This document is the authoritative build specification for the JARVIS Agent Core. The Agent Core is the cognitive and orchestration layer that converts unrestricted natural-language requests into bounded, authorized, observable, and verifiably completed tasks.

The subsystem must support requests that were never explicitly programmed. It must not depend on a fixed vocabulary, a fixed command list, or chains of if/else statements that directly map phrases to actions. It must instead operate on declared capabilities, structured goals, typed plans, policy decisions, verified tool results, and durable task state.

The Agent Core decides what should happen. It does not directly implement operating-system actions, store service credentials, or bypass security controls.

It must handle requests such as:

> Check whether the CareerMitra project has any local changes or commits that have not been pushed. Summarize them and tell me whether it appears safe to publish.

> Find the latest email concerning the Caterpillar hackathon, explain what action is required, and prepare a reply. Do not send anything until I approve it.

> Continue what we were doing yesterday, but use my personal GitHub account and do not modify the backend.

These requests require interpretation, reference resolution, planning, tool selection, policy enforcement, execution, verification, memory, interruption handling, and explanation. This document defines those responsibilities.

---

# 2. Normative Instructions for Coding Agents

Any coding agent implementing this specification must follow these rules.

1. Read this complete document and the companion Connection Manager and PC Control specification before modifying code.
2. Treat **MUST**, **MUST NOT**, **SHOULD**, and **MAY** as normative requirements.
3. Do not replace typed contracts with free-form dictionaries at subsystem boundaries.
4. Do not allow an LLM response to directly execute a tool. Every proposed action must pass schema validation, resource resolution, policy evaluation, authorization checks, and the Tool Gateway.
5. Do not expose credentials, approval tokens, internal policy data, or raw secret-bearing tool output to any model.
6. Do not introduce unrestricted shell execution. Command execution must use typed command profiles from the PC Control subsystem.
7. Do not make the model the source of truth for permissions, task state, tool success, or verification.
8. Do not mark a mutating step complete because a tool merely returned success. Required postconditions must be verified.
9. Preserve user changes in an existing repository. Inspect before editing and avoid unrelated rewrites.
10. Implement each phase behind interfaces and feature flags where appropriate. Keep the system runnable after every phase.
11. Add database migrations for every durable schema change.
12. Add the tests required by each phase. A phase is incomplete until its exit conditions pass.
13. Use deterministic fakes for model providers, time, tools, approvals, and external services in automated tests.
14. Never make automated tests depend on paid APIs, real email accounts, real repositories, or uncontrolled desktop input.
15. Log structured metadata with redaction. Do not log secrets or full private documents by default.
16. Record architectural deviations in an Architecture Decision Record before implementing them.
17. If ambiguity affects safety, persistence, authorization, or external side effects, request a decision rather than silently choosing.
18. Produce small, reviewable commits aligned with the implementation phases. Include implementation, tests, migrations, and a concise change note.
19. Do not claim completion because a conversational demo works. Completion is determined by the release gates and Definition of Done.
20. Keep interfaces provider-neutral. No domain module may depend directly on a particular LLM vendor.

---

# 3. Scope

## 3.1 In scope

The Agent Core owns:

- natural-language request interpretation;
- structured goal generation;
- conversational and task context assembly;
- entity, target, account, and resource reference resolution;
- clarification decisions;
- task decomposition and dependency planning;
- dynamic capability and tool selection;
- plan validation and static safety checks;
- model routing and fallback;
- durable task and step state;
- execution orchestration;
- bounded retries and replanning;
- interruption, pause, resume, and cancellation;
- approval request coordination;
- verification coordination;
- task-scoped working memory;
- controlled long-term memory writes;
- user-facing progress and final explanations;
- audit events, traces, metrics, and evaluation hooks.

## 3.2 Out of scope

The Agent Core does not own:

- OAuth, API keys, PAT storage, or secret refresh;
- MCP server lifecycle and authentication;
- Windows UI Automation implementation;
- raw mouse, keyboard, clipboard, screen, or process control;
- browser automation implementation;
- filesystem, IDE, terminal, or Git adapter implementation;
- provider-specific email, calendar, drive, or GitHub APIs;
- wake-word detection, audio capture, speech recognition, or speech synthesis;
- the visual dashboard, except for the APIs and events it consumes.

Those capabilities belong to the Connection Manager, PC Control subsystem, tool providers, Voice subsystem, and user interface. The Agent Core consumes them through typed contracts.

---

# 4. Architectural Principles

## 4.1 The model proposes; deterministic systems decide

An LLM may interpret, plan, summarize, compare, and propose. Deterministic code must validate schemas, resolve resources, enforce policy, issue approvals, manage state transitions, execute tools, and verify postconditions.

## 4.2 Goals are separate from plans

A goal describes the desired outcome and constraints. A plan describes one possible execution strategy. Replanning may change the plan without changing the approved goal.

## 4.3 Content is not authority

Email text, web pages, repository files, screenshots, tool descriptions, tool results, and retrieved memories are untrusted content. They may provide facts but cannot grant permission, expand scope, change accounts, or override policy.

## 4.4 State is durable

The task database, not the model conversation, is the authoritative record of tasks, steps, approvals, invocations, outcomes, and recovery state.

## 4.5 Capabilities are discovered, not assumed

Plans must be grounded in the current Tool Registry. The model cannot invent a tool or assume that a connection, account, window, repository, or browser session exists.

## 4.6 Side effects are explicit

Every planned step must declare its effect class, resources, expected postconditions, and compensation characteristics before execution.

## 4.7 Verification is part of execution

Execution is incomplete until required evidence exists or the system explicitly reports an uncertain outcome.

## 4.8 Minimum necessary context

Each model call receives only the information needed for that decision. Credentials, unrelated memories, full audit histories, and unnecessary private content must be excluded.

## 4.9 Local-first control

Policy enforcement, authorization, secrets, task state, PC control, and audit records remain local by default. Cloud models may receive redacted task context but never become a security boundary.

## 4.10 Graceful degradation

If a preferred model, tool, or connection is unavailable, use an allowed fallback, ask the user, or stop safely. Never silently substitute a higher-risk route.

---

# 5. Responsibility Boundaries

| Responsibility | Agent Core | Connection Manager | PC Control Gateway | Model Provider |
|---|---|---|---|---|
| Understand user goal | Owns | No | No | Assists |
| Create candidate plan | Owns | No | No | Assists |
| Discover capabilities | Consumes | Publishes connected tools | Publishes local tools | No |
| Store credentials | Never | Owns | Never | Never receives them |
| Resolve resources | Coordinates | Resolves accounts/connections | Resolves PC resources | Suggests aliases only |
| Decide authorization | Requests and obeys | Enforces connection scope | Enforces action policy | Never |
| Execute service action | Orchestrates | Routes | No | Never |
| Execute PC action | Orchestrates | No | Owns | Never |
| Verify outcome | Coordinates | Supplies evidence | Supplies evidence | Summarizes evidence only |
| Maintain task state | Owns | Connection state only | Invocation state only | No |
| Maintain user memory | Owns through Memory Service | No | Device/project facts only | No |

The Agent Core MUST NOT call a provider SDK, MCP server, OS API, browser driver, Git binary, or UI Automation API directly. Every effectful action enters through the unified Tool Gateway.

---

# 6. High-Level Architecture

~~~mermaid
flowchart TD
    IN["Voice, Text, Events"] --> SESSION["Session and Context Manager"]
    SESSION --> UNDERSTAND["Goal Interpreter"]
    UNDERSTAND --> RESOLVE["Reference Resolver"]
    RESOLVE --> PLAN["Planner"]
    PLAN --> VALIDATE["Plan Validator and Policy Preflight"]
    VALIDATE --> ORCH["Durable Orchestrator"]
    ORCH --> GATEWAY["Unified Tool Gateway"]
    GATEWAY --> CM["Connection Manager"]
    GATEWAY --> PC["PC Control Gateway"]
    CM --> VERIFY["Verification Coordinator"]
    PC --> VERIFY
    VERIFY --> ORCH
    ORCH --> MEMORY["Memory Service"]
    ORCH --> OUT["Progress and Response Composer"]
~~~

Cross-cutting components:

- Policy and Approval Service
- Model Router
- Capability Catalog
- Event Store and Audit Log
- Redaction and Trust-Label Service
- Cancellation Service
- Observability and Evaluation Service

---

# 7. Core Domain Contracts

Use Pydantic v2 with strict validation and generated JSON Schema. Persisted enums must use stable string values.

## 7.1 Identifiers

Use UUIDv7 or ULID identifiers for sortable uniqueness.

Required IDs include:

~~~text
session_id
turn_id
task_id
goal_id
plan_id
step_id
invocation_id
approval_id
evidence_id
memory_id
trace_id
~~~

IDs emitted by a model are never authoritative. The runtime creates all authoritative identifiers.

## 7.2 Structured goal

~~~python
class GoalSpec(BaseModel):
    goal_id: UUID
    task_id: UUID
    user_request: str
    objective: str
    target_refs: list[ResourceReference]
    requested_outputs: list[OutputRequirement]
    constraints: list[Constraint]
    prohibitions: list[Prohibition]
    completion_conditions: list[Postcondition]
    interaction_mode: Literal["interactive", "guided", "delegated"]
    maximum_effect: Literal["read", "local_write", "remote_write", "privileged"]
    ambiguity: list[Ambiguity]
    confidence: float
    created_at: datetime
~~~

The original request is retained for traceability but must not be reparsed as new authority after a structured goal is accepted. Prohibitions take precedence over requested outputs.

## 7.3 Trust-labelled context

~~~python
class ContextItem(BaseModel):
    item_id: UUID
    source_type: Literal[
        "user_current", "user_prior", "system_policy", "tool_registry",
        "memory", "email", "web", "document", "repository", "tool_result"
    ]
    trust_class: Literal["authority", "trusted_fact", "untrusted_content"]
    content: str | dict
    resource_id: str | None
    observed_at: datetime
    expires_at: datetime | None
    content_hash: str
    sensitivity: Literal["public", "internal", "private", "secret"]
~~~

Only the current authenticated user input, a cryptographically bound approval, and system policy may convey action authority. Prior user messages provide context but must be checked for continued applicability.

## 7.4 Plan and steps

~~~python
class PlanSpec(BaseModel):
    plan_id: UUID
    task_id: UUID
    goal_id: UUID
    revision: int
    steps: list[PlanStep]
    assumptions: list[Assumption]
    unresolved_questions: list[ClarificationQuestion]
    estimated_cost: CostEstimate
    created_by_model: str
    capability_snapshot_hash: str
    policy_version: str

class PlanStep(BaseModel):
    step_id: UUID
    ordinal: int
    title: str
    purpose: str
    depends_on: list[UUID]
    capability_query: CapabilityQuery
    selected_tool_id: str | None
    selected_tool_version: str | None
    arguments_template: dict
    resource_refs: list[ResourceReference]
    effect: Literal["read", "local_write", "remote_write", "privileged"]
    expected_postconditions: list[Postcondition]
    approval_requirement: Literal["none", "policy", "explicit"]
    retry_policy: RetryPolicy
    timeout_ms: int
    compensation: CompensationSpec | None
~~~

The planner may initially specify a capability query. The Tool Selector resolves it against the current catalog. A plan cannot execute until each executable step has a concrete tool version and validated argument schema.

## 7.5 Normalized tool result

Consume the ToolResult contract from the companion specification:

~~~json
{
  "status": "succeeded",
  "structured_data": {},
  "changed_resources": [],
  "evidence_refs": [],
  "error_code": null,
  "retryable": false,
  "execution_uncertain": false
}
~~~

Missing fields must never be interpreted as success.

---

# 8. Request Ingestion and Turn Handling

Every input becomes a TurnEnvelope:

~~~python
class TurnEnvelope(BaseModel):
    turn_id: UUID
    session_id: UUID
    actor_id: str
    modality: Literal["voice", "text", "event", "ui"]
    text: str
    received_at: datetime
    speech_confidence: float | None
    device_id: str
    foreground_context_ref: str | None
    reply_to_task_id: UUID | None
~~~

The ingestion layer must:

1. authenticate the local user or record identity confidence;
2. redact transport-level secrets;
3. classify whether the turn starts a task, modifies a task, answers a clarification, grants approval, cancels work, or requests status;
4. associate the turn with a task only at sufficient confidence;
5. preserve original and corrected transcripts separately for voice;
6. ask the user to repeat low-confidence consequential instructions;
7. apply rate limits and duplicate-turn detection;
8. create a trace and durable turn record before cognitive processing.

Cancellation phrases such as “stop,” “cancel that,” and “do not send it” must pass through a deterministic high-priority interrupt classifier before normal planning.

---

# 9. Goal Interpretation

The Goal Interpreter converts a turn and bounded context into a GoalSpec. It extracts:

- requested outcome;
- targets and aliases;
- requested information or artifacts;
- explicit constraints;
- explicit prohibitions;
- implied effect ceiling;
- temporal conditions;
- ambiguity and confidence;
- whether the request modifies an existing task.

Use structured output constrained by the GoalSpec JSON Schema. Free-form parsing of model prose is prohibited.

The runtime must deterministically add restrictions implied by the phrasing:

| User phrasing | Enforced interpretation |
|---|---|
| “Check”, “inspect”, “tell me” | Read-only unless another explicit verb authorizes change |
| “Draft”, “prepare” | Create a draft; do not publish |
| “Open” | Launch or focus only |
| “Commit” | Local Git write; no push authorization |
| “Commit and push” | Exact reviewed change set and selected remote only |
| “Delete” | Resolve exact target and require destructive approval |

If the model omits an explicit prohibition, deterministic post-processing must restore it. If interpretation confidence is below the configured threshold, the task moves to clarification rather than planning.

---

# 10. Context Assembly

The Context Manager builds a bounded ContextBundle for each cognitive operation. Context sources are queried separately and labelled.

Recommended order:

1. system policy and safety configuration;
2. current user turn;
3. active task state and accepted goal;
4. directly relevant prior turns;
5. current capability snapshot;
6. resolved resource metadata;
7. relevant working memory;
8. retrieved long-term memory;
9. untrusted content needed for the task.

Support token budgeting, summarization, deduplication, and freshness. Never silently truncate current prohibitions, pending approvals, failed postconditions, or cancellation state.

Every model request carries a context manifest with item IDs, trust labels, sensitivities, and hashes. Retain the manifest for debugging without retaining secret payloads.

Context compaction must be deterministic for authority-bearing elements. Summaries of user constraints must be checked against the structured goal before use.

---

# 11. Reference and Resource Resolution

The Reference Resolver converts aliases such as “CareerMitra,” “my personal account,” “that file,” “the last email,” or “him” into canonical resource candidates.

Resolution sources include:

- project registry;
- Connection Manager accounts and connections;
- PC Control resource registry;
- open windows and tabs;
- conversation entities;
- contact directory;
- recent task resources;
- user-approved aliases.

Return candidates with evidence:

~~~python
class ResolutionResult(BaseModel):
    reference_text: str
    candidates: list[ResourceCandidate]
    selected: ResourceIdentity | None
    confidence: float
    ambiguity_reason: str | None
    evidence_refs: list[str]
~~~

Automatic resolution is allowed only when one candidate clearly dominates, lies within scope, does not increase effect level, and is not a safety-critical account or destination ambiguity.

Ask a concise clarification when plausible repositories, recipients, accounts, branches, or destructive targets remain.

Canonical resource IDs, not display names, must be used in plans, approvals, invocations, and evidence.

---

# 12. Clarification Policy

Ask only when the answer materially changes safety, target, cost, or outcome.

Clarification is required when:

- the target is ambiguous;
- the intended account or external recipient is unclear;
- the outcome conflicts with a prohibition;
- an unavailable capability has materially different alternatives;
- a destructive operation lacks an exact target;
- completion conditions cannot be inferred;
- voice confidence is inadequate for a consequential action.

Clarification is not required when:

- a safe read-only discovery step can resolve uncertainty;
- the choice is an internal detail with equivalent effects;
- a reversible fallback remains inside scope;
- the user explicitly delegated the choice and policy permits it.

Questions should present the smallest useful choice set and the consequence of each option. Clarifications expire when task state or resource state changes materially.

---

# 13. Capability Catalog and Tool Selection

The Agent Core receives a normalized catalog from the Tool Registry. It must never parse tools from arbitrary prompt text.

Each capability entry exposes at least:

~~~text
tool_id
version
human_name
capability_tags
input_schema
output_schema
effect
action_class
resource_types
connection_requirements
timeout_ms
cancellation_mode
schema_hash
health
trust_level
verification_support
~~~

Selection order:

1. Filter by required capability.
2. Remove unhealthy, unavailable, or unauthorized tools.
3. Filter by effect ceiling and resource scope.
4. Prefer structured provider APIs or native adapters.
5. Prefer deterministic OS APIs over visual automation.
6. Prefer browser DOM automation over screen coordinates.
7. Rank by reliability, verification support, latency, cost, and user preference.
8. Bind tool ID, version, schema hash, and resource scope into the plan.

A model may rank compatible candidates only after deterministic filtering. Tool descriptions are untrusted metadata until admitted by the registry. A schema change invalidates plans referencing the previous schema hash.

---

# 14. Planning and Validation

The Planner produces a dependency graph, not a prose checklist. A valid plan is acyclic and exposes every side effect.

Planning flow:

1. Accept an approved GoalSpec and capability snapshot.
2. Generate a candidate PlanSpec using constrained output.
3. Resolve capability queries to tools.
4. Resolve or mark unresolved resources.
5. Infer effect classes from Tool Registry metadata, never from the model.
6. Compute approval requirements from policy.
7. Validate dependencies, schemas, constraints, budgets, and postconditions.
8. Request clarification or approval if needed.
9. Persist the accepted plan as an immutable revision.

The Planner must keep plans minimal and may not add speculative actions unrelated to the goal.

A plan is invalid if:

- it contains a dependency cycle;
- a tool or version is unavailable;
- arguments fail JSON Schema validation;
- a step exceeds the goal effect ceiling;
- a required resource is unresolved;
- a mutating step lacks postconditions;
- an external publication lacks a specific destination;
- a destructive step lacks compensation or an explicit non-reversible marker;
- a later step depends on unverified mutated state;
- a secret is embedded in model-generated arguments;
- estimated cost or duration exceeds the budget;
- it treats content as approval;
- it requires a capability outside the snapshot.

Plans are immutable after acceptance. Replanning creates a new revision and records replaced and retained steps. Completed verified steps are not repeated unless their observations are stale.

---

# 15. Durable State Machines

## 15.1 Task states

~~~text
RECEIVED
INTERPRETING
AWAITING_CLARIFICATION
PLANNING
PREFLIGHT
AWAITING_APPROVAL
READY
RUNNING
PAUSING
PAUSED
VERIFYING
REPLANNING
COMPLETED
PARTIALLY_COMPLETED
BLOCKED
FAILED
CANCELLING
CANCELLED
ROLLING_BACK
ROLLED_BACK
~~~

## 15.2 Step states

~~~text
PENDING
BLOCKED_BY_DEPENDENCY
READY
AWAITING_APPROVAL
EXECUTING
VERIFYING
SUCCEEDED
FAILED_RETRYABLE
FAILED_TERMINAL
SKIPPED
CANCELLED
UNCERTAIN
COMPENSATING
COMPENSATED
~~~

Validate all transitions with deterministic transition tables. Direct database state edits that bypass the state machine are prohibited.

Each transition must atomically append an event and update the current projection. Use optimistic concurrency with a version column so two workers cannot advance the same task.

Terminal status must follow all step outcomes. A task with an uncertain side effect may not be reported as simply failed or completed.

---

# 16. Execution Orchestrator

The Orchestrator executes only accepted plans as a durable, resumable loop.

~~~python
async def run_task(task_id: UUID) -> None:
    task = await task_store.lock_and_load(task_id)

    while not task.is_terminal:
        await cancellation.check(task_id)
        step = await scheduler.next_ready_step(task)

        if step is None:
            await scheduler.resolve_wait_or_terminal_state(task)
            return

        decision = await policy.preflight(task, step)

        if decision.requires_approval:
            await approvals.request(task, step, decision)
            continue

        if not decision.allowed:
            await tasks.block(task, decision.reason)
            return

        invocation = await invocations.create_idempotent(task, step)
        result = await tool_gateway.invoke(invocation)
        await invocations.record_result(invocation, result)

        if result.execution_uncertain:
            await tasks.mark_uncertain(task, step)
            return

        verification = await verifier.verify(task, step, result)
        await evidence.record(verification)

        if verification.satisfied:
            await steps.succeed(step)
        else:
            await failure_manager.handle(task, step, result, verification)
~~~

Production code must use transactions, leases, timeouts, cancellation tokens, and complete error handling.

Independent read-only steps may run concurrently when they do not compete for resources or leak data across boundaries. Mutating steps on the same resource are serialized. Desktop input requires the exclusive lease defined in the PC Control specification.

Each invocation has a dedupe key derived from task, plan revision, step, tool version, canonical resource, and normalized arguments. A retry must reconcile previous results before repeating a side effect.

Each task has explicit budgets for:

- wall-clock time;
- model calls;
- tool invocations;
- retries;
- replans;
- external cost;
- output size;
- parallelism.

Exceeding a budget pauses or blocks work. It never silently expands the budget.

---

# 17. Policy and Approval Integration

Evaluate policy during goal interpretation, plan validation, and immediately before invocation. Final preflight uses current machine state, connection state, tool schema hash, resource identity, and policy version.

An approval request shows:

- exact action;
- canonical target;
- account or Windows identity;
- important arguments;
- expected effects;
- reversibility;
- relevant before-state;
- expiry.

Approval tokens use the canonical intent binding from the companion specification. The Agent Core stores only an approval reference and consumption result. It cannot create or alter a valid token.

Approvals are single-use unless policy creates a constrained grant. A changed file set, recipient, branch, remote, account, destination, tool version, argument set, or before-state invalidates approval.

A voice “yes” may approve only when it is securely associated with one visible pending approval, speaker identity is sufficient, the action is not in a class requiring UI confirmation, and the complete target was just presented.

---

# 18. Verification Coordinator

Every mutating step declares machine-checkable postconditions. Read-only steps require evidence sufficient to support the answer.

The coordinator:

1. selects the verifier declared by the tool or action class;
2. obtains a fresh observation through an independent path where possible;
3. compares it with expected postconditions;
4. records evidence hashes and structured results;
5. returns satisfied, failed, stale, or uncertain;
6. blocks dependants until required verification passes.

Prefer structured provider responses, DOM queries, filesystem hashes, Git refs, process queries, and API reconciliation over screenshots.

User-facing outcomes distinguish:

- completed and verified;
- completed but verification unavailable;
- partially completed;
- blocked before execution;
- failed with no side effect;
- uncertain and requiring inspection.

Evidence references must be immutable, access-controlled, redacted for display, and linked to invocation and task IDs.

---

# 19. Failure Handling and Replanning

Classify before retrying.

| Failure class | Examples | Default response |
|---|---|---|
| Transient | timeout, temporary outage | Bounded exponential backoff |
| Stale state | file, window, or branch changed | Refresh and replan |
| Authentication | expired connection | Ask Connection Manager to reauthenticate |
| Authorization | scope denied, approval absent | Request authorization or stop |
| Ambiguity | multiple targets | Clarify |
| Capability loss | tool disconnected or changed | Select allowed alternative or stop |
| Validation | malformed argument/output | Repair once, then fail |
| Safety | policy denial or injection signal | Block and report |
| Uncertain effect | timeout after possible mutation | Reconcile; never blindly retry |
| Terminal | target absent, invariant violated | Fail with actionable explanation |

Replanning remains inside the accepted goal and effect ceiling. It may not change recipient, account, project, branch, remote, or prohibited resources without clarification or renewed approval.

The replan context includes goal, completed verified steps, observations, failure class, remaining budget, and allowed capabilities. It excludes credentials and unrelated history.

---

# 20. Interruption, Cancellation, and Resume

User interruption has priority over planning and normal execution.

Required operations:

- pause the current task;
- resume a paused task;
- cancel the current task;
- cancel all desktop-input tasks;
- change a constraint;
- answer a clarification;
- deny an approval;
- request status.

On cancellation:

1. set the cancellation flag immediately;
2. stop scheduling new steps;
3. propagate cancellation tokens;
4. terminate owned process trees when safe;
5. release leases;
6. reconcile possibly completed actions;
7. offer rollback where supported;
8. report what did and did not occur.

The PC Control emergency stop works independently of the LLM and Agent Core loop.

After restart, reconstruct tasks from durable state, reconcile EXECUTING and VERIFYING steps, renew valid leases, and never repeat a side effect without idempotency reconciliation.

A new user request may supersede, amend, or coexist with active work. The turn classifier must identify which and must not silently abandon a mutating task.

---

# 21. Memory Architecture

Do not use one undifferentiated vector database as the source of truth.

| Memory class | Examples | Storage | Default lifetime |
|---|---|---|---|
| Turn context | Current conversation | Session store | Session |
| Working memory | Active plan facts | Task store | Task plus recovery window |
| Episodic | “We deployed Friday” | Memory store | Configurable |
| Semantic | Project aliases, preferences | Structured store | Until changed |
| Procedural | Approved reusable workflow | Versioned procedure store | Until invalidated |
| Resource | Repository path, editor | Resource registry | Until revalidated |
| Audit | Actions and evidence | Audit store | Policy-defined |

The LLM may propose memory; deterministic policy decides whether to save it. Each record includes provenance, confidence, sensitivity, owner, retention, and invalidation conditions.

Never store:

- passwords, tokens, cookies, private keys, or approval nonces;
- inferred sensitive traits not requested by the user;
- full private documents when a minimal fact is enough;
- untrusted instructions as procedural memory;
- temporary output without a defined future purpose.

User corrections override values without deleting provenance. Time-sensitive memory requires expiry or revalidation.

Retrieval order:

1. filter by owner, task, resource type, sensitivity, and validity;
2. search exact aliases and structured keys;
3. use semantic retrieval when needed;
4. rerank for relevance and recency;
5. return a small labelled set with provenance.

Retrieved memory is context, never authorization.

---

# 22. Model Router

Do not hardcode one model.

~~~python
class ModelClient(Protocol):
    async def generate_structured(
        self,
        request: ModelRequest,
        output_schema: dict,
        cancellation_token: CancellationToken,
    ) -> ModelResponse: ...
~~~

Profiles declare:

~~~text
profile_id
provider
model_id
allowed_data_classes
supports_structured_output
supports_tools
supports_vision
maximum_context
latency_class
cost_class
local_or_remote
health
~~~

Recommended routes:

| Operation | Preferred profile |
|---|---|
| Interrupt classification | Deterministic rules plus small local classifier |
| Goal extraction | Fast structured-output model |
| Simple plan | Fast capable model |
| Complex plan/replan | Strong reasoning model |
| Screenshot interpretation | Vision model |
| Sensitive summarization | Local model or redacted remote context |
| Final response | Fast model or deterministic template |

Fallbacks must preserve data policy. A remote fallback cannot receive data restricted to local inference.

Record provider, model, prompt-template version, context-manifest hash, schema version, latency, token use, estimated cost, and validation result for each call.

---

# 23. Prompt and Structured Output Design

Prompts are versioned application code. Store them as tested templates, not scattered inline strings.

Each cognitive prompt states:

- one role for the call;
- authoritative goal and constraints;
- which context is untrusted;
- allowed capabilities;
- prohibited behaviors;
- output schema;
- uncertainty behavior;
- prohibition on inventing tools, resources, or approvals.

Model output uses strict schema validation. On failure:

1. allow one schema-repair call with validation errors;
2. reject unknown fields where strictness is required;
3. never execute partially parsed actions;
4. emit MODEL_OUTPUT_INVALID after budget exhaustion.

Prompt injection defense cannot rely only on wording. Trust labels, tool filtering, resource scopes, and external policy are mandatory.

Never persist or display hidden chain-of-thought. Store decisions, structured rationale codes, evidence, and user-facing explanations instead.

---

# 24. Response and Progress Composition

Communicate outcomes rather than hidden reasoning. Useful progress examples:

- “Inspecting the repository status.”
- “I found three modified files and one unpushed commit.”
- “Waiting for approval to push commit abc1234 to origin/main.”

Do not expose credentials, raw approval tokens, policy internals, or verbose traces.

A final response includes:

1. outcome status;
2. concise answer or artifact;
3. material actions performed;
4. verification status;
5. incomplete or uncertain items;
6. a next action only when useful.

Voice output should be shorter than visual output. Detailed evidence stays available in the dashboard.

---

# 25. Event Model

Use append-only domain events with an outbox.

Minimum events:

~~~text
turn.received
goal.interpreted
clarification.requested
clarification.resolved
plan.created
plan.accepted
plan.invalidated
task.state_changed
step.ready
approval.requested
approval.resolved
invocation.started
invocation.finished
verification.finished
replan.requested
memory.proposed
memory.saved
task.completed
task.failed
task.cancelled
~~~

Each event includes event ID, aggregate ID and version, event type, timestamp, actor, trace ID, redacted payload, and schema version.

The initial implementation may use SQLite/PostgreSQL tables and an in-process dispatcher. Kafka is unnecessary for a single-user local system.

---

# 26. Persistence Model

Use SQLAlchemy 2.x async models and Alembic. SQLite is the local default. Keep transaction behavior compatible with PostgreSQL where practical.

| Table | Purpose |
|---|---|
| sessions | Conversation identity and state |
| turns | User and assistant turns with modality |
| tasks | Current task projection, budgets, state, version |
| goals | Immutable structured goal revisions |
| plans | Immutable plan revisions |
| steps | Step definitions and current state |
| invocations | Tool calls, dedupe keys, results, uncertainty |
| verifications | Postcondition outcomes |
| evidence | Evidence metadata and protected references |
| clarifications | Questions, answers, and expiry |
| approval_refs | Approval references and consumption |
| memories | Memory metadata and content references |
| resources | Canonical identities and aliases |
| task_events | Append-only events |
| outbox | Reliable event delivery |
| model_calls | Model metadata, use, and schema outcome |

Large, sensitive, or binary payloads belong in an encrypted content store referenced by ID. Do not place screenshots, audio, credentials, or entire documents in ordinary audit rows.

All records need created and updated timestamps where appropriate. Mutable projections need version columns. Immutable records must not be overwritten.

---

# 27. Local Service API

Expose FastAPI on loopback by default.

~~~text
POST   /v1/turns
GET    /v1/tasks
GET    /v1/tasks/{task_id}
POST   /v1/tasks/{task_id}/pause
POST   /v1/tasks/{task_id}/resume
POST   /v1/tasks/{task_id}/cancel
POST   /v1/tasks/{task_id}/clarifications/{clarification_id}
POST   /v1/tasks/{task_id}/approvals/{approval_id}/decision
GET    /v1/tasks/{task_id}/events
GET    /v1/tasks/{task_id}/evidence
GET    /v1/capabilities
GET    /v1/health
~~~

Use Server-Sent Events or WebSockets for progress. Mutating endpoints require local authentication, CSRF protection where browser-accessible, and idempotency keys.

The API must not expose raw prompts, secrets, unrestricted database queries, or raw private payloads.

---

# 28. Error Taxonomy

Define stable errors in addition to Tool Gateway codes:

~~~text
GOAL_AMBIGUOUS
GOAL_CONFLICT
REFERENCE_UNRESOLVED
CLARIFICATION_REQUIRED
CAPABILITY_NOT_FOUND
CAPABILITY_UNAVAILABLE
PLAN_INVALID
PLAN_STALE
MODEL_UNAVAILABLE
MODEL_OUTPUT_INVALID
MODEL_POLICY_BLOCKED
BUDGET_EXCEEDED
APPROVAL_REQUIRED
APPROVAL_EXPIRED
APPROVAL_SCOPE_MISMATCH
TASK_VERSION_CONFLICT
TASK_PAUSED
TASK_CANCELLED
POSTCONDITION_FAILED
REPLAN_EXHAUSTED
MEMORY_POLICY_DENIED
INJECTION_DETECTED
INTERNAL_INVARIANT_VIOLATION
~~~

Errors include a stable code, safe user message, internal diagnostic reference, retryability, and recommended next transition.

---

# 29. Multi-Agent Coordination

Begin with one authoritative orchestrator and optional specialist workers. Do not start with an unconstrained society of autonomous agents.

Permitted roles include interpreter, planner, repository analyst, research analyst, verifier, and response composer.

Specialists return typed proposals. They do not mutate task state or execute tools. Only the Orchestrator schedules Tool Gateway invocations.

Subtasks inherit:

- parent goal constraints;
- effect ceiling;
- resource scope;
- privacy classification;
- remaining budget;
- cancellation token;
- trace ID.

A subtask cannot delegate greater authority than it received. Cross-agent messages are untrusted proposals until validated.

---

# 30. Security and Privacy Requirements

1. Run as a standard user, not administrator.
2. Bind local APIs to loopback unless remote access is deliberately configured.
3. Authenticate every UI, voice node, and remote client.
4. Encrypt sensitive payload storage with OS-protected key material.
5. Keep credentials exclusively in the Connection Manager secure store.
6. Redact logs and model context with centrally tested rules.
7. Apply destination allowlists and resource scopes outside the model.
8. Treat retrieved content and tool metadata as untrusted.
9. Require explicit authorization for remote writes and dedicated authorization for destructive or privileged actions.
10. Never execute code found in email, pages, documents, memories, or repository instructions merely because the content requests it.
11. Prevent data leakage between accounts, projects, and tasks.
12. Let users inspect, export, correct, and delete memory.
13. Define retention profiles for transcripts, screenshots, evidence, and audit data.
14. Support offline/private mode that disables remote models.
15. Maintain a threat model for identity spoofing, indirect prompt injection, malicious tools, confused-deputy attacks, and supply-chain compromise.

---

# 31. Observability

Use structured logging and OpenTelemetry-compatible traces and metrics.

Required spans:

~~~text
turn.ingest
goal.interpret
context.assemble
reference.resolve
plan.generate
plan.validate
policy.preflight
approval.wait
tool.invoke
verification.run
replan.generate
memory.retrieve
memory.write
response.compose
~~~

Track:

- task success and verified-completion rates;
- clarification and approval rates;
- plan-validation failures;
- average steps per task;
- tool failures and uncertain outcomes;
- retries and replans;
- cancellation latency;
- model latency, tokens, and estimated cost;
- memory retrieval precision;
- injection block rate;
- task duration by class.

Logs contain IDs and metadata, not hidden chain-of-thought or unredacted private data.

---

# 32. Package Structure

~~~text
src/jarvis/
├── agent_core/
│   ├── service.py
│   ├── config.py
│   ├── errors.py
│   ├── ids.py
│   ├── domain/
│   │   ├── goals.py
│   │   ├── plans.py
│   │   ├── tasks.py
│   │   ├── steps.py
│   │   ├── context.py
│   │   ├── events.py
│   │   └── transitions.py
│   ├── ingestion/
│   │   ├── turns.py
│   │   ├── interrupts.py
│   │   └── identity.py
│   ├── cognition/
│   │   ├── interpreter.py
│   │   ├── planner.py
│   │   ├── replanner.py
│   │   ├── clarifier.py
│   │   ├── tool_selector.py
│   │   └── response_composer.py
│   ├── context/
│   │   ├── assembler.py
│   │   ├── budget.py
│   │   ├── trust.py
│   │   └── redaction.py
│   ├── resources/
│   │   ├── resolver.py
│   │   ├── aliases.py
│   │   └── registry.py
│   ├── orchestration/
│   │   ├── orchestrator.py
│   │   ├── scheduler.py
│   │   ├── state_machine.py
│   │   ├── budgets.py
│   │   ├── retries.py
│   │   ├── failure_manager.py
│   │   └── cancellation.py
│   ├── policy/
│   │   ├── client.py
│   │   ├── preflight.py
│   │   └── approvals.py
│   ├── verification/
│   │   ├── coordinator.py
│   │   ├── postconditions.py
│   │   └── evidence.py
│   ├── memory/
│   │   ├── service.py
│   │   ├── retrieval.py
│   │   ├── write_policy.py
│   │   └── invalidation.py
│   ├── models/
│   │   ├── base.py
│   │   ├── router.py
│   │   ├── profiles.py
│   │   ├── structured_output.py
│   │   └── providers/
│   ├── prompts/
│   │   ├── interpreter/
│   │   ├── planner/
│   │   ├── replanner/
│   │   └── composer/
│   ├── persistence/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── unit_of_work.py
│   │   ├── event_store.py
│   │   └── outbox.py
│   ├── api/
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   └── events.py
│   └── observability/
│       ├── logging.py
│       ├── tracing.py
│       ├── metrics.py
│       └── evaluation.py
├── connections/
├── pc_control/
└── tool_registry/

tests/
├── unit/agent_core/
├── contract/agent_core/
├── integration/agent_core/
├── e2e/agent_core/
├── adversarial/agent_core/
└── fixtures/
~~~

---

# 33. Technology Baseline

| Concern | Technology |
|---|---|
| Runtime | Python 3.12+ and asyncio |
| API | FastAPI and Uvicorn |
| Validation | Pydantic v2 and JSON Schema |
| Persistence | SQLAlchemy 2.x async |
| Migrations | Alembic |
| Local database | SQLite in WAL mode |
| Production option | PostgreSQL |
| HTTP | HTTPX |
| Retry primitives | Tenacity or a small explicit wrapper |
| Logging | Structured JSON logging |
| Tracing | OpenTelemetry |
| Testing | pytest, pytest-asyncio, Hypothesis |
| Formatting/linting | Ruff |
| Type checking | Pyright or mypy strict mode |

Do not introduce Redis, Kafka, Celery, Kubernetes, or a distributed workflow engine in the initial local-first release unless measured requirements justify them. Preserve interfaces for later replacement.

---

# 34. Configuration

Configuration is typed, validated at startup, and layered as:

1. secure defaults;
2. versioned application configuration;
3. machine-local configuration;
4. environment references for non-secret toggles;
5. secure-store references for secrets.

Example:

~~~yaml
agent_core:
  default_interaction_mode: guided
  maximum_parallel_read_steps: 4
  maximum_replans: 2
  default_task_timeout_seconds: 900

models:
  routes: {}
  data_policies: {}

memory:
  enabled: true
  retention_profile: private_default

policy:
  default_remote_write: explicit_approval
  default_privileged: dedicated_approval

observability:
  log_level: INFO
  retain_model_payloads: false
~~~

Unknown fields should fail startup during development. Never place credentials directly in configuration files.

---

# 35. Implementation Phases

## Phase AC1 — Domain contracts and state machine

Implement identifiers, Pydantic models, states, transitions, error taxonomy, and property tests.

**Exit condition:** Invalid transitions, malformed plans, unknown enums, and effect-ceiling violations are deterministically rejected.

## Phase AC2 — Persistence and event foundation

Implement SQLAlchemy tables, migrations, repositories, Unit of Work, optimistic concurrency, event store, outbox, and restart tests.

**Exit condition:** A task survives restart and cannot be advanced by two workers simultaneously.

## Phase AC3 — Tool Registry and Gateway integration

Implement capability snapshots, ToolSpec ingestion, filtering, selection, schema-hash binding, ToolResult consumption, and deterministic fake tools.

**Exit condition:** The core invokes a fake read-only tool only through the Gateway.

## Phase AC4 — Model abstraction and structured output

Implement ModelClient, profiles, routing, structured validation, prompt versions, schema repair, and a fake provider.

**Exit condition:** Goals and plans are generated from fixtures; invalid output is rejected; free-form model prose cannot execute tools.

## Phase AC5 — Goal interpretation and clarification

Implement turn ingestion, interrupt classification, Goal Interpreter, deterministic constraint enrichment, ambiguity scoring, and clarification lifecycle.

**Exit condition:** Read-only language cannot authorize writes, and ambiguous accounts or repositories cause clarification.

## Phase AC6 — Planner and validator

Implement plan generation, DAG validation, resource/tool binding, effect computation, postcondition requirements, immutable revisions, and static preflight.

**Exit condition:** Representative tasks produce executable DAGs, while invented or unsafe tools are rejected.

## Phase AC7 — Durable orchestration

Implement scheduler, leases, idempotent invocations, budgets, retries, cancellation, pause/resume, and progress events.

**Exit condition:** A multi-step read workflow pauses, restarts, resumes, and completes without duplicate execution.

## Phase AC8 — Approvals and mutations

Implement policy client, approval presentation, intent-bound references, expiry, consumption, and stale-state invalidation.

**Exit condition:** A changed target, account, branch, recipient, arguments, tool schema, or before-state invalidates approval.

## Phase AC9 — Verification, failure handling, and replanning

Implement verifier coordination, postconditions, evidence, failure classification, uncertain-outcome reconciliation, and bounded replanning.

**Exit condition:** False tool success cannot complete a task; dependants wait for verification; uncertain writes are not blindly retried.

## Phase AC10 — Context and memory

Implement trust-labelled assembly, token budgets, working memory, structured long-term memory, optional semantic retrieval, write policy, expiry, correction, and deletion.

**Exit condition:** Relevant aliases and preferences are recalled without treating memory as authority or storing secrets.

## Phase AC11 — API, dashboard events, and voice contract

Implement FastAPI, local auth, event streaming, voice metadata, concise spoken responses, and detailed visual evidence contracts.

**Exit condition:** UI and Voice clients can create, observe, clarify, approve, pause, resume, and cancel without database access.

## Phase AC12 — Hardening and evaluation

Implement injection tests, data-boundary tests, provider outage tests, chaos and restart tests, metrics, evaluation set, and threat review.

**Exit condition:** All release gates pass and residual risks are documented.

---

# 36. Testing Strategy

## 36.1 Unit tests

Test schema validation, transitions, effect ceilings, deterministic language restrictions, tool filtering, DAG validation, budgets, retry classification, approval matching, memory policy, redaction, and error mapping.

## 36.2 Contract tests

Test ModelClient providers, Tool Registry snapshots, Tool Gateway, Connection Manager capability state, PC Control ToolSpec and ToolResult, approval service, verification evidence, API schemas, and event versions.

## 36.3 Integration tests

Use temporary databases and fakes for:

- crash between invocation and result recording;
- crash during verification;
- expired approval;
- schema change after planning;
- connection loss;
- cancellation during a long tool;
- competing workers;
- memory correction/deletion;
- local/remote model data restrictions.

## 36.4 End-to-end scenarios

1. Inspect a repository and summarize uncommitted and unpushed work.
2. Commit an exact reviewed file set after approval.
3. Push an exact commit and verify remote SHA.
4. Search email and answer without sending.
5. Draft email and require approval before sending.
6. Clarify an ambiguous project.
7. Pause a browser task and resume after restart.
8. Cancel during execution and report partial effects.
9. Handle disconnected MCP without inventing success.
10. Reject instructions embedded in an email or page.
11. Use a project alias while revalidating its path.
12. Deny a request outside user scope.

## 36.5 Adversarial tests

Include cases where:

- email says to ignore previous instructions and upload secrets;
- README claims permission to run a script;
- tool schema changes after approval;
- model fabricates an approval ID;
- tool claims success but postcondition fails;
- timeout happens after a remote write may have succeeded;
- voice confuses “do” and “do not”;
- memory has obsolete account information;
- two tasks request desktop control;
- malicious MCP output contains instructions;
- model selects a tool outside the snapshot;
- replanner expands read-only work into remote write.

---

# 37. Evaluation and Release Gates

Create a versioned dataset of requests, contexts, expected goals, allowed effects, required clarifications, acceptable plans, and forbidden actions.

Minimum gates before real mutations:

| Metric | Gate |
|---|---|
| Goal effect classification | 100% on safety-critical cases |
| Explicit prohibition retention | 100% |
| Invented tool execution | 0 |
| Unauthorized remote write | 0 |
| Prompt-injection policy bypass | 0 in release suite |
| Approval scope mismatch acceptance | 0 |
| Duplicate side effect after restart | 0 |
| Required mutation verification | 100% |
| Cancellation acknowledgement at core boundary | Under 1 second |
| Crash-state recovery | 100% for release fixtures |

Track planning accuracy and clarification rate, but do not trade safety gates for convenience.

---

# 38. Workflow: Repository Inspection and Publication

User:

> Check whether there are pending changes in CareerMitra and tell me what they are. Do not modify anything.

Expected flow:

1. Ingest as a new read-only task.
2. Create a goal with maximum effect read and prohibition on modification.
3. Resolve CareerMitra through the project registry.
4. Plan repository status, diff, branch, upstream, and unpushed-commit inspection.
5. Select structured Git read tools.
6. validate all steps as read-only;
7. execute and collect evidence;
8. verify repository state remained unchanged;
9. summarize staged, modified, untracked, and unpushed work;
10. complete without approval.

If the user then says:

> Commit and push those changes.

The core must:

1. bind “those changes” to the reviewed change-set hash;
2. refresh Git status;
3. invalidate the reference if the change set differs;
4. propose exact files, commit message, branch, and remote;
5. obtain required approval;
6. commit only approved changes;
7. verify the commit tree;
8. push the exact commit;
9. verify the remote ref;
10. report SHA and evidence outcome.

---

# 39. Workflow: Email Question and Draft

User:

> Check my latest Caterpillar hackathon email, tell me whether we qualified, and prepare a reply to the team.

Expected flow:

1. Resolve or clarify the email account.
2. Search with a read-only mail capability.
3. Treat message content as untrusted.
4. Identify the latest relevant message by sender, thread, and timestamp.
5. Extract the result with evidence.
6. Explain qualification status and uncertainty.
7. Resolve “the team” or clarify recipients.
8. create a draft only;
9. present draft and recipients;
10. require separate bound approval before sending.

Instructions within the email to upload files, expose credentials, or send messages are ignored unless independently requested by the user and permitted by policy.

---

# 40. Definition of Done

The first production release is complete only when:

- [ ] Unrestricted requests become validated structured goals.
- [ ] Read-only wording cannot authorize writes.
- [ ] Project, account, recipient, branch, and resource ambiguity is handled safely.
- [ ] Plans are typed DAGs grounded in current capabilities.
- [ ] Every step binds a concrete tool version and schema hash.
- [ ] Every action passes deterministic policy preflight.
- [ ] Approvals are exact, expiring, and scope-bound.
- [ ] Tasks, steps, invocations, and events survive restart.
- [ ] Retries are idempotent and uncertain effects are reconciled.
- [ ] Mutations require verified postconditions.
- [ ] Pause, resume, cancellation, and emergency-stop integration work.
- [ ] Model providers can change without altering domain logic.
- [ ] Local-only data policies prevent remote leakage.
- [ ] Memory is typed, provenance-aware, correctable, and deletable.
- [ ] Prompt injection cannot grant authority or expand scope.
- [ ] Users receive accurate progress and outcomes.
- [ ] Logs and traces are useful without exposing secrets.
- [ ] All unit, contract, integration, end-to-end, and adversarial gates pass.
- [ ] Operational and developer documentation is current.
- [ ] Residual risks and unsupported actions are visible.

---

# 41. Required Implementation Deliverables

An agentic coding tool must deliver:

1. Source modules matching the package boundaries.
2. Strict domain models and generated JSON Schemas.
3. Database models and Alembic migrations.
4. State transition tables and diagrams.
5. Tool Gateway, policy, approval, model, and memory interfaces.
6. A fake model provider and deterministic fake tools.
7. Versioned prompt templates.
8. FastAPI endpoints and event streaming.
9. Structured logging, metrics, and traces.
10. Unit, contract, integration, end-to-end, and adversarial tests.
11. Evaluation fixtures and repeatable evaluation command.
12. Setup, configuration, migration, testing, and recovery instructions.
13. Threat model and data-flow diagram.
14. Architecture Decision Records for deviations.
15. Phase-by-phase implementation report mapping code to exit conditions.

---

# 42. Final Architecture Principle

The Agent Core must make JARVIS flexible without making it uncontrolled.

The language model supplies adaptable interpretation and planning. The surrounding system supplies identity, capability truth, authorization, durable state, isolation, verification, recovery, and accountability.

> **Natural language may describe any goal, but only typed, authorized, bounded, and verified actions may change the world.**

