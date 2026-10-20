---
name: swinerton-producer
description: Builds and reviews Swinerton Boomi Producer processes (ReqABCS / source-side processes) that extract source data, map it to an Enterprise Business Object (EBO), and route it to the EBS Router. Use when creating, cloning from the Producer template, modifying, or reviewing any Swinerton Producer; when choosing a Producer's start shape, global DPPs, Try/Catch, EBO map, EBS route, tracking field, naming, folder, or description; or when asked "how should this Producer be built". Works with the swinerton-error-handling skill for the catch path.
---

# Swinerton Producer Processes

A Producer is the source-side half of every Swinerton integration:

```text
Producer -> EBO -> EBS Router -> Boomi Atom Queue -> Consumer
```

The Producer does exactly four things:

1. Gets the source data.
2. Applies any source-side business logic.
3. Maps the data to the canonical EBO.
4. Hands the EBO to the EBS Router with a Process Route shape.

It never calls a Consumer, never sends to a queue directly, and never writes to a target system.

If a request asks for a non-compliant pattern, answer:

```text
That pattern does not follow Swinerton Boomi standards because <reason>.
The compliant approach is <recommended design>.
```

Then build the compliant version.

For the catch path, DPP meanings, error types and audit rules, also load the **swinerton-error-handling** skill. This skill covers the Producer-specific parts and references that one rather than repeating it.

## Starting point: the Producer template

Clone the template. Do not build from a blank canvas.

| Item | Value |
| --- | --- |
| Template process | `Producer_<Source_System>_<BusinessObject>` |
| Component ID | `3f82bd52-5988-4eb7-8a57-a4034d0d3802` (v14) |
| Boomi folder | Swinerton Incorporated/Integrations/Timberlab/Templates |
| Local export | `process_template/process/Producer_Source_System_BusinessObject.xml` |
| Sibling templates | `Router_<BusinessObject>` (`7bcccdc6-6bf2-48ae-9db3-a5b306e71b4c`), `Consumer_<Target_System>_<BusinessObject>` (`df64e027-5fc4-4c68-8f81-b821fc446809`) |
| Import script | `process_template/import_templates.py` |

### What the template gives you

```text
Start
-> Set | Global Props                         (Set Properties)
-> Global Try/Catch                           (retry 0, catch all)
   Try:   <source connector> -> <logic> -> ...   <- you replace this
   Catch: Branch
          1 -> Set | MailBody (Message) -> Set | Mail Props (DPP_MailBody) -> Stop
          2 -> Map | Temp FF - Generic Notification & Audit XML [Insert audit E]
            -> Process Route | Error Notification & Audit (key Notification&Audit)
                 Return | WS Error Resp -> Return Documents
                 Default                -> Stop
```

Process options in the template: Allow Simultaneous = false, Stop Processing If Zero Documents = true. Keep these unless there is a documented reason to change them.

Components the template references:

| Component | ID |
| --- | --- |
| `Route \| Error Notification & Audit` | `65a36f82-d68b-46e3-a59b-913764c55590` |
| Map `Temp FF To Generic Notification & Audit XML [Insert audit E]` | `26d00fe1-a96c-407f-ad56-ce7f95102ded` |
| `[UTIL] Temp FF` flat file profile | `01b4c2a9-c74f-4bef-a6d4-17571f6d9ebc` |
| `Common Props` (Boomi Base Url, used in the mail body) | `f9aef53f-63f2-487a-8bef-1b1ef30c27b0` |

### Fix these template gaps every time you clone it

The template is a working skeleton from a Timberlab simulation, and it does not yet meet every standard:

1. **Start shape.** The template uses a "No Data" start (`<connectoraction/>`, labelled `None`). The standard requires **Data Pass Through**. Change it, and move the source connector into the Try path. A listener-driven or scheduled Producer whose data must come from a connector is the only exception: document the reason in the process description.
2. **Try path placeholder.** The template's Try path is `GET STMCC Pack Info Data` (MySQL STMCC) → a Groovy simulation script using `java.util.Random` → an empty, unconnected Message shape. Delete all three. They are test scaffolding, not a pattern.
3. **No EBO map or EBS route.** The template stops before the two required steps. Add `Map | <Source> to <BusinessObject> EBO` and `Process Route | <BusinessObject> EBS`.
4. **`DPP_Application`** is set to the placeholder `<TargetSystem>`. In a Producer, set it to the **source** application, the value used in `CRT | Email_Distribution_List`.
5. **Missing DPPs.** `DPP_Source` and `DPP_EntityID` are not set. Add them (see the DPP table).
6. **Mail body placeholders are shifted by one.** The message parameters are, in order: `{0}` Boomi Base Url, `{1}` `DPP_BoomiExecutionID`, `{2}` `DPP_ErrorCode`, `{3}` `DPP_ErrorType`, `{4}` Try/Catch message, `{5}` current date. The template HTML uses `{1}{2}` for the link and `{3}`–`{6}` for the cells. Correct it to `href="{0}{1}"`, Error Code `{2}`, Error Type `{3}`, Error Message `{4}`, Date Time `{5}`.
7. **Labels.** Rename `Set | Mai lBody` to `Set | MailBody`.
8. **Map location.** The `[Insert audit E]` map lives in `Integrations/1) Job/Ramco - Deprecated`. Keep referencing it until a copy exists in `#UniversalShared`, but do not copy it into the interface folder.

