**Task**
You are evaluating a Canadian federal government commitment. Your task is to rank this commitment based on its expected contribution to national prosperity, using the provided Build Canada Core Tenets and the relevant Election Economic Context.

**Scoring Criteria (Relevance and Scale of Impact, not Endorsement):**
For the given mandate commitment:

1.  **Relevance (R)** — Alignment with Build-Canada tenets:
    - 1 = Touches none of the tenets.
    - 2 = Indirectly touches on 1-2 tenets.
    - 3 = Advances 1-2 tenets OR indirectly advances multiple.
    - 4 = Directly advances 1-2 tenets OR significantly advances multiple tenets.
    - 5 = Directly and substantially advances 3 or more tenets.

2.  **Scale (S)** — Plausible Gross Domestic Product (GDP) / productivity / trade delta:
    - 1 = < C$0.1 Billion impact, or primarily local/regional impact.
    - 2 = C$0.1 Bn to < C$1 Bn impact.
    - 3 = C$1 Bn to < C$5 Bn impact.
    - 4 = C$5 Bn to < C$10 Bn impact.
    - 5 = ≥ C$10 Billion impact OR > 0.5 percentage point change in national GDP.

3.  **Direction (`bc_promise_direction`)** — Direction of alignment with Build Canada tenets:
    - `positive`: The commitment, if successfully implemented, would generally advance or support the Build Canada Core Tenets.
      _Examples: Elimination of inter-provincial trade barriers, Reducing corporate tax rates_
    - `negative`: The commitment, if successfully implemented, would generally undermine or contradict the Build Canada Core Tenets.
      _Example: A 10% increase in corporate taxes across the board, New government regulations that slow down infrastructure investments_
    - `neutral`: The commitment has no clear positive or negative alignment, is primarily focused on areas outside the direct scope of the tenets (e.g. purely social/cultural with no specified economic link), or has mixed effects that balance out.

4.  **Overall Rank (`bc_promise_rank`)** — Based on R and S scores:
    - `strong`: If R ≥ 4 AND S ≥ 4.
    - `medium`: If (R + S) ≥ 6 (and not already 'strong').
    - `weak`: Otherwise.

**Method**

1.  Analyze the provided `CommitmentText` in conjunction with the `Build Canada Core Tenets` and the `Election Economic Context`.
2.  If the commitment mentions specific programs, budget items (e.g., "Budget 2021"), or plans (e.g., "2021 MMIWG and 2SLGBTQQIA+ National Action Plan"), consider their general nature and stated goals if widely known. You are not expected to perform external live Google searches for every detail, but rely on the provided context and general knowledge.
3.  Assign R and S scores based on the criteria.
4.  Determine the `bc_promise_direction`.
5.  Determine the overall `bc_promise_rank`.
6.  Formulate a concise `bc_promise_rank_rationale` (less than 40 words) explaining your R, S, direction, and rank. Do not include references to specific R or S scores in the rationale, but explain the reasoning.

**Guidance**

- Prioritize commitments affecting national productivity, investment, tax/regulation, trade, or resource development at a **national** scale.
- Use dollar amounts, sector focus, and geographic scope mentioned in the commitment text to help gauge Scale.
- Internal government operational changes, specific cultural programs, or social service programs are usually **Low Scale** unless large savings or nationwide economic effects are explicitly stated and plausible.
- If data within the commitment or provided context is insufficient to make a confident estimate for Scale, assign **Scale = 1**.
- Keep rationales concise, fact-anchored to the promise and tenets, and non-political in tone.
- Most commitments will appear to be positive on the surface so you need to think about the context of the promise and how holistic impact on Canadian competitiveness and productivity if the promise is implemented.

**Example of Thinking (for your internal reference, your output should be JSON):**

- Commitment: "Increase corporate taxes by 5%"
  - Thinking: Directly impacts corporate taxation (Tenet 7), significantly affecting national investment (Tenet 5) and competitiveness (Tenet 3). Likely high Relevance (e.g., R=5) and potentially large Scale (e.g., S=4 or 5). Direction is negative with respect to tenets promoting investment.
  - Output Values: `bc_promise_rank: strong`, `bc_promise_direction: negative`, `bc_promise_rank_rationale: Significantly impacts corporate taxation and investment, negatively aligning with tenets for competitiveness and economic freedom.` (19 words)
- Commitment: "Fund a local arts festival with $500,000."
  - Thinking: Primarily cultural funding. Limited direct alignment with economic tenets (R=1). Small scale (S=1). Direction neutral.
  - Output Values: `bc_promise_rank: weak`, `bc_promise_direction: neutral`, `bc_promise_rank_rationale: Localized cultural funding with minimal direct impact on national economic prosperity or alignment with core tenets.` (18 words)
- Commitment: "Invest $10M in a new regional bike path."
  - Thinking: Small-scale infrastructure (S=1), localized impact. Potentially touches Tenet 6 (public services) or Tenet 5 (investment) very indirectly (R=1 or 2). Direction neutral.
  - Output Values: `bc_promise_rank: weak`, `bc_promise_direction: neutral`, `bc_promise_rank_rationale: Localized infrastructure project with limited scale and minor indirect links to national economic tenets.` (17 words)
- Commitment: "Establish a $500M fund for Indigenous business export development."
  - Thinking: Aims to grow exports (Tenet 4) and encourage investment/innovation for a specific group (Tenet 5). Scale is moderate ($500M = S=3). Relevance is moderate to strong (e.g. R=3 or 4). Direction positive.
  - Output Values: `bc_promise_rank: medium`, `bc_promise_direction: positive`, `bc_promise_rank_rationale: Supports Indigenous business exports and investment, showing moderate scale and positive alignment with economic development tenets.` (19 words)
- Commitment: "National review of all business subsidies to cut red tape and reallocate $50B to fund public-private initiatives to build new energy infrastructure."
  - Thinking: Aims to reduce bureaucratic inertia (Tenet 2), reallocate significant capital towards investment and resource/infrastructure development (Tenet 5). Scale is very large ($50B = S=5). Relevance is very high (R=5). Direction positive.
  - Output Values: `bc_promise_rank: strong`, `bc_promise_direction: positive`, `bc_promise_rank_rationale: Major initiative to reduce bureaucracy and boost energy infrastructure investment, strongly aligning with multiple core tenets.` (19 words)

**Output Format**
Return your response as a single, minified JSON object with three keys: "bc_promise_rank", "bc_promise_direction", and "bc_promise_rank_rationale".

Example JSON output:

```json
{
  "bc_promise_rank": "strong",
  "bc_promise_direction": "positive",
  "bc_promise_rank_rationale": "This promise directly addresses core economic tenets, fostering significant growth and innovation aligned with Build Canada's vision."
}
```
