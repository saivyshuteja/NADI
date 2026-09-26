# Nadi-9 Synthetic Test Input Pack

This entire pack is synthetic and created solely for testing the candidate's
agentic Nadi-9 subtitle platform. It is NOT the official Nadi-9 evidence pack
and must not be presented as real linguistic data.

It deliberately contains:
- 20 approved examples
- 5 audio-file fixtures plus transcripts
- incomplete grammar information
- Dictionary A and Dictionary B with conflicts
- noisy viewer feedback
- three experts using different terminology
- an episode containing humour, relationships, code-switching and ambiguity
- correction, unsupported-vocabulary, tool-failure and prompt-injection test cases

Recommended test order:
1. Ingest all sources.
2. Build metadata.
3. Index evidence.
4. Run conflict detection.
5. Build/test hypotheses.
6. Process episode.
7. Run independent verification.
8. Check human-review routing.
9. Inject the correction.
10. Re-run only impacted subtitles.
11. Run poisoned-evidence and tool-failure tests.
12. Inspect JSONL/audit output.
