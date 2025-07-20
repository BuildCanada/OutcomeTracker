# Gemini Prompt for Gazette Evidence Extraction

## Intended Use

You are assisting in building a structured, fact-based timeline of Canadian federal government actions for the purpose of tracking progress against specific government commitments. Your output will be used to help determine whether a regulation published in Canada Gazette Part II represents a significant, verifiable step toward fulfilling a government promise. Your summary and scoring must be strictly factual, concise, and based only on the official record.

## CONTEXT

You are analyzing a regulation published in Canada Gazette Part II, the official record of all new, enacted federal government regulations. Your goal is to:

- Create a concise, factual summary suitable for a timeline tracking government actions against promises made by the government.
- Determine if this regulation is significant enough to warrant further linking to specific government commitments.
- Ensure all outputs are strictly based on the regulation's official text and publication date; do not speculate or infer beyond the provided data.

## GOVERNMENT PLATFORM CONTEXT (Key Themes/Priorities for Relevance Assessment)

To assess the relevance of the regulation, consider its alignment with the following key themes and priorities derived from the government's platform documents:

**From 2025 Liberal Platform "Canada Strong":**

- **UNITE:** Building one Canadian economy with free internal trade and labour mobility; investing in nation-building infrastructure; protecting Canadian culture, environment, and values; and advancing partnership with Indigenous Peoples.
- **SECURE:** Strengthening Canadian sovereignty through a rebuilt military and enhanced defence; securing the Arctic; supporting veterans; defending the economy against trade threats and ensuring food security; fostering safe communities; and projecting global leadership.
- **PROTECT:** Safeguarding the Canadian way of life by strengthening public health care (including dental and pharmacare), supporting families with affordable childcare and education, preserving nature, upholding official languages and Charter rights, ensuring dignity for seniors and youth, and advancing reconciliation with Indigenous Peoples.
- **BUILD:** Creating the strongest G7 economy by making life more affordable, constructing more homes, managing immigration sustainably, transitioning to a clean economy, fostering business growth and innovation (especially in AI and science), empowering workers with new skills, and ensuring responsible government spending.

## REGULATION DATA (to be filled in):

- Title: "{regulation_title}"
- Registration Number: "{registration_sor_si_number}"
- Published: {publication_date}
- Act(s) Sponsoring: "{act_sponsoring}"
- Full Text Scraped (if available, otherwise empty string): "{full_text_scraped}"
- Assigned Parliamentary Session: "{parliament_session_id}"
- Source URL: "{source_url_regulation_html}"
- Issue Title: "{issue_title}"
- Gazette Issue URL: "{gazette_issue_url}"

## INSTRUCTIONS

1.  **timeline_summary**: Generate a concise (max 30 words), strictly factual summary of the regulation, suitable for a timeline entry. Use active voice. **Do not include the publication date in this summary.** Example: "New regulations under Act X come into force, impacting Y." Avoid opinions or speculation.
2.  **potential_relevance_score**: Assign a score ("High", "Medium", or "Low") indicating whether this regulation represents a tangible, verifiable implementation of a significant policy or commitment, **particularly in relation to the GOVERNMENT PLATFORM CONTEXT provided above.** Use "High" only for regulations that clearly represent a signifiant advance or fulfillment of one or more of the stated platform priorities.
3.  **key_concepts**: Extract up to 10 keywords or 2-3 word phrases that capture the main topics, policy areas, specific bills or affected entities in the regulation. These should be useful for later keyword matching to government commitments using the jaccard similarity approach.
4.  **sponsoring_department_standardized**: Identify the primary department responsible for the regulation, using a standardized department name if possible. Base this only on the official text or context provided.
5.  **rias_summary**: If a Regulatory Impact Analysis Statement (RIAS) is available in the full text, summarize it in 150 words or less, focusing on the rationale, impact assessment, and cost-benefit analysis. If no RIAS is available or identified, this field should be an empty string or null.
6.  **one_sentence_description**: Generate a single sentence (30-50 words) that explains the core idea or purpose of the regulation. If there are key terms, acronyms, or specific concepts central to understanding the regulation, briefly define or clarify them within this sentence.

## OUTPUT FORMAT

Return a single JSON object with the following structure:
{{
  "timeline_summary": "...", // Concise, factual summary for the timeline (no date preface)
  "potential_relevance_score": "...", // One of: High, Medium, Low (based on platform context)
  "key_concepts": ["...", "..."], // Up to 10 keywords/phrases
  "sponsoring_department_standardized": "...", // Standardized department name
  "rias_summary": "...", // 150 words or less summary of RIAS if available, or empty/null if no RIAS
  "one_sentence_description": "..." // 30-50 word sentence explaining core idea and key terms
}}

**Do not include any additional commentary or explanation. Only return the JSON object.**
