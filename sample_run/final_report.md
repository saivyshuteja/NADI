# Nadi-9 Episode-01 release report

- Run: `1f5423e3`
- Recommendation: **HOLD_FOR_HUMAN_REVIEW**
- Model calls: 19 / 25
- Tool calls: 14 / 50
- Review items: 2

## Plan
- Inventory: 8 sources, 110 evidence records
- Do not trust largest (dictionary_A) or newest file automatically
- Retrieve evidence for risky scenes first (kinship, humour, gaps)
- Form and test hypotheses with counterexamples visible
- Translate only from evidence; independent verify; escalate uncertainty
- Apply mid-run correction to affected subtitles only
- Priority order: S002, S006, S005, S003, S001, S004, S007, S008

## Subtitle decisions

- `S001` RELEASE (p=0.9): Hello. → salu.
  - reason: All content words mapped from dictionary/example evidence without unresolved invention.
- `S002` RELEASE (p=0.9): You came back, elder brother? → ti ela bira-ka retu ven?
  - reason: Direct match to an approved example.
- `S003` RELEASE (p=0.9): I came home. → ka gharu ven.
  - reason: Direct match to an approved example.
- `S004` RELEASE (p=0.9): The food is not ready. → anna tayar na.
  - reason: Direct match to an approved example.
- `S005` HUMAN_REVIEW (p=0.65): The joke is funny. → None
  - reason: Approved example E18 uses an independently unattested token; escalate rather than copy a challenged form.; conflicts present
  - conflicts: ['example:E18 vs interview:interview_3']
  - review: Is 'zinglo' acceptable in this humour line, or should hasa be used alone?
- `S006` INSUFFICIENT_EVIDENCE (p=0.35): Please wait. The telescope is here. → None
  - reason: Required source term has no attested Nadi-9 form in the evidence pack.
  - review: What Nadi-9 form, if any, should be used for the unsupported term?
- `S007` RELEASE (p=0.9): The work is finished. → kama loven.
  - reason: Direct match to an approved example.
- `S008` RELEASE (p=0.9): Yes, family is home. → aha, kula gharu.
  - reason: Direct match to an approved example.

## Corrections

- C-R17: Grammar rule R17: after reconciliation with an older sibling, the respectful form bira-ka is required. Example E03 is withdrawn.
  - affected subtitles: ['S002']

## Limitations

- Sample pack is synthetic demonstration data, not the hidden evaluator pack.
- Mock mode uses deterministic evidence mapping rather than a hosted LLM.
