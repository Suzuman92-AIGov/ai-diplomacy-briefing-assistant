# Risk Matrix

| Risk | Example | Initial Level | Control | Residual Level |
|---|---|---:|---|---:|
| Hallucination | System adds unsupported facts | High | RAG citations and no-source-no-claim rule | Medium |
| Source bias | Overreliance on one type of source | Medium | Source reliability tiers and source diversity | Low/Medium |
| Outdated information | Old article treated as current | Medium | Published-date metadata and freshness filters | Low/Medium |
| Diplomatic misinterpretation | AI overstates policy significance | High | Human and senior review for sensitive topics | Medium |
| Data leakage | User inputs confidential material | High | Public-sources-only policy and training | Medium |
| Prompt injection | Malicious instructions in web content | Medium | HTML cleaning and instruction isolation | Low/Medium |
