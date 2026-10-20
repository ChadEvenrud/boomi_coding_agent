---
name: swinerton-error-handling
description: Swinerton enterprise error handling standard for Boomi. Use when building, modifying, or reviewing any Swinerton Boomi Producer, Consumer, EBS, or subprocess; when wiring a Try/Catch, catch path, error notification, audit record, HTTP response check, or email distribution list; or when answering how errors, alerts, audit rows (status S/E/W), or rerun/withdraw work. Covers the shared Generic Notification & Audit framework, its component IDs, required DPPs, and review rules.
---

# Swinerton Enterprise Error Handling

Every Swinerton Producer and Consumer sends failures down one shared path:

```text
Global Try/Catch (Catch path)
-> Map: Temp FF To Generic Notification & Audit XML [Insert audit E]
-> Process Route: Route | Error Notification & Audit  (key Notification&Audit)
-> Process Email Notification & Audit
     -> email Atom Queue  -> Listen Atom Queue [Email]          -> support inbox
     -> audit Atom Queue  -> Listen Atom Queue [<Iface> Audit]  -> audit DB
     -> error response document returned to web service callers
```

Integrations never build their own alerting, email, or audit logging. If a request asks for that, explain the standard and build the compliant version instead.

## Where error handling sits

```text
Producer -> EBS Router -> Atom Queue -> Consumer -> Target app
   |                                       |
   | BUSINESS FAULT                        | BUSINESS FAULT or REMOTE FAULT
   v                                       v
        Shared error framework (#UniversalShared)
   -> Support inbox    -> Integration audit DB -> Exception dashboard
                                                   (replays stored EBO into EBS)
```

- Producers and Consumers each own a global Try/Catch.
- The EBS Router and queues contain no error logic.
- Steps up to the route run inside the failing execution. Email and audit run later in separate queue-listener executions, so a mail or DB outage never blocks the integration.

## Shared components

Use these components by reference. Do not copy or fork them.

| Component | Type | Folder | ID |
| --- | --- | --- | --- |
| Route \| Error Notification & Audit | Process route | #UniversalShared/Generic Notification & Audit | `65a36f82-d68b-46e3-a59b-913764c55590` |
| Process Email Notification & Audit | Process | #UniversalShared/Generic Notification & Audit | `10368311-44c1-40e1-8e50-83eec1bdd709` |
| Generic Notification & Audit XML Prof | XML profile | #UniversalShared | `5674bbbb-3ff0-470f-a1cb-71d59d02db10` |
| CRT \| Email_Distribution_List | Cross-reference | #UniversalShared | `0ea5958b-64a1-4acb-9988-ca309abee3c6` |
| Route \| Push Error Messages to Email Queue | Process route (key `ErrorMessages`) | #UniversalShared/Notification | `04f29a07-024c-44de-aabc-c45ac7247d9f` |
| Sub: Push Error Messages to Email Queue | Process | #UniversalShared/Notification | `124750a2-d57a-4522-8a21-4c8455b62a74` |
| Listen Atom Queue [Email] | Listener | #UniversalShared/Notification | `033a5638-e8c5-4e8f-956b-0c1144da4b1a` |
| Route \| Send Audit Messages To Queue | Process route (key `AuditMessages`) | #UniversalShared/UTILS/Audit | `48a87939-309c-41f4-9ed7-bace52fd8042` |
| Sub : Audit Messages To Atom Queue | Process | #UniversalShared/UTILS/Audit | `b7c3bab6-70cc-48c1-81cd-9687bbb5716f` |
| Sub : Listen Atom Queue [Audit] | Process | #UniversalShared/UTILS/Audit | `56ed9675-d159-4e4e-9cd1-49939ffa138a` |
| Listen Atom Queue [Default Audit] | Listener | #UniversalShared/UTILS/Audit | `cadc2afc-aa34-4351-bcb6-05d01098ab96` |
| [UTIL] SUB_HTTPResponseCheck | Process (route key `HTTPResponseCheck`) | Integrations/Employee/#Common Components | `dc26829c-cca7-4364-83d8-339d15c49c09` |

Maps: `Temp FF To Generic Notification & Audit XML [Insert audit E]` (catch path) and `[Insert audit S]` (success path), in `active-development/transform.map/`.

## Building a Producer or Consumer

Apply every item. Treat a missing item as a defect.

