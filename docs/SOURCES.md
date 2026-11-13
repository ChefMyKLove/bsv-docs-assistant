# Knowledge base sources

All files retrieved 2026-10-16. Each `.txt` file starts with `SOURCE:`, `RETRIEVED:` and `LICENSE:` header lines. Text is as published (light cleanup only), not summarized.

| File | Source | Covers | License |
|---|---|---|---|
| `bsv_ts_sdk_reference.txt` | https://github.com/bsv-blockchain/ts-sdk/tree/master/docs (@bsv/sdk 2.0.16) | Transaction, script, primitives, wallet (BRC-100 WalletClient), messages, identity reference pages | Open BSV License v4 |
| `bsv_brc_standards.txt` | https://github.com/bsv-blockchain/BRCs | README index plus 25 BRCs (wallet interface, BEEF/BUMP/SPV, key derivation, mutual auth) | Open BSV License (per README) |
| `ordinals_protocol_spec.txt` | https://github.com/BitcoinSchema/1sat-ordinals | 1Sat Ordinals protocol spec, BSV-20, BSV-21, metadata schemas, ordinal lock | CC0 1.0 |
| `ordinals_ordfs_names_libraries.txt` | https://github.com/BitcoinSchema/1sat-ordinals | OrdFS, directories, streams, OpNS names, libraries, partially signed transactions | CC0 1.0 |
| `ordinals_js_1sat_ord.txt` | https://github.com/BitcoinSchema/js-1sat-ord | js-1sat-ord README, metadata, reinscription | MIT (package.json only) |
| `gorillapool_1sat_sdk.txt` | https://github.com/b-open-io/1sat-sdk | Current TypeScript SDK and CLI, OpNS paymail bind, BAP URL scheme | MIT |
| `gorillapool_api_and_stack.txt` | https://github.com/BitcoinSchema/1sat-ordinals/blob/main/public-apis.md (plus 1sat-server and 1sat-stack READMEs) | Legacy GorillaPool API endpoints, indexing architecture | public-apis.md CC0; 1sat-server and 1sat-stack: no license file found |
| `scrypt_scrypt-ts_toolchain.txt` | npm: scrypt-ts 1.4.5, scrypt-cli 0.2.3, scrypt-ts-lib 0.1.28 | READMEs, changelog, frontend integration guide (wallet, deploy, call) | MIT |
| `scrypt_scryptlib_reference.txt` | npm: scryptlib 2.2.6 | scryptlib README | MIT |

## Known gaps and caveats

- **sCrypt coverage is thin.** docs.scrypt.io and the sCrypt-Inc docs repo could not be retrieved, so there is nothing on language basics, testing guides, or sCrypt + ordinals guides. Only package READMEs are included.
- **Not the live sites.** docs.1satordinals.com, the GorillaPool Swagger reference, and docs.bsvblockchain.org were not retrievable. Content comes from the GitHub repos behind them and may differ from the live sites.
- **Legacy API.** The GorillaPool `ordinals.gorillapool.io` endpoints are marked historical by the 1Sat docs; new work uses 1sat-stack and `@1sat/client`. The assistant's system prompt should say so.
- **BRC coverage is partial.** 25 of roughly 170 BRCs. The SDK reference omits the auth, compat, kvstore, overlay-tools, registry, remittance, storage and totp pages.
- **Licenses.** The Open BSV License restricts use of the covered material to the BSV blockchains; 1sat-stack and 1sat-server licenses are unconfirmed. Fine for a private course knowledge base; re-check before any public redistribution.
- **BSV-20** was not checked for being superseded by BSV-21.
