# References and reading boundary

Primary URLs were checked on 3 November 2026. These are scholarly/system
references, not experiments reproduced by the present manuscript. No competitor
code is copied. Repository identities below preserve RDR-01's inspected versions;
current landing pages are not substituted for those source pins.

<a id="sweagent"></a>
**[1]** John Yang, Carlos E. Jimenez, Alexander Wettig, Kilian Lieret, Shunyu Yao,
Karthik Narasimhan, and Ofir Press. 2024. *SWE-agent: Agent-Computer Interfaces
Enable Automated Software Engineering*. arXiv:2405.15793v3.
[Author record](https://arxiv.org/abs/2405.15793v3).
Used for ACI/interface framing, not numerical comparison. Author abstract and
metadata checked; no rerun of its evaluations.

<a id="codestruct"></a>
**[2]** Myeongsoo Kim, Chao-Chun Hsu, Dingmin Wang, Shweta Garg, Varun Kumar,
and Murali Krishna Ramanathan. 2026. *CODESTRUCT: Code Agents over Structured
Action Spaces*. Proceedings of ACL 2026, Volume 1: Long Papers, pp. 13290–13306.
doi:[10.18653/v1/2026.acl-long.607](https://doi.org/10.18653/v1/2026.acl-long.607).
[Publisher record](https://aclanthology.org/2026.acl-long.607/).
[Inspected artifact](https://github.com/amazon-science/CodeStruct/tree/d89efa473754f455d38ab47b4dc938cfc8334a0d).
RDR-01 read paper text and selected actual read/edit implementations; this draft
rechecks the primary bibliographic record and frames it as closest prior art.
No competitor benchmark is reproduced; absence of a feature outside inspected
paths is not inferred. Artifact license is CC-BY-NC-4.0, not ALVA's license.

<a id="serena"></a>
**[3]** Serena contributors. *Serena: semantic retrieval and editing toolkit*.
[Official repository](https://github.com/oraios/serena).
[Pinned symbol-tool source](https://github.com/oraios/serena/blob/ede329aaf0c824bea75455a2926f01420d7aa620/src/serena/tools/symbol_tools.py).
Software reference; no asserted paper venue/year. The repository and RDR-01's
specific symbol-editing source support the narrow capability description.
Uninspected backend transaction guarantees remain unverified.

<a id="openrewrite"></a>
**[4]** OpenRewrite contributors. *Lossless Semantic Trees (LST)*.
[Official documentation](https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees).
Documentation reference, accessed 3 November 2026. Supports type attribution and
format preservation, not an assertion of universal semantic preservation or a
comparative ALVA result. No recipe/backend was executed.

<a id="plump"></a>
**[5]** Detlef Plump. 1999. *Term Graph Rewriting*. In Hartmut Ehrig, Gregor
Engels, Hans-Joerg Kreowski, and Grzegorz Rozenberg (eds.), Handbook of Graph
Grammars and Computing by Graph Transformation, Volume 2: Applications,
Languages and Tools. World Scientific, pp. 3–61.
doi:[10.1142/9789812815149_0001](https://doi.org/10.1142/9789812815149_0001).
[Author bibliography](https://www-users.york.ac.uk/~djp10/papers.html),
[author-hosted chapter](https://www-users.york.ac.uk/~djp10/Papers/tgr_survey.pdf).
Bibliography and survey framing only; no detailed locality theorem/algorithm is
attributed without proof inspection. The institutional page timed out during
this draft's refresh; the author bibliography was accessible.

<a id="git"></a>
**[6]** Git contributors. *git-update-ref: Update the object name stored in a
ref safely*. [Official manual](https://git-scm.com/docs/git-update-ref).
Documentation reference, accessed 3 November 2026. Expected-old-value checking
and reference transactions are prior publication mechanisms; this is not an
audit of ALVA's GitHub branch protections or a behavioral guarantee.

<a id="taubench"></a>
**[7]** Shunyu Yao, Noah Shinn, Pedram Razavi, and Karthik Narasimhan. 2024.
*tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*.
arXiv:2406.12045v1. [Author record](https://arxiv.org/abs/2406.12045v1).
Author abstract specifies final database-state comparison. Used to acknowledge
state-based evaluation prior art, not to import its rates into ALVA.

<a id="verifiedcalls"></a>
**[8]** Isham Kalappurackal Mansoor, Abhishek Phadke, and Pratip Rana. 2026.
*Verified Tool Calls Improve LLM Agent Reliability Under Non-Atomic Failures*.
arXiv:2608.02645v1. [Author record](https://arxiv.org/abs/2608.02645v1).
Preprint, not asserted peer-reviewed. Author abstract describes verification,
idempotency and retry in simulation; artifact/effect sizes not independently
reproduced. No coding-agent locality coverage is presumed absent.

<a id="aft"></a>
**[9]** Zihao Wang. 2026. *Callability Is Not Operability: Controlled Interface
Interventions for LLM Agents*. arXiv:2608.23628v2.
[Author record](https://arxiv.org/abs/2608.23628v2).
Preprint, not asserted peer-reviewed. Author abstract supports the distinction
between callable tools and action-relevant operational state. Detailed overlap
is bounded by that reading depth; no global novelty claim follows.
