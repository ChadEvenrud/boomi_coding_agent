---
name: swinerton-ebs-router
description: Builds and reviews Swinerton Boomi EBS Router processes (Enterprise Business Service, "<Object> EBS", Router_<BusinessObject>) that receive an Enterprise Business Object (EBO) from a Producer through a Process Route and send it to one point-to-point Atom Queue per consuming application. Use when creating, cloning from the Router template, modifying, or reviewing any Swinerton EBS or router; when adding a new consumer/target to an interface; when designing routing on the EBO Transmission Header, the Process Route component and key, queue send operations, per-company sync flags, naming, folder, or description. Pairs with swinerton-producer, swinerton-consumer and swinerton-error-handling.
---

# Swinerton EBS Router Processes

The EBS Router is the hub between Producers and Consumers:

```text
Producer --Process Route--> EBS Router --Atom Queue send--> Queue_<Interface>_<App> --> Consumer
```

It has one job: read the EBO's Transmission Header and put the unchanged EBO on the queue of every consumer that should receive it. Adding a new target system means adding one route path and one queue in the EBS. The Producer does not change.

The EBS must not:
- transform the business payload, unless that is required for routing;
- call Consumer processes (Process Call or Process Route);
- contain target-system business logic, lookups or API calls;
- write to any system other than Atom Queues;
- bypass queues by handing the EBO straight to a Consumer.

If a request asks for a non-compliant pattern, answer:

```text
That pattern does not follow Swinerton Boomi standards because <reason>.
The compliant approach is <recommended design>.
```

Then build the compliant version.

## Starting point: the Router template

| Item | Value |
| --- | --- |
| Template process | `Router_<BusinessObject>` |
| Component ID | `7bcccdc6-6bf2-48ae-9db3-a5b306e71b4c` (v3) |
| Boomi folder | Swinerton Incorporated/Integrations/Timberlab/Templates |
| Local export | `process_template/process/Router_BusinessObject.xml` |
| Sibling templates | `Producer_<Source_System>_<BusinessObject>` (`3f82bd52-5988-4eb7-8a57-a4034d0d3802`), `Consumer_<Target_System>_<BusinessObject>` (`df64e027-5fc4-4c68-8f81-b821fc446809`) |

### What the template gives you

```text
Start (Data Pass Through)
-> Route shape (no route property, no route values)
     Default -> (unconnected)
```

Process options: Allow Simultaneous = false, Stop Processing If Zero Documents = true, Update Run Dates = true.

### Fill these template gaps every time you clone it

The template is a bare skeleton. To finish it:

1. **Route property.** Point the Route shape at the EBO Transmission Header field that decides routing (see Routing design).
2. **Route values.** Add one value per routing key. Label the shape `Route | Based on <HeaderField>`.
3. **Default path.** Connect `Default` to a Stop shape labelled `Stop | Unrouted <Key>`. Never leave it unconnected. If an unknown key is a real error for the interface, end Default with an Exception shape instead, so the Producer's catch path reports it (see Error behaviour).
4. **Queue sends.** Add one Atom Queue **Send** shape per consumer, using that consumer's `Send_<Interface>_<Application>` operation.
5. **Process Route component.** Create the `Route | <BusinessObject> EBS` component that Producers call. The template does not include it.
6. **Description.** Add the process description; the template has none.

## Routing design

Route on the **Transmission Header**, never on business payload fields, except for the per-company flag below.

```xml
<TransmissionHeader>
  <TransmissionID/>
  <CreationDateTime/>
  <SourceApplication/>     <!-- common routing key: who produced it -->
  <TargetApplication/>     <!-- routing key when the Producer names a target -->
  <TransactionCode/>       <!-- routing key for create/update or business-flow variants -->
</TransmissionHeader>
```

Use these building blocks, in order of preference:

| Need | Shape | Example in production |
| --- | --- | --- |
| Choose a path by one header value | **Route** shape on the header field | `COAEBS`: `Route \| Based on TransmissionID` → `CMiC`, `Certify`, `Workday`, `AURORA`; `Quantities EBS`: `Route\|TransmissionSource` → `WORKMAX` |
| Fan one EBO out to several consumers | **Branch** shape, one branch per consumer queue | `COAEBS` CMiC path: `Branch \| Project Task Queues` (4 queues) |
| Yes/no gate on one path | **Decision** shape on a header field | `Decision \| Check is Source System = CMiC?` |
| Per-company or per-target on/off switch | **Decision** on a cross-reference lookup | `Decision \| SyncData = TRUE? - WORKDAY`, using `CRT \| Company Control Table` (`81be6747-ae0e-4fc3-985f-bde65fa02401`), inputs CompCode + TargetApp + InterfaceName, output `SyncData` |
| Business-flow variant (onboarding vs sync) | **Route** on a routing-code field | `BusinessPartner EBS`: `TransmissionRoutingCode` → `AutoDeskCompaniesOnboarding` / `AutodeskSync` |

Rules:
- Every consumer queue gets its own path that ends in its own Queue Send and a Stop. Do not chain one queue send after another on the same path.
- Decisions answer routing questions only ("should target X get this?"). Validation and enrichment belong in the Producer or Consumer.
- Turning a target on or off for a company is a CRT data change, not a process change. Prefer the `CRT | Company Control Table` `SyncData` pattern over hard-coded company lists.
- Keep the EBO byte-for-byte as received. Change it only when routing truly needs it, and document why in a component note.

## Process Route component

Producers reach the EBS through a Process Route component, never a Process Call.

| Setting | Standard |
| --- | --- |
| Name | `Route \| <BusinessObject> EBS`, e.g. `Route \| Job EBS`, `Route \| BusPartner EBS` |
| Key | `<BusinessObject>EBS`, e.g. `JobEBS`, `BusPartnerEBS`, `COAEBS` |
| Process entry | The EBS Router process |
| Start type | Pass through (`enforcePassthrough="true"`) |
| Return paths | None by default. Add one only when a synchronous web-service Producer must return a response; label it `Return \| <What>` |
| Caller shape | `Process Route \| <BusinessObject> EBS`, with Wait = true and Abort = true |

Use one Process Route per business object. When a new EBS version is needed, add a new key or repoint the existing key rather than editing every Producer.

## Queue sends

| Item | Standard |
| --- | --- |
| Queue type | Point-to-point, one per consuming application |
| Queue name | `Queue_<InterfaceName>_<ConsumingApplicationName>`, e.g. `Queue_Job_CMiC`, `Queue_ProductionOrder_SAP` |
| Send operation | `Send_<InterfaceName>_<ApplicationName>`, e.g. `Send_Job_CMiC` |
| Shape label | `Queue \| <Application>` |
| Batch size | 0 or 1 unless a larger value is documented |
| Payload | The EBO only. For large data, the EBO carries metadata and parameters, and the Consumer fetches the rest |
| Tracking | `SWIN_ENTITY_ID` on the send operation, so the entity can be followed from Producer through queue to Consumer |
| Connection | The shared queue connection; values via environment extensions |

A new consumer needs four things:
- a new queue;
- a `Send_` operation, used in the EBS;
- a `Listen_` operation, used in the Consumer;
- one new EBS path.

## Error behaviour

The EBS does not carry its own enterprise catch path.

- The Producer calls the EBS with a Process Route that has Wait = true and Abort = true, so any EBS failure (a queue send error, or an Exception on an unknown key) lands in the **Producer's** global Try/Catch. The Producer then sends it through `Route | Error Notification & Audit` with the Producer's DPPs, `DPP_OriginalPayload` included.
- Therefore do not set or overwrite global DPPs in the EBS. Do not add a Try/Catch that swallows errors. Do not call the error route from the EBS.
- Once the EBO is on a queue, delivery problems are the Consumer's to report.
- The Exception Dashboard replays stored EBOs into the EBS by interface (`Listen Exception Dashboard [Rerun & Withdraw]` routes to `COAEBS`, `JobEBS`, `BusPartnerEBS`, `BUDGET_EBS` and others). An EBS must therefore accept a replayed EBO exactly as the Producer sent it. Keep routing based on header data that is stored with the EBO.
- When you create a new EBS, add its interface key to the rerun router so replays can reach it.

