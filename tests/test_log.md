# Test Log

Minimum 10 questions: 3 direct, 2 paraphrased, 1 misspelled, 2 multi-section, 2 irrelevant.

Run against the real 1,401-chunk index (`gpt-4o-mini`, `text-embedding-3-small`, K=5). Each answer was checked against the actual source doc, not just read at face value.

| # | Type | Question | Correct chunks retrieved? | Accurate answer? | Correct source cited? | Irrelevant rejected? | Top score | Notes |
|---|------|----------|---------------------------|------------------|-----------------------|----------------------|-----------|-------|
| 1 | Direct | What does the WalletClient class do in @bsv/sdk? | Yes | Yes | Yes (`bsv_ts_sdk_reference.txt`, wallet.md) | n/a | 0.700 | Clean, inline citation with link. |
| 2 | Direct | What does BRC-100 specify? | Partial | Mostly | Partial | n/a | 0.578 | Top chunk came from the BRC-56 "status note" (wallet messaging layer, superseded-by-BRC-100 discussion) rather than the core BRC-100 doc itself. Content is still accurate (unified wallet interface, method names, BEEF transaction data) but the cited source isn't the primary spec. |
| 3 | Direct | How is a 1Sat Ordinal inscription structured? | Yes | Yes | Yes (`ordinals_protocol_spec.txt`, Protocol Specification) | n/a | 0.675 | Correct inscription script opcodes, verified against source doc. |
| 4 | Paraphrased (of #1) | Describe what the WalletClient class is used for in the bsv sdk. | Yes | Yes | Yes (`bsv_ts_sdk_reference.txt` + `bsv_brc_standards.txt`) | n/a | 0.705 | Consistent with #1, slightly richer (pulled in BRC standards context too). |
| 5 | Paraphrased (of #3) | Explain the structure of an inscription for a 1Sat Ordinal. | Yes | Yes | Yes (`ordinals_protocol_spec.txt`) | n/a | 0.674 | Consistent with #3. |
| 6 | Misspelled | how do i creat a BSV-21 token | Yes | Yes | Yes (`ordinals_js_1sat_ord.txt`) | n/a | 0.644 | Misspelling had no effect on retrieval. `deployBsv21Token`/`DeployBsv21TokenConfig` code sample checked against source doc — real, not hallucinated. |
| 7 | Multi-section | How does the WalletClient class in @bsv/sdk relate to the BRC-100 wallet interface specification? | Yes, spans 2 files | Yes | Yes (`bsv_ts_sdk_reference.txt` + `bsv_brc_standards.txt`, cites the actual `wallet/0100.md` BRC-100 doc) | n/a | 0.757 | Best multi-section result: correctly synthesizes SDK docs and the BRC-100 spec. |
| 8 | Multi-section | How do I mint a BSV-21 token with the 1sat SDK and then look it up via ORDFS? | Partial | Partial | Yes for the mint half | n/a | 0.626 | Mint part fully correct and cited. For the ORDFS lookup half, the retrieved ORDFS chunk didn't contain lookup-specific detail, and the model correctly said so instead of guessing — good safety behavior, imperfect retrieval. |
| 9 | Irrelevant | What is the capital of France? | n/a | n/a | n/a | Yes | 0.121 | Safe fallback triggered correctly. |
| 10 | Irrelevant | Give me a lasagna recipe. | n/a | n/a | n/a | Yes | 0.144 | Safe fallback triggered correctly. |

## Summary

- 3/3 direct: 2 clean, 1 cited an adjacent/related doc instead of the primary one (#2) — content still accurate.
- 2/2 paraphrased: consistent with their direct counterparts, no degradation from rewording.
- 1/1 misspelled: no retrieval degradation from the typo.
- 2/2 multi-section: one clean success spanning two docs (#7); one partial success where the model correctly declined to guess on the part it couldn't support (#8) rather than fabricating.
- 2/2 irrelevant: both correctly rejected via the safe fallback, well below the 0.2 WEAK floor (0.121, 0.144).
- **No fabricated answers observed** in any of the 10 — the two "partial" cases (#2, #8) are retrieval/citation precision issues, not hallucination; in both cases the model stayed within what the retrieved context actually supported.
- A separate test (see README "K experiment") found a case where retrieval misses one side of a two-part question entirely (wallet connection + ordinal inscription) — the model's response there was to correctly refuse rather than fabricate, which is the desired fallback behavior even when retrieval itself falls short.
