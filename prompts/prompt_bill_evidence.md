# Gemini Prompt for Bill Evidence Extraction

## Intended Use
You are assisting in building a structured, fact-based timeline of Canadian federal legislative actions for the purpose of tracking progress against specific government commitments. Your output will be used to help categorize and describe legislative bills and their purpose in relation to government platform commitments.

## CONTEXT
You are analyzing a Canadian federal legislative bill from LEGISinfo. Your goal is to:
- Create a concise, factual summary suitable for a timeline tracking legislative actions
- Extract key concepts and terms that will help match this bill to government commitments
- Determine the sponsoring department and standardize its name
- Provide a descriptive summary that explains the bill's purpose and key provisions

## GOVERNMENT PLATFORM CONTEXT (Key Themes/Priorities for Relevance Assessment)
To assess the relevance of the bill, consider its alignment with the following key themes and priorities derived from the government's platform documents:

**From 2025 Liberal Platform "Canada Strong":**
- **UNITE:** Building one Canadian economy with free internal trade and labour mobility; investing in nation-building infrastructure; protecting Canadian culture, environment, and values; and advancing partnership with Indigenous Peoples.
- **SECURE:** Strengthening Canadian sovereignty through a rebuilt military and enhanced defence; securing the Arctic; supporting veterans; defending the economy against trade threats and ensuring food security; fostering safe communities; and projecting global leadership.
- **PROTECT:** Safeguarding the Canadian way of life by strengthening public health care (including dental and pharmacare), supporting families with affordable childcare and education, preserving nature, upholding official languages and Charter rights, ensuring dignity for seniors and youth, and advancing reconciliation with Indigenous Peoples.
- **BUILD:** Creating the strongest G7 economy by making life more affordable, constructing more homes, managing immigration sustainably, transitioning to a clean economy, fostering business growth and innovation (especially in AI and science), empowering workers with new skills, and ensuring responsible government spending.

## BILL DATA (to be filled in):
- Long Title: "{bill_long_title_en}"
- Short Title: "{bill_short_title_en}"
- Legislative Summary: "{short_legislative_summary_en_cleaned}"
- Sponsor Title: "{sponsor_affiliation_title_en}"
- Sponsor Name: "{sponsor_person_name}"
- Parliament Session: "{parliament_session_id}"

## INSTRUCTIONS
1. **timeline_summary_llm**: Generate a concise (max 30 words), strictly factual summary of the bill's core purpose, suitable for a timeline entry. Use active voice. Example: "Bill proposes amendments to Income Tax Act regarding disability tax credits." Avoid opinions or speculation.

2. **one_sentence_description_llm**: Generate a single sentence (30-50 words) that explains the core idea and key provisions of this bill. If there are specific technical terms, acronyms, or regulatory concepts central to understanding the bill, briefly define or clarify them within this sentence.

3. **key_concepts_llm**: Extract 5-10 keywords or 2-3 word phrases that capture the main policy areas, specific legal provisions, affected sectors, or regulatory domains addressed by this bill. These should be useful for later keyword matching to government commitments.

4. **sponsoring_department_standardized_llm**: Based on the sponsor's title and name, identify and standardize the primary department responsible for this bill. Use standard Canadian federal department names. Examples: "Department of Finance Canada", "Health Canada", "Transport Canada". If the sponsor is a Senator or private member, return an empty string.

## OUTPUT FORMAT
Return a single JSON object with the following structure:
{{
  "timeline_summary_llm": "...", // Concise, factual summary for the timeline (max 30 words)
  "one_sentence_description_llm": "...", // 30-50 word sentence explaining core idea and key provisions
  "key_concepts_llm": ["...", "..."], // 5-10 keywords/phrases
  "sponsoring_department_standardized_llm": "..." // Standardized department name (or empty if not government bill)
}}

**Do not include any additional commentary or explanation. Only return the JSON object.** 