## Required Producer flow

```text
Start (Data Pass Through)
-> Set | Global Props
-> Global Try/Catch (Retry Count 0, Failure Trigger: All Errors)
   Try:
   -> Get source data            (connector or subprocess, tracking field set)
   -> Set | Entity Props         (DPP_EntityID, request/response payloads)
   -> Business logic             (subprocesses, not inline spaghetti)
   -> Map | <Source> to <BusinessObject> EBO
   -> Process Route | <BusinessObject> EBS
   -> (success) Map [Insert audit S] -> Route | Error Notification & Audit   [when the interface audits success]
   Catch:
   -> enterprise error path (template catch path, unchanged)
```

Rules:

- The Global Try/Catch goes immediately after `Set | Global Props`. Nothing sits between them.
- The Producer sends to the EBS with a **Process Route** shape. Never use a Process Call to a Consumer, a direct queue send, or a Route shape as a queue substitute.
- Keep the main canvas readable. Put API calls, extraction, validation, EBO building and payload formatting in subprocesses.
- For an external API call, add a dedicated Try/Catch directly before that connector if you want Boomi native retry. The global one stays at retry 0.
- After each HTTP call, check the response (`Route | Error Notification & Audit` key `HTTPResponseCheck`, or the system-specific check) so a non-2xx response becomes a `REMOTE FAULT`.

## Global DPPs (`Set | Global Props`)

| DPP | Value in a Producer | Source type |
| --- | --- | --- |
| `DPP_BoomiExecutionID` | Execution Id | Execution property |
| `DPP_ProcessName` | Process Name | Execution property |
| `DPP_AtomName` | Atom Name | Execution property |
| `DPP_Application` | Source application, for example `WORKDAY` or `CMiC` | Static |
| `DPP_InterfaceName` | Interface, for example `EMPLOYEE` or `JOB` (must match the CRT and audit queue routing) | Static |
| `DPP_Source` | Source application | Static |
| `DPP_ErrorType` | `BUSINESS FAULT` | Static |
| `DPP_IsAttachment` | `No` | Static |
| `DPP_ResponseType` | `xml` | Static |
| `DPP_OriginalPayload` | Current document | Current data |

Set later, inside Try:

| DPP | When |
| --- | --- |
| `DPP_EntityID` | As soon as the business key is known; before the connector if possible, otherwise from the connector response |
| `DPP_RequestPayload` / `DPP_ResponsePayload` | Around each external call |
| `DPP_ErrorCode`, `DPP_ErrorMsg`, `DPP_FailurePoint` | Set by HTTP checks or validation before throwing |

`DPP_InterfaceName` values must be the uppercase interface keys used by the audit and rerun routers: `EMPLOYEE`, `VENDOR`, `JOB`, `JOBSTART`, `COA`, `BUSPARTNER`, `BUSUNIT`, `TIMECARD`, `QUANTITIES`, `INVOICE`, and so on. A new key needs a CRT row, and an audit route if the interface has its own audit queue.

## EBO

The Producer's main map creates the EBO. Header fields drive routing; the Business Object is the canonical payload.

```xml
<EnterpriseBusinessObject>
  <TransmissionHeader>
    <TransmissionID/>        <!-- DPP_BoomiExecutionID -->
    <CreationDateTime/>      <!-- current date/time -->
    <SourceApplication/>     <!-- DPP_Source -->
    <TargetApplication/>     <!-- target(s) when known; routing hint -->
    <TransactionCode/>       <!-- e.g. CREATE / UPDATE; used by EBS decisions -->
  </TransmissionHeader>
  <BusinessObject>
    <EntityID/>              <!-- DPP_EntityID / SWIN_ENTITY_ID value -->
    <EntityData/>            <!-- canonical business fields -->
  </BusinessObject>
</EnterpriseBusinessObject>
```