1. **Global DPPs right after Start** (Consumers: right after the Atom Queue Listen):
   - `DPP_BoomiExecutionID`, `DPP_ProcessName`, `DPP_InterfaceName`, `DPP_Application`, `DPP_AtomName`, `DPP_Source`, `DPP_Target` (Consumers)
   - `DPP_ErrorType = BUSINESS FAULT`
   - `DPP_IsAttachment = No`
   - `DPP_ResponseType = xml`
   - `DPP_OriginalPayload` = the current inbound document
2. **Set later in the flow:**
   - `DPP_EntityID` as soon as the entity key is known.
   - `DPP_RequestPayload` / `DPP_ResponsePayload` around each external call.
   - `DPP_MailBody` when a custom mail body is needed.
3. **Global Try/Catch immediately after the DPP shape**, with Retry Count `0` and Failure Trigger `All Errors`.
4. **Catch path:** Map `[Insert audit E]`, then Process Route `Route | Error Notification & Audit` with key `Notification&Audit`.
5. **Success path:** Map `[Insert audit S]`, then the same route, so every run writes an audit row.
6. **After each HTTP connector:** route with key `HTTPResponseCheck`, or use the system-specific check (`SUB_HTTPResponseCheck_AutoDesk`, `[Util] | AutodeskHTTPErrorCodes`).
7. **API retries:** to use Boomi native retry, put a dedicated Try/Catch directly before the connector. Keep the global one at retry 0.
8. **CRT row:** add or confirm a `CRT | Email_Distribution_List` row for the `Application` + `InterfaceName`.
9. **Audit queue:** if the interface needs its own audit queue, add a route value in `Sub : Audit Messages To Atom Queue` and deploy a `Listen Atom Queue [<Interface> Audit]` listener. Otherwise traffic falls to the default audit queue.

## Subprocesses

A subprocess never calls the error framework itself. It must contain:

```text
Try/Catch -> (Catch) Exception shape    # rethrows to the caller
          -> (Try)   ... -> Return shape
```

The exception lands in the parent's global Try/Catch, which runs the enterprise path once. Do not overwrite the parent's DPPs inside a subprocess, except `DPP_ErrorType`, `DPP_ErrorCode`, `DPP_ErrorMsg`, `DPP_FailurePoint`, `DPP_RequestPayload` and `DPP_ResponsePayload` when describing the failure.

## Error classification

| `DPP_ErrorType` | Meaning | Who sets it | CRT list used |
| --- | --- | --- | --- |
| `BUSINESS FAULT` | Data or rule problem: validation, mapping, bad input | Default in every Producer and Consumer | `Business_Exception_Alert_DL` |
| `REMOTE FAULT` | External system failed: HTTP 4xx/5xx, connection, API error | HTTP response checks | `Exception_Alert_DL` |
| other / success | Successful run | Success-path map | `Success_Alert_DL` |

The map function `Fun | Email Address & Flag based On ErrorType` selects the distribution list and email flag.

`[UTIL] SUB_HTTPResponseCheck` reads the Application Status Code:

- `20*`: pass.
- `40*`: sets `REMOTE FAULT`, `DPP_ErrorCode`, `DPP_ErrorMsg`, `DPP_ResponsePayload` and `DPP_FailurePoint`, then throws "HTTP 4xx Client Exception".
- `50*`: same properties, then throws "HTTP 5xx Client Exception".
- Anything else: throws a `REMOTE FAULT` exception with code, message and body.

## Email distribution list

`CRT | Email_Distribution_List` has one row per `Application` + `InterfaceName`. Its columns are:

- `Success_Alert_DL`, `Exception_Alert_DL`, `Business_Exception_Alert_DL`: semicolon-separated addresses.
- `Success_Email_Flag`, `Exception_Email_Flag`, `Business_Exception_Email_Flag`: `Y` sends; a blank flag sends no email, but the audit row is still written.

Never hard-code recipients in a process or map. Change them in the CRT.

## Generic Notification & Audit XML

One document drives both email and audit.

- `Notification`:
  - Email fields: `subject`, `message`, `toAddress`, `fromAddress`, `IsAttachment`, `attachmentData`.
  - Run and error details: `executionId`, `processName`, `interface_name`, `source`, `target`, `error_code`, `error_txt`, `PointOfFailure`, `environmentName`.
  - Switches: `NotificationFlag` (gates email) and `WSS_error_response_type` (`json` or `xml` for web service responses).
