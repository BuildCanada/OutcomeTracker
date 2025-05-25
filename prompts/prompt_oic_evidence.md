# Gemini Prompt for Order in Council (OIC) Evidence Extraction

## Intended Use
You are assisting in building a structured, fact-based timeline of Canadian federal government actions for the purpose of tracking progress against specific government commitments. Your output will be used to help determine whether an Order in Council (OIC) represents a significant, verifiable step toward fulfilling a government promise. Your summary and scoring must be strictly factual, concise, and based only on the official record.

## CONTEXT
You are analyzing an Order in Council (OIC) from the Canadian Privy Council Office. Your goal is to:
- Create a concise, factual summary suitable for a timeline tracking government actions against promises made by the government.
- Determine if this OIC is significant enough to warrant further linking to specific government commitments.
- Ensure all outputs are strictly based on the OIC's official text and publication date; do not speculate or infer beyond the provided data.

## GOVERNMENT PLATFORM CONTEXT (Key Themes/Priorities for Relevance Assessment)
To assess the relevance of the OIC, consider its alignment with the following key themes and priorities derived from the government's platform documents:

**From 2025 Liberal Platform "Canada Strong":**
- **UNITE:** Building one Canadian economy with free internal trade and labour mobility; investing in nation-building infrastructure; protecting Canadian culture, environment, and values; and advancing partnership with Indigenous Peoples.
- **SECURE:** Strengthening Canadian sovereignty through a rebuilt military and enhanced defence; securing the Arctic; supporting veterans; defending the economy against trade threats and ensuring food security; fostering safe communities; and projecting global leadership.
- **PROTECT:** Safeguarding the Canadian way of life by strengthening public health care (including dental and pharmacare), supporting families with affordable childcare and education, preserving nature, upholding official languages and Charter rights, ensuring dignity for seniors and youth, and advancing reconciliation with Indigenous Peoples.
- **BUILD:** Creating the strongest G7 economy by making life more affordable, constructing more homes, managing immigration sustainably, transitioning to a clean economy, fostering business growth and innovation (especially in AI and science), empowering workers with new skills, and ensuring responsible government spending.

## ORDER IN COUNCIL DATA (to be filled in):
- OIC Number (Full, Raw): "{oic_number_full_raw}"
- OIC Date: "{oic_date}"
- Title/Summary (Raw): "{title_or_summary_raw}"
- Responsible Department (Raw): "{responsible_department_raw}"
- Act Citation (Raw): "{act_citation_raw}"
- Full Text (Scraped - snippet or full): "{full_text_scraped}"
- Assigned Parliamentary Session: "{parliament_session_id}"

## INSTRUCTIONS
1.  **timeline_summary**: Generate a concise (max 30 words), strictly factual summary of the OIC's action. Use active voice. **Do not include the OIC date in this summary.** Example: "New appointment made under Act X." or "Regulation Y amended to address Z." Avoid opinions or speculation.
2.  **potential_relevance_score**: Assign a score ("High", "Medium", or "Low") indicating whether this OIC represents a tangible, verifiable implementation of a significant policy or commitment, **particularly in relation to the GOVERNMENT PLATFORM CONTEXT provided above.** Use "High" only for OICs that clearly represent a significant advance or fulfillment of one or more of the stated platform priorities. Medium should have a clear link to progressing on of the commitments. Low will be a small impact announcement or change or not be related to one of the commitments. 
3.  **key_concepts**: Extract up to 10 keywords or 2-3 word phrases that capture the main topics, policy areas, specific acts, or affected entities in the OIC. These will be used later keyword matching. Be sure to include any legislation or bills that are mentioned. 
4.  **sponsoring_department_standardized**: Based on the "Responsible Department (Raw)" and the "Full Text (Scraped)", identify the primary department responsible for the OIC. Aim for a standardized name if possible (e.g., "Transport Canada" instead of "Minister of Transport"). If unclear or not applicable, leave as an empty string or null.
5.  **one_sentence_description**: Generate a single sentence (30-50 words) that explains the core purpose or action of the OIC. If there are key terms or specific concepts central to understanding the OIC, briefly define or clarify them within this sentence.

## OUTPUT FORMAT
Return a single JSON object with the following structure:
{{
  "timeline_summary": "...",
  "potential_relevance_score": "...",
  "key_concepts": ["...", "..."],
  "sponsoring_department_standardized": "...",
  "one_sentence_description": "..."
}}

**Do not include any additional commentary or explanation. Only return the JSON object.** 