- Map to the shared EBO profile for the business object. Do not invent a per-Producer structure.
- Put only canonical data in `BusinessObject`. Keep source-system quirks out.
- Fill every header field the EBS Router decides on.
- **Large data:** send metadata and parameters in the EBO, not the dataset. The Consumer fetches the payload itself.

## Tracking

- Tracking field: `SWIN_ENTITY_ID`. Use the same field as the Consumer.
- Set tracking on every connector in the Producer.
- Use a business identifier (Job Code, Employee Number, Vendor Number, Invoice Number, Production Order, Material Document, Batch Number), not a random technical ID.
- Do not add extra tracking fields.

## Subprocesses called by a Producer

- Name each one `<DescriptiveName>(<DataObjectOrParameter>)`, for example `Get CMiC Data(DPP_CompanyCode)` or `Validate Employee(Employee EBO)`.
- Each one must contain: Try/Catch → (Catch) Exception shape, and (Try) … → Return shape.
- Never call the enterprise error route from a subprocess. The Exception shape rethrows to the Producer's global catch.
- Do not overwrite the Producer's global DPPs, except the error-detail DPPs listed above.
- Use a Cache shape for large documents shared with a subprocess. Use Set Properties for small values. Clear the cache before re-caching transformed data.

## Naming and location

| Item | Convention | Example |
| --- | --- | --- |
| Process | `Producer_<Source_System>_<BusinessObject>` | `Producer_Workday_Employee` |
| Legacy name (existing interfaces only) | `Process<Object><Source>ReqABCS` | `ProcessEmployeeWDReqABCS` |
| Folder | `Integrations/<Interface>/<SourceApplication>/03_Main_Process` | `Integrations/Employee/Workday/03_Main_Process` |
| Subprocesses | `.../<SourceApplication>/02_Subprocess` | |
| Utilities | `.../<SourceApplication>/01_Utility` | |
| Test harness | `.../<SourceApplication>/04_Unit_Testing` | |
| Shapes | `<Type> \| <What>` | `Set \| Global Props`, `Map \| Workday to Employee EBO`, `Process Route \| Employee EBS` |

Connectors: use the one shared connection per application from `#UniversalShared`. Do not save credentials in the shape. Values come from environment extensions.

## Description and notes

The process description must state:

- Source application
- Data extracted
- The business process that creates the data
- The EBO produced
- The EBS Router destination
- A queue routing summary

Add a component note on every Decision, Data Process, business-logic shape, complex map, connector change and bug fix:

```text
Title: <Developer Name>
Body:  <ChangeNumber> | <YYYY-MM-DD> | <short reason>
       e.g. CHG-12345 | 2026-05-28 | Added vendor null validation before EBO map
```

## Testing

- Unit test each subprocess on its own, with a harness in `04_Unit_Testing`.
- Run the Producer end to end through the EBS and queue to the Consumer.
- Check the `SWIN_ENTITY_ID` tracking value in Atom Management.
- Force an error. Confirm an audit row with status `E`, an email to the CRT list, and a working Boomi execution link in the mail body.
- Confirm the happy path writes an `S` row when the interface audits success.
- Check that the Exception Dashboard can replay the record, which requires `DPP_OriginalPayload` to be captured.

## Validation checklist

Run this before declaring a Producer done, and include it in any design answer.

- [ ] Name, folder and description follow the standard
- [ ] Start shape is Data Pass Through (or the exception is documented)
- [ ] `Set | Global Props` sets every global DPP, with `DPP_Application` / `DPP_Source` set to the source system
- [ ] Global Try/Catch directly follows the DPP shape: retry 0, All Errors
- [ ] Template scaffolding (STMCC GET, Random script, empty Message) removed
- [ ] `DPP_EntityID` set; request and response payloads captured around external calls
- [ ] HTTP responses checked
- [ ] Complex logic is in compliant subprocesses (Try/Catch, Exception, Return)
- [ ] Source data mapped to the shared EBO profile with the header populated
- [ ] EBO sent by `Process Route | <BusinessObject> EBS`, with no direct Consumer call or queue send
- [ ] No large dataset in the EBO
- [ ] `SWIN_ENTITY_ID` tracking on every connector
- [ ] Catch path unchanged from the template; mail body placeholders corrected
- [ ] CRT row exists for `DPP_Application` + `DPP_InterfaceName`
- [ ] No hard-coded credentials; environment extensions used
- [ ] Component notes added with change number and date

## When information is missing

Ask for these before building:

- Interface name
- Source application
- Business entity / EBO
- Trigger method (schedule, listener, web service)
- Payload format
- Expected volume
- Tracking ID
- Target applications the EBS should reach
