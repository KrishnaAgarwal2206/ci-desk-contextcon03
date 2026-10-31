# Architecture diagram

```mermaid
flowchart TD
    B[Research brief] --> P["Planner<br/>Claude · deterministic fallback"]
    P --> CD

    subgraph CD[Crustdata data plane]
        ID[Identify / Search]
        EN[Company Enrich]
        JB[Job Search]
        PP[Person Search]
        WB[Web Search]
    end

    CD --> EV[("Evidence store<br/>provenance + retrieval time")]
    EV --> CL[Claims & dedupe]
    CL --> ES[("Event store<br/>shared")]
    ES --> PS["Persona policy scoring<br/>5 stakeholders · versioned"]
    PS --> RB["Rich briefs<br/>Claude · citation-validated"]

    RB --> FB[NL feedback]
    FB --> PR["Proposal<br/>Claude · typed"]
    PR --> VD[Validation · diff · replay]
    VD --> AP[Named reviewer approval]
    AP --> NV[New policy version]
    NV -->|re-score that persona| PS

    CL -.-> W["Crustdata Watcher<br/>company entity watch"]
    W --> RH[Run-history reconciliation]
    W --> WH[Signed webhook]
    RH --> IG["Ingest<br/>test / baseline isolated"]
    WH --> IG
    IG --> ES

    CD -.-> TR[("Trace<br/>credits · tokens · cost")]
    P -.-> TR
    RB -.-> TR
    PR -.-> TR
```

Notes: Watcher create/read-back and run-history reconciliation are live-verified; the signed webhook receiver is unit-tested only (no public HTTPS URL), and no Watcher change event has been received yet. Monitoring is scheduled, not real time.