- `Audit`:
  - Run and entity: `execution_id`, `parent_exec_id`, `process_name`, `interface_name`, `source_app`, `target_app`, `source_entity_id`, `target_entity_id`.
  - Outcome: `status`, `error_type`, `error_code`, `error_message`.
  - Payloads: `original_payload`, `request_payload`, `response_payload`.
  - Support: `action_type`, `assigned_group`.
  - Switch: `AuditFlag` (gates the audit write).
  - Plus five generic name-value pairs each for source, target and global attributes.

`Process Email Notification & Audit` branches the document three ways. Email goes out only if `NotificationFlag` is true, the audit row is written only if `AuditFlag` is true, and an error response goes back to web service callers according to `WSS_error_response_type`.

## Audit statuses

Audit rows are stored in `swin_integration_audit_tbl` / `boomi_integration_audit`.

| Status | Meaning |
| --- | --- |
| `S` | Success |
| `E` | Error |
| `W` | Waiting: an open error already exists for the entity, or the record is queued for rerun or withdrawn |

For entity-ordered interfaces, check for an existing `E` row for the entity before processing. If one exists, write the new record as `W` so updates are not applied out of order. `SyncCompToAutodesk` is the reference example.

## Retry behaviour

- Global Try/Catch: retry 0. Failures surface instead of retrying silently.
- Connector-level Try/Catch: Boomi native retry for API calls.
- `Listen Atom Queue [Email]`: retries mail send twice, then fails with "Failed to Send Error Notification".
- Atom Queues hold email and audit messages until their listeners succeed.

## Rerun and withdraw (operations)

| Process | Folder | Role |
| --- | --- | --- |
| Query Audit [swin_integration_audit_tbl] | Flow/Exception Handling/QueryAudit | Search audit rows; JSON or export file |
| Flow Exception Reprocess | Flow/Exception Handling/Rerun & Withdraw | `ReProcess`, `ReRun`, `Withdraw`, `ReAssign`, `Save`; updates audit status |
| Listen Exception Dashboard [Rerun & Withdraw] | Flow/Exception Handling/ReSync | Replays the stored EBO into the EBS for the interface (EMPLOYEE, VENDOR, WORKORDER, TIMECARD, JOBSTART, JOB, COA, BUSPARTNER, QUANTITIES, BUDGET, INVOICE, VENDORCHECK, and others) |

Reruns depend on `DPP_OriginalPayload` being captured. A process that skips it cannot be replayed. New interfaces that need rerun must also get a route value in `Listen Exception Dashboard [Rerun & Withdraw]`.

## Known variations

- **Business Partners:** `Route | BusPartner Common Error Handling` (key `Error`) leads to `Process BusPartner Common Error Handler` (`a9bb6248-d89a-4dc3-8c41-65b5de8533d3`). Same pattern: an email queue and audit status `E`.
- **AutoDesk company sync:** the catch path calls `SUB:ErrorNotificationAudit` (`a12b8836-957a-49e2-982b-6d3ad7f17775`).
- **Timberlab hsbCAD:** `[Sub]: Audit & Notification` (`570c1661-2b0d-47f7-ab08-ab5e05fac309`) wraps the route.

Follow an existing variation only when you are extending that interface. New work uses the standard route.

## Review checklist

When reviewing a process, flag each of these:

- [ ] Global DPPs are missing, or set after the Try/Catch.
- [ ] The global Try/Catch has retry > 0, or is not set to All Errors.
- [ ] The catch path does not reach `Route | Error Notification & Audit`, or uses custom Mail/DB shapes instead.
- [ ] The success path writes no audit row.
- [ ] A subprocess calls the error route or sends email directly, or lacks a Try/Catch → Exception.
- [ ] An HTTP call has no response check, so a non-2xx response passes as success.
- [ ] `DPP_OriginalPayload` or `DPP_EntityID` is not captured.
- [ ] Recipients are hard-coded, or no CRT row exists for the `Application` + `InterfaceName`.
- [ ] Error logic is in the EBS Router.

## Anti-patterns

- Sending email with a Mail connector inside an integration process.
- Writing directly to the audit DB from a Producer or Consumer instead of using the audit queue.
- Swallowing errors with a Stop shape on the catch path.
- Running the full enterprise error path inside a subprocess.
- Copying the shared components into an interface folder.

## Source

This skill is condensed from the "Enterprise Error Handling Architecture" doc (https://claude.ai/code/artifact/6c834075-6714-46a8-8652-4c6aa4225014) and `swinerton_best_practices.md`. Component details come from exports in `active-development/`. Design-time versions can be ahead of Production, so confirm against the deployed version before relying on a specific shape.
