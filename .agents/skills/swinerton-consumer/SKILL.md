---
name: swinerton-consumer
description: Builds and reviews Swinerton Boomi Consumer processes (ProvABCS / target-side processes) that listen on a Boomi Atom Queue, take an Enterprise Business Object (EBO) from the EBS Router, transform it to the target system's format, and call the target connector, API or database. Use when creating, cloning from the Consumer template, modifying, or reviewing any Swinerton Consumer or "Listen ..." queue process; when choosing a Consumer's queue listener, global DPPs, Try/Catch, EBO-to-target map, target call, response handling, tracking, concurrency, naming, folder, or description. Works with the swinerton-error-handling skill for the catch path.
---

# Swinerton Consumer Processes

A Consumer is the target-side half of every Swinerton integration:

```text
Producer -> EBO -> EBS Router -> Boomi Atom Queue -> Consumer -> Target application
```

The Consumer does four things:

1. Listens on its own point-to-point Atom Queue.
2. Reads the EBO.
3. Transforms the EBO into the target system's format, applying target-side business rules.
4. Calls the target connector, API or database and checks the response.

It never calls a Producer or another Consumer. It never changes the canonical EBO structure, and it never re-routes to other targets (that is the EBS Router's job).

If a request asks for a non-compliant pattern, answer:

```text
That pattern does not follow Swinerton Boomi standards because <reason>.
The compliant approach is <recommended design>.
```

Then build the compliant version.

For the catch path, DPP meanings, error types, HTTP checks and audit rules, also load the **swinerton-error-handling** skill. This skill covers the Consumer-specific parts and references that one rather than repeating it.

## Starting point: the Consumer template

Clone the template. Do not build from a blank canvas.

| Item | Value |
| --- | --- |
| Template process | `Consumer_<Target_System>_<BusinessObject>` |
| Component ID | `df64e027-5fc4-4c68-8f81-b821fc446809` (v5) |
| Boomi folder | Swinerton Incorporated/Integrations/Timberlab/Templates |
| Local export | `process_template/process/Consumer_Target_System_BusinessObject.xml` |
| Sibling templates | `Producer_<Source_System>_<BusinessObject>` (`3f82bd52-5988-4eb7-8a57-a4034d0d3802`), `Router_<BusinessObject>` (`7bcccdc6-6bf2-48ae-9db3-a5b306e71b4c`) |

### What the template gives you

```text
Start (Atom Queue connector placeholder)
-> Set | Global Props                          (Set Properties)
-> Global Try/Catch                            (retry 0, catch all)
   Try:   Set | Process Props (empty) -> Branch (4 unconnected paths)   <- you replace this
   Catch: Branch
          1 -> Set | MailBody (Message) -> Set | Mail Props (DPP_MailBody) -> Stop
          2 -> Map | Temp FF - Generic Notification & Audit XML [Insert audit E]
            -> Process Route | Error Notification & Audit (key Notification&Audit)
                 Return | WS Error Resp -> Return Documents
                 Default                -> Stop
```

Process options in the template: Allow Simultaneous = false, Stop Processing If Zero Documents = true, Update Run Dates = true. Keep them unless there is a documented reason to change them.

Components the template references:

| Component | ID |
| --- | --- |
| `Route \| Error Notification & Audit` | `65a36f82-d68b-46e3-a59b-913764c55590` |
| Map `Temp FF To Generic Notification & Audit XML [Insert audit E]` | `26d00fe1-a96c-407f-ad56-ce7f95102ded` |
| `[UTIL] Temp FF` flat file profile | `01b4c2a9-c74f-4bef-a6d4-17571f6d9ebc` |
| `Common Props` (Boomi Base Url, used in the mail body) | `f9aef53f-63f2-487a-8bef-1b1ef30c27b0` |

### Fix these template gaps every time you clone it

1. **Queue listener not configured.** The start shape is an Atom Queue connector with an empty action, no connection and no operation. Set the action to **Listen** and pick the interface's queue connection and `Listen_<Interface>_<Application>` operation. Put the tracking field `SWIN_ENTITY_ID` on the operation.
2. **`DPP_Source` is a static placeholder** (`<ProducerSystem>`). The standard says to take it from the EBO, `TransmissionHeader/SourceApplication`. Set it from the profile element, not a typed value, so a Consumer fed by several Producers reports the right source.
3. **`DPP_Target` is missing.** Add `DPP_Target` = the target application, normally the same value as `DPP_Application`.
4. **`DPP_EntityID` is missing.** Set it from `BusinessObject/EntityID` in the EBO, right after the listener.
5. **Try path placeholder.** `Set | Process Props` is empty and the 4-way Branch has no shapes attached. Replace both with the real flow below. Use a Branch only when the paths are truly independent; delete unused branch paths.
6. **Mail body placeholders are shifted by one** (same bug as the Producer template). The parameters are, in order: `{0}` Boomi Base Url, `{1}` `DPP_BoomiExecutionID`, `{2}` `DPP_ErrorCode`, `{3}` `DPP_ErrorType`, `{4}` Try/Catch message, `{5}` current date. Correct the HTML to `href="{0}{1}"`, Error Code `{2}`, Error Type `{3}`, Error Message `{4}`, Date Time `{5}`.
7. **Labels.** Rename `Set | Mai lBody` to `Set | MailBody`.
8. **Map location.** The `[Insert audit E]` map lives in `Integrations/1) Job/Ramco - Deprecated`. Reference it; do not copy it into the interface folder.

## Required Consumer flow

```text
Start: Atom Queue connector, action Listen      (Listen_<Interface>_<Application>, tracking SWIN_ENTITY_ID)
-> Set | Global Props
-> Global Try/Catch (Retry Count 0, Failure Trigger: All Errors)
   Try:
   -> Set | Entity Props            (DPP_EntityID, DPP_Source from the EBO header)
   -> [optional] Check open errors  (existing E row for this entity -> audit W, stop)
   -> Business rules / lookups      (subprocesses)
   -> Map | <BusinessObject> EBO to <Target> <Object>
   -> Set | Request Payload         (DPP_RequestPayload)
   -> Target connector / API / DB   (tracking set; optional connector-level Try/Catch for retry)
   -> Set | Response Payload        (DPP_ResponsePayload)
   -> HTTP / response check         (non-success -> REMOTE FAULT thrown)
   -> Map [Insert audit S] -> Route | Error Notification & Audit   (success audit)
   Catch:
   -> enterprise error path (template catch path, unchanged)
```

Rules:

- The start shape must be the Atom Queue **Listen**. A Consumer never starts with No Data, a schedule plus query, or a Process Call.
- The Global Try/Catch goes immediately after `Set | Global Props`.
- Transform from the EBO only. Do not call back to the source system for data the EBO should carry.
  - **Large-data exception:** when the EBO carries only metadata and parameters, the Consumer retrieves the payload using them. Do that in a subprocess.
- Do not change the canonical EBO. Map from it to a separate target profile.
- Keep the canvas readable. Put API calls, lookups, validation and response parsing in subprocesses.
- For each external call:
  - Capture the request and response in DPPs.
  - Run the response check: the `HTTPResponseCheck` route key, or a system-specific check such as `SUB_HTTPResponseCheck_AutoDesk`.
  - For Boomi native retry, add a dedicated Try/Catch directly before that connector. The global one stays at retry 0.
- **Entity ordering:** if updates for one entity must apply in order, check `swin_integration_audit_tbl` for an existing `E` row for `DPP_EntityID` first. If one exists, write the record with status `W` instead of processing it (see swinerton-error-handling).
- **Success audit:** if the interface audits success, map `[Insert audit S]` and call `Route | Error Notification & Audit` at the end of the Try path, so the dashboard shows an `S` row.

## Queue listener

| Setting | Standard |
| --- | --- |
| Queue type | Point-to-point, one queue per consuming application |
| Queue name | `Queue_<InterfaceName>_<ConsumingApplicationName>`, for example `Queue_Job_CMiC` |
| Listen operation | `Listen_<InterfaceName>_<ApplicationName>`, for example `Listen_Job_CMiC` |
| Matching send operation (in the EBS) | `Send_<InterfaceName>_<ApplicationName>` |
| Tracking field | `SWIN_ENTITY_ID`, the same field the Producer uses |
| Batch size | 0 or 1 unless a larger value is documented |
| Concurrent executions | 1 by default; raise only when volume and processing time justify it and the target tolerates parallel writes |
| Connection | The shared queue connection; values via environment extensions |

## Global DPPs (`Set | Global Props`)

| DPP | Value in a Consumer | Source type |
| --- | --- | --- |
| `DPP_BoomiExecutionID` | Execution Id | Execution property |
| `DPP_ProcessName` | Process Name | Execution property |
| `DPP_AtomName` | Atom Name | Execution property |
| `DPP_Application` | Target (consuming) application, for example `CMiC` or `AUTODESK`; must match the CRT row | Static |
| `DPP_InterfaceName` | Interface key, for example `JOB`, `EMPLOYEE` or `BUSPARTNER` | Static |
| `DPP_Source` | Producer application from `TransmissionHeader/SourceApplication` | Profile element |
| `DPP_Target` | Target application | Static |
| `DPP_ErrorType` | `BUSINESS FAULT` | Static |
| `DPP_IsAttachment` | `No` | Static |
| `DPP_ResponseType` | `xml` | Static |
| `DPP_OriginalPayload` | The EBO as received from the queue | Current data |

Set later, inside Try:

| DPP | When |
| --- | --- |
| `DPP_EntityID` | Immediately, from `BusinessObject/EntityID` |
| `DPP_RequestPayload` | Before each target call (the mapped target request) |
| `DPP_ResponsePayload` | After each target call |
| `DPP_ErrorCode`, `DPP_ErrorMsg`, `DPP_FailurePoint` | Set by response checks or validation before throwing |
| `DPP_ErrorType = REMOTE FAULT` | When the target system rejects or fails the call |

Because `DPP_OriginalPayload` holds the full EBO, the Exception Dashboard can replay the record through the EBS without the Producer running again. Never set it after a transform.

## Subprocesses called by a Consumer

- Name each one `<DescriptiveName>(<DataObjectOrParameter>)`, for example `Send Job(CMiC Payload)` or `Get CMiC Vendor(DPP_EntityID)`.
- Each one must contain: Try/Catch → (Catch) Exception shape, and (Try) … → Return shape.
- Never call the enterprise error route from a subprocess. The Exception shape rethrows to the Consumer's global catch.
- Do not overwrite the Consumer's global DPPs, except the error-detail and request/response DPPs.
- Use a Cache shape for large lookup results shared with subprocesses. Use Set Properties for small values. Clear the cache before re-caching transformed data.

## Naming and location

| Item | Convention | Example |
| --- | --- | --- |
| Process | `Consumer_<Target_System>_<BusinessObject>` | `Consumer_CMiC_Job` |
| Legacy names (existing interfaces only) | `Listen <Object> [<Target>]`, `Sync<Object><Target>ProvABCS` | `Listen Job [Workmax]`, `SyncJobCMiCProvABCS` |
| Folder | `Integrations/<Interface>/<TargetApplication>/03_Main_Process` | `Integrations/Job/CMiC/03_Main_Process` |
| Subprocesses | `.../<TargetApplication>/02_Subprocess` | |
| Utilities | `.../<TargetApplication>/01_Utility` | |
| Test harness | `.../<TargetApplication>/04_Unit_Testing` | |
| Shapes | `<Type> \| <What>` | `Set \| Global Props`, `Map \| Job EBO to CMiC Job`, `Check \| Open Errors` |

Connectors: use one shared connection per application from `#UniversalShared`. Do not save credentials in the shape; values come from environment extensions and Runtime Management. Do not create a second connection for an application that already has one.

## Description and notes

The process description must state:

- The queue listened to
- The EBO consumed
- The target application
- The transformations performed
- The business rules applied
- The target connector, API or database operation

Add a component note on every Decision, Data Process, business-logic shape, complex map, connector change and bug fix:

```text
Title: <Developer Name>
Body:  <ChangeNumber> | <YYYY-MM-DD> | <short reason>
```

## Testing

- Unit test each subprocess on its own, with a harness in `04_Unit_Testing` that feeds a sample EBO.
- Run end to end: Producer → EBS → queue → Consumer → target.
- Check the `SWIN_ENTITY_ID` tracking value on the queue listener and target connector in Atom Management.
- Happy path: the target record is created or updated, and an audit `S` row is written if the interface audits success.
- Business fault (bad EBO data): audit `E` with `BUSINESS FAULT`, and an email to `Business_Exception_Alert_DL`.
- Remote fault (target down or returning 4xx/5xx): audit `E` with `REMOTE FAULT`, a request and response captured, and an email to `Exception_Alert_DL`.
- A second message for an entity with an open error is held as `W` (when ordering applies).
- An Exception Dashboard replay succeeds once the cause is fixed.
- The mail body link opens the correct Boomi execution.

## Validation checklist

Run this before declaring a Consumer done, and include it in any design answer.

- [ ] Name, folder and description follow the standard
- [ ] Start shape is an Atom Queue **Listen** on `Listen_<Interface>_<Application>`
- [ ] Queue is point-to-point and named `Queue_<Interface>_<Application>`; batch 0/1; concurrency justified
- [ ] `SWIN_ENTITY_ID` tracking on the listener and every connector
- [ ] `Set | Global Props` sets every global DPP, including `DPP_Target`; `DPP_Source` comes from the EBO header
- [ ] Global Try/Catch directly follows the DPP shape: retry 0, All Errors
- [ ] `DPP_EntityID` set from the EBO; request and response payloads captured around target calls
- [ ] Target responses checked; failures thrown as `REMOTE FAULT`
- [ ] EBO transformed to a target profile, and the EBO itself is not modified
- [ ] Complex logic is in compliant subprocesses (Try/Catch, Exception, Return)
- [ ] Open-error (`W`) check present when entity order matters
- [ ] Success audit wired when the interface audits success
- [ ] Template placeholders removed (empty Set Properties, unconnected Branch)
- [ ] Catch path unchanged from the template; mail body placeholders corrected
- [ ] CRT row exists for `DPP_Application` + `DPP_InterfaceName`
- [ ] No hard-coded credentials; environment extensions used
- [ ] Component notes added with change number and date

## When information is missing

Ask for these before building:

- Interface name and EBO
- Target application and operation (API, DB, file)
- Queue name, if it already exists
- Business rules and lookups
- Expected volume and whether concurrency is needed
- Whether entity order matters (`W` handling)
- Whether success should be audited or emailed
- Tracking ID
