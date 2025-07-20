# Gemini Prompt for News Evidence Extraction

## Intended Use

You are assisting in building a structured, fact-based timeline of Canadian federal government actions for the purpose of tracking progress against specific government commitments. Your output will be used to help determine whether a news item represents a significant, verifiable step toward fulfilling a government promise. Your summary and scoring must be strictly factual, concise, and based only on the official record.

## CONTEXT

You are analyzing a Canadian federal government news release. Your goal is to:

- Create a concise, factual summary suitable for a timeline tracking government actions against promises made by the government.
- Determine if this news item is significant enough to warrant further linking to specific government commitments.
- Ensure all outputs are strictly based on the news item's official text and publication date; do not speculate or infer beyond the provided data.

## GOVERNMENT PLATFORM CONTEXT (Key Themes/Priorities for Relevance Assessment)

To assess the relevance of the news item, consider its alignment with the following key themes and priorities derived from the government's platform documents:

**From 2025 Liberal Platform "Canada Strong" (REPLACE with actual key themes/chapters):**

- **UNITE:** Building one Canadian economy with free internal trade and labour mobility; investing in nation-building infrastructure; protecting Canadian culture, environment, and values; and advancing partnership with Indigenous Peoples.
- **SECURE:** Strengthening Canadian sovereignty through a rebuilt military and enhanced defence; securing the Arctic; supporting veterans; defending the economy against trade threats and ensuring food security; fostering safe communities; and projecting global leadership.
- **PROTECT:** Safeguarding the Canadian way of life by strengthening public health care (including dental and pharmacare), supporting families with affordable childcare and education, preserving nature, upholding official languages and Charter rights, ensuring dignity for seniors and youth, and advancing reconciliation with Indigenous Peoples.
- **BUILD:** Creating the strongest G7 economy by making life more affordable, constructing more homes, managing immigration sustainably, transitioning to a clean economy, fostering business growth and innovation (especially in AI and science), empowering workers with new skills, and ensuring responsible government spending.

## NEWS ITEM DATA (to be filled in):

- Title: "{news_title}"
- Summary/Snippet: "{news_summary_snippet}" # Brief summary from RSS feed
- Full Article Text: "{full_text}" # Complete article content extracted from the news page
- Publication Date: {publication_date} # This is the evidence_date, do not repeat in timeline_summary
- Assigned Parliamentary Session: "{parliament_session_id}"

## INSTRUCTIONS

Analyze the FULL ARTICLE TEXT primarily, using the title and summary as supporting context. Base your analysis on the complete content, not just the headline or summary.

1.  **timeline_summary**: Generate a concise (max 30 words), strictly factual summary of the news item based on the full article content, suitable for a timeline entry. Use active voice. **Do not include the publication date in this summary.** Example: "Government announces funding for new infrastructure project." Avoid opinions or speculation.
2.  **potential_relevance_score**: Assign a score ("High", "Medium", or "Low") indicating whether this news item represents a tangible action, policy change, funding announcement, or legislative step **in relation to the GOVERNMENT PLATFORM CONTEXT provided above.** Use "High" only for news that clearly and directly fulfills or advances one or more of these stated platform themes/priorities. Use "Low" if the announcement has little or not impact on the platform priorities. Base this assessment on the full article content, not just the headline.
3.  **key_concepts**: Extract up to 10 keywords or 2-3 word phrases that capture the main topics, policy areas, specific initiatives or affected entities from the FULL ARTICLE TEXT. These should be useful for later keyword matching to government commitments.
4.  **sponsoring_department_standardized**: (If identifiable from the news content or context) Identify the primary department responsible for the announcement or initiative, using a standardized department name if possible. Look throughout the full article text for department mentions. If not clear, return an empty string or null.
5.  **one_sentence_description**: Generate a single sentence (30-50 words) that explains the core idea or messages of this news item based on the full article content. If there are key terms, acronyms, or specific concepts central to understanding the announcement, briefly define or clarify them within this sentence.

## OUTPUT FORMAT

Return a single JSON object with the following structure:
{{
  "timeline_summary": "...", // Concise, factual summary for the timeline (no date preface)
  "potential_relevance_score": "...", // One of: High, Medium, Low (based on platform context)
  "key_concepts": ["...", "..."], // Up to 10 keywords/phrases
  "sponsoring_department_standardized": "..." // Standardized department name (or empty/null)
  "one_sentence_description": "..." // 30-50 word sentence explaining core idea and key terms
}}

**Do not include any additional commentary or explanation. Only return the JSON object.**
