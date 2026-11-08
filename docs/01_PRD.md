# JARVIS — Product Requirements Document (PRD)

**Version:** 0.1 | **Owner:** Rishabh Kumar P | **Status:** Draft

## 1. Vision
A personal, voice-first agent that operates my computer and my connected services the way a capable human assistant would. I state an *intent* in natural speech; the system works out *how* to do it. There is no command list, no keyword routing, no per-action code path. Adding a new capability means connecting a tool, not writing new logic.

## 2. Problem
Existing assistants (and most hobby "JARVIS" builds, including the reference repo) map speech to a fixed set of hand-coded functions (`open_app`, `play_youtube`, `send_message`). They break the moment I phrase something differently or ask for something nobody pre-wrote. Meanwhile my real work is spread over Gmail, Drive, GitHub, VS Code/Antigravity, the browser and the file system, and I context-switch constantly between them.

## 3. Findings from reference analysis
**Caveat:** GitHub blocked automated access to the repo you linked, so I could only see its README-level description (the sibling Mark-L/Mark-XXX line), not the source. Treat these as README-level observations, to be confirmed by reading the code locally.
- Strengths worth borrowing: real-time voice via Gemini live audio, session summaries ("remembers yesterday"), opt-in background monitoring, screen/camera awareness, proactive check-ins, cross-platform Python.
- Limitation relative to your goal: the design is a curated set of built-in tools/actions. Capability is bounded by what the author coded. Your requirement inverts this: **capability should be bounded by connected tools plus a general computer-control layer**, with the LLM planning over them.

## 4. Target user and environment
Single user (me). Windows 11 laptop primarily; macOS/Linux a later consideration. Developer workflow: Git, VS Code, Antigravity, terminal, browser, Google Workspace.

## 5. Goals
| ID | Goal |
|----|------|
| G1 | Any spoken instruction in free-form language is understood and executed or answered; no fixed vocabulary |
| G2 | Tools are pluggable: any MCP server can be added by config and is usable immediately |
| G3 | General computer control: files, shell, apps, windows, browser, and (fallback) screen-level UI control |
| G4 | Multi-step tasks: the agent plans, acts, observes results and adapts |
| G5 | Safe by design: risky actions need spoken confirmation; everything is logged and reversible where possible |
| G6 | Conversational latency: first spoken response under ~1.5 s for simple turns; progress narrated for long tasks |
| G7 | Memory: remembers projects, preferences, folders and yesterday's context |

## 6. Non-goals (v1)
Multi-user support, mobile app, cloud hosting, wake-word accuracy for noisy rooms, smart-home control, autonomous actions without being asked (background monitoring is opt-in only).

## 7. Representative scenarios (acceptance-driving, not a command set)
1. **Git status (your example):** "Do I have any uncommitted or unpushed changes in the portfolio project?" → locates the project, inspects repo state (opens it in VS Code/Antigravity if asked or useful), summarizes the diff in plain speech. "Commit and push with a good message" → drafts message, **confirms**, commits, pushes, reports.
2. **Mail Q&A:** "Did the professor reply about the review meeting? What time did he say?" → searches Gmail, reads thread, answers; no mail is sent without confirmation.
3. **Drive:** "Find last semester's DS report and summarize the conclusions."
4. **Cross-tool:** "Take the action items from today's emails and add them as GitHub issues in repo X."
5. **Unseen request:** "Free up space by finding the largest files in Downloads older than 6 months and list them." Never pre-coded; solved via shell/file tools.
6. **UI fallback:** "Turn on dark mode in this app" where no API exists → screenshot-driven UI control.
7. **Conversation:** follow-ups ("and who else was on that thread?"), interruptions ("stop"), clarifying questions only when truly ambiguous.

## 8. Functional requirements
- **FR1 Voice I/O:** push-to-talk and optional wake word; streaming speech recognition; streamed spoken replies; barge-in (I can interrupt).
- **FR2 Intent handling:** one LLM agent loop decides everything; no hardcoded intent→action table.
- **FR3 Tool connectivity:** MCP client supporting stdio and HTTP servers; add/remove via a config file; OAuth handled once per service.
- **FR4 Computer control:** shell execution, file read/write/search, launch/focus apps, clipboard, browser automation, screen-reading and mouse/keyboard control as last resort.
- **FR5 Planning:** multi-step execution with observation after each step; ability to retry or change approach on failure; progress narration.
- **FR6 Project awareness:** resolves "the portfolio project", "that repo" to folders via a registry and fuzzy search; learns aliases.
- **FR7 Safety layer:** action risk tiers (read / reversible write / destructive-or-external); spoken confirmation for the top tier; spend/step limits; kill switch ("stop everything", hotkey).
- **FR8 Memory:** facts, aliases, preferences and session summaries stored locally and retrievable.
- **FR9 Transparency:** a minimal UI shows live transcript, current plan/step, tool calls, and a log I can review.
- **FR10 Untrusted-content handling:** text from emails, web pages and files is treated as data, never as instructions.

## 9. Non-functional requirements
- **Latency:** simple Q&A < 1.5 s to first audio; tool calls stream partial progress.
- **Reliability:** a failing tool never crashes the session; every tool call has a timeout.
- **Privacy:** credentials in the OS keyring; local logs and memory; clear statement of which content goes to the model provider.
- **Cost:** configurable model per role (fast voice model vs stronger planner); per-session budget cap.
- **Extensibility:** new tool = config entry; new model provider = adapter.

## 10. Risks
| Risk | Mitigation |
|------|-----------|
| Agent takes a harmful action from a misheard command | Confirmation tier, transcript echo for risky actions, dry-run previews |
| Prompt injection via email/web content | Content isolation, no tool escalation from untrusted text, confirmation on cross-tool side effects |
| Too many tools degrade model accuracy | Dynamic tool retrieval (TRD §6) |
| Screen-control flakiness | Prefer APIs/MCP/shell; UI control only as fallback, with verification screenshots |
| Voice latency with a heavy planner | Split fast voice front-end from slower planner; narrate while working |

## 11. Success metrics
≥90% of 50 diverse test utterances completed correctly without code changes; zero unconfirmed destructive actions in testing; median simple-turn latency < 1.5 s; a new MCP server usable in < 5 minutes of config.

## 12. Milestones
M1 voice loop + shell/files → M2 MCP client + GitHub/Gmail/Drive → M3 safety + memory + UI → M4 computer-use fallback + proactive features → M5 hardening. Details in the Implementation Doc.
