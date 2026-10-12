# Project Moonshot: Manufacturing and Engineering Proof Brief

Source: TRC meeting transcript, approximately 01:56-07:06 and 14:30-18:57.
Status: Two illustrative use cases distilled from the meeting, with technical assertions subject to verification.
Audience: Richie, Ryan, Alex, Honey and functional reviewers.

## Scenario A: Glenmare Dairy Foods, process manufacturing

### Illustrative operating context

- Two chilled-food plants, approximately 280 staff, deliveries to supermarkets.
- Paper-based allergen changeover and label checks.
- First-expiry-first-out (FEFO) not reliably enforced in the warehouse.
- Planning depends on spreadsheets, and yield and cost insight arrives late.
- Desired outcome: trace a recall in minutes, enforce checks at the line, and adapt plans when a supermarket runs a promotion.

### Representative proof

1. Choose one milk-derived product family with ingredients, batches, best-before dates and customer shipments.
2. Capture intake, batch genealogy, manufacturing stages, label approval, allergen changeover and outbound deliveries.
3. Run a timed mock recall to find affected inputs, finished goods, locations and customers.
4. Test a blocked allergen-changeover step and a mislabelled lot.
5. Demonstrate FEFO handling and exception alerts, if verified on the target edition/version.
6. Run a simulated retail promotion and show how supply planning responds.
7. Display assumptions, results and any manual steps still required.

### Capability boundaries

- Distinguish Odoo standard manufacturing, inventory and quality workflows from site-specific configuration.
- Validate recall, batch handling, FEFO and allergen requirements against actual plant controls and applicable food-safety obligations.
- Any TRC extension is a proposed scope item until implemented, tested and approved.
- Illustrative annual savings of $250k-$750k discussed in the meeting are not customer-validated. Show the model and assumptions before public claims.

## Scenario B: Kestrel Power Supplies, discrete engineering manufacturing

### Illustrative operating context

The meeting refers to an engineering/power-supplies example involving product variants, bills of materials, routings, quality checks, equipment burn-in or test rigs, compressors and industrial interfaces. Detailed client specifications were not provided in the transcript.

### Representative proof

1. Configure one representative product with variants, materials, work centers and routing.
2. Issue a production order, consume components and capture production progress.
3. Define a quality gate based on the real operational procedure, not merely the generic Odoo workflow.
4. Capture an illustrative reading from a burn-in test or machine controller through a simulated interface first.
5. Trigger a quality exception when a reading breaches a validated threshold.
6. Show who is notified, the hold/rework decision, audit evidence and the impact on release.
7. Trace the resulting production cost, status and customer order.

### Industrial device discovery checklist

- Manufacturer and model, firmware/version, protocol and available interface documentation.
- Is the signal available through MQTT, OPC UA, HTTP, serial, file export, PLC gateway or another supported method?
- Sampling frequency, buffering needs, reliability, timestamps, units and calibration.
- Security boundary between operational technology and business applications.
- What decision should the data drive, who must act, and what happens if the signal is missing?
- Which components are documented Odoo capabilities versus a custom integration service?

Important distinction: Odoo's IoT device/peripheral framework does not, by itself, prove compatibility with arbitrary industrial PLCs and process equipment. Each interface requires proof.

## Prototype experiment requested in the meeting

- Give Richie a written, bounded requirements package.
- Start from a clean target-version Odoo test environment.
- Ask the team to configure or build the proof and record what is genuinely standard, what needs an add-on/integration, what requires development and what fails.
- Evaluate the result on functionality, elapsed time, developer effort, errors, security, upgradeability and test evidence.

## GoTestify pilot for manufacturing discovery

- Invite a production supervisor, quality manager and finance/controller persona to complete narrated screen recordings of the same product's journey from receipt to shipment.
- Compare actual process variance and undocumented workarounds.
- Attempt an export into structured roles, processes, exceptions, dependencies and acceptance criteria.
- This requires validating GoTestify's capture scope, permitted business data, export methods and technical integration.

## Deliverables from the proof

1. Demonstrable Odoo workflows with test data.
2. Requirements-to-capability matrix with evidence links.
3. Gap/extension backlog and integration protocol register.
4. Timed proof results and development effort.
5. Human functional approval or documented no-fit decision.

## Transcript anchors

01:56-07:06 manufacturer entry, Glenmare example, recall and proof-before-commitment; 15:39-18:57 Kestrel example and industrial integrations; 34:00-38:59 recorded legacy process walkthroughs and potential GoTestify integration.