See **swinerton-error-handling** for the full error path.

## Naming and location

| Item | Convention | Examples |
| --- | --- | --- |
| Process | `EBS_<Interface>_Router`. The template's `Router_<BusinessObject>` is acceptable while the template keeps that name | `EBS_Job_Router` |
| Legacy names (existing interfaces only) | `<Object> EBS`, `<Object>EBS`, `[Sub] ... : <Object> EBS` | `COAEBS`, `Quantities EBS`, `Payroll EBS`, `[Sub] [Sync/Onboarding] : BusinessPartner EBS` |
| Folder | `Integrations/<Interface>/EBS` | `Integrations/2) COA/EBS` |
| EBO map (if one is shared) | `Integrations/<Interface>/EBS/MAP_EBO_<Interface>` | |
| Process Route component | Same `EBS` folder | |
| Shapes | `<Type> \| <What>` | `Route \| Based on SourceApplication`, `Branch \| CMiC Queues`, `Decision \| SyncData = TRUE? - WORKDAY`, `Queue \| CMiC` |

The name `Router_<BusinessObject>` (template) and the standard folder entry `EBS_<Interface>_Router` disagree. For new work use `EBS_<Interface>_Router`, and raise the mismatch so the template can be renamed.

## Process options

- **Allow Simultaneous.** Default false, as in the template. Set it to true when several Producers or high-volume runs share the EBS and routing has no ordering dependency (`COAEBS` runs with true). The EBS is stateless, so this is usually safe.
- **Stop Processing If Zero Documents:** true.
- No connectors other than Atom Queue sends.
- If a CRT lookup is needed, use Decision shapes on cross-reference values.

## Description and notes

The process description must state:
- the EBO received, and the Process Route and key that call it;
- the header field(s) used for routing;
- each route value → consumer application → queue name;
- any CRT switch used, with its inputs and output;
- what happens to unrouted documents.

Add a component note on every Route, Decision and Branch shape:

```text
Title: <Developer Name>
Body:  <ChangeNumber> | <YYYY-MM-DD> | <short reason>
       e.g. CHG-12345 | 2026-05-28 | Added SAP queue route for ProductionOrder
```

## Testing

- Unit test from a harness in `Integrations/<Interface>/EBS` or `04_Unit_Testing`. Send sample EBOs for each route value plus one unknown value.
- Confirm each sample lands on exactly the expected queue(s) and nowhere else (Atom Queue management, message counts).
- Confirm the EBO on the queue is identical to the input.
- Confirm the `SWIN_ENTITY_ID` tracking value shows on the send.
- For CRT switches, test each company/target combination with `SyncData` on and off.
- Force a queue send failure. The Producer's catch path should write an audit `E` and send the email.
- Replay a record from the Exception Dashboard. It should route the same way.

## Validation checklist

- [ ] Name, folder and description follow the standard
- [ ] Start shape is Data Pass Through
- [ ] Called only through `Route | <BusinessObject> EBS` (Process Route, key `<BusinessObject>EBS`), never a Process Call
- [ ] Routes only on Transmission Header fields (or a documented CRT switch)
- [ ] Route shape has a property, labelled values, and a connected Default
- [ ] One path, one Queue Send and one Stop per consumer queue
- [ ] Queue and operation names follow `Queue_` / `Send_` conventions; point-to-point; batch 0/1
- [ ] `SWIN_ENTITY_ID` tracking on every send
- [ ] EBO not transformed; no target business logic, lookups or API calls
- [ ] No Consumer calls; no queue bypass
- [ ] No catch path that swallows errors; no global DPPs overwritten
- [ ] New interface key added to the Exception Dashboard rerun router
- [ ] No hard-coded credentials; environment extensions used
- [ ] Component notes on Route, Decision and Branch shapes

## When information is missing

Ask for:
- the interface and EBO name;
- the Producers that will call it;
- the consuming applications and their queues;
- which header field decides routing, and its values;
- whether any target is switched on or off per company;
- what should happen to unrouted documents (silent stop or error);
- expected volume and whether simultaneous runs are needed.
