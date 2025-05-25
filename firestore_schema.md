# Firestore Data Schema

This document outlines the structure of the collections used in the Firestore database for the Build Canada Promise Tracker.

## `promises` Collection

Stores individual commitments made by political parties or the government.

**Document ID:** Unique `promise_id` (String, e.g., MLC ID for mandate letters, UUID for others).

**Fields:**

*   `promise_id`: (String) - Unique identifier for the promise. Matches document ID.
*   `text`: (String) - The core text of the promise or commitment.
*   `key_points`: (Array of Strings) - Concise bullet points summarizing the promise (potentially LLM-generated).
*   `source_document_url`: (String, Nullable) - URL to the original source document (e.g., Mandate Letter page, YouTube video).
*   `source_type`: (String) - e.g., "Mandate Letter Commitment (Structured)", "Video Transcript (YouTube)", "Party Platform (PDF)".
*   `date_issued`: (String, Nullable) - Date the promise was made or the source document was published (e.g., "YYYY-MM-DD" or "YYYYMMDD").
*   `candidate_or_government`: (String, Nullable) - The entity making the promise (e.g., "Justin Trudeau", "Government of Canada (2021 Mandate)", "Conservative Party of Canada").
*   `party`: (String, Nullable) - Political party associated with the promise (e.g., "Liberal Party of Canada", "Conservative Party of Canada").
*   `category`: (String, Nullable) - Primary policy category (e.g., "Economy", "Healthcare", "Environment"). See `common_utils.py` for list.
*   `responsible_department_lead`: (String, Nullable) - Standardized full name of the primary responsible government department (e.g., "Finance Canada").
*   `relevant_departments`: (Array of Strings, Nullable) - List of standardized full names of other relevant departments.
*   `commitment_history_rationale`: (String, Nullable) - LLM-generated summary of the context/rationale behind the promise.
*   `linked_evidence_ids`: (Array of Strings, Default: `[]`) - Stores `evidence_id`s from the `evidence_items` collection.
*   `bc_promise_rank`: (String, Nullable) - Build Canada priority rank: 'strong', 'medium', 'weak'.
*   `bc_promise_direction`: (String, Nullable) - Alignment with Build Canada tenets: 'positive', 'negative'.
*   `bc_promise_rank_rationale`: (String, Nullable) - 15-25 word rationale for the rank and direction.

    *Metadata & Source Specific Fields:*
*   `mlc_raw_reporting_lead`: (String, Nullable) - Raw reporting lead string from MLC source.
*   `mlc_raw_all_ministers`: (String, Nullable) - Raw all ministers string from MLC source.
*   `video_source_id`: (String, Nullable) - YouTube video ID if source is video.
*   `video_timestamp_cue_raw`: (String, Nullable) - Raw text cue from LLM identifying promise location in video transcript.
*   `video_source_title`: (String, Nullable) - Title of the source YouTube video.
*   `video_upload_date`: (String, Nullable) - Original upload date string (YYYYMMDD) from YouTube metadata.
*   `ingested_at`: (Timestamp) - Firestore server timestamp when the record was first created.
*   `last_updated_at`: (Timestamp) - Firestore server timestamp when the record was last modified.

## `evidence_items` Collection

Stores specific, dated pieces of evidence related to government actions on promises.

**Document ID:** Unique `evidence_id` (String, e.g., UUID).

**Fields:**

*   `evidence_id`: (String) - Unique identifier. Matches document ID.
*   `promise_ids`: (Array of Strings) - Links to `promise_id`s in the `promises` collection that this evidence relates to.
*   `evidence_source_type`: (String) - Type of evidence (e.g., "Bill (LEGISinfo)", "OrderInCouncil", "News Release", "Government Report", "Budget Document", "Hansard Record").
*   `evidence_date`: (String) - Date the evidence item occurred or was published ("YYYY-MM-DD").
*   `title`: (String) - Title of the evidence item (e.g., Bill title, News Release headline).
*   `summary`: (String, Nullable) - Brief description or key takeaway from the evidence.
*   `url`: (String, Nullable) - Link to the source of the evidence.
*   `source_document_key`: (String, Nullable) - Identifier for the source if applicable (e.g., Bill number C-19, OIC number 2023-1234).
*   `mentions_ministers`: (Array of Strings, Nullable) - Ministers mentioned in the evidence text.
*   `mentions_departments`: (Array of Strings, Nullable) - Departments mentioned (standardized names).
*   `raw_text_snippet`: (String, Nullable) - Relevant excerpt from the source document.
*   `ingested_at`: (Timestamp) - Firestore server timestamp.

## `youtube_video_data` Collection

Stores metadata and transcript information fetched from YouTube videos before promise extraction.

**Document ID:** YouTube Video ID (String).

**Fields:**

*   `video_id`: (String) - YouTube video ID.
*   `title`: (String)
*   `description`: (String)
*   `upload_date`: (String) - YYYYMMDD format.
*   `uploader`: (String)
*   `uploader_id`: (String)
*   `channel_id`: (String)
*   `channel_url`: (String)
*   `duration`: (Number) - Seconds.
*   `duration_string`: (String)
*   `view_count`: (Number)
*   `like_count`: (Number)
*   `comment_count`: (Number)
*   `tags`: (Array of Strings)
*   `categories`: (Array of Strings)
*   `thumbnail_url`: (String)
*   `webpage_url`: (String)
*   `original_url`: (String)
*   `transcript_cues_cleaned`: (Array of Maps) - List of {start: float, end: float, text: string}.
*   `transcript_text_generated`: (String) - Full transcript text compiled from cleaned cues.
*   `transcript_language_original`: (String) - 'en', 'fr', or null/unknown.
*   `transcript_en_translated`: (String, Nullable) - English translation if original was French.
*   `needs_translation`: (Boolean) - True if original transcript was French.
*   `translation_processed_at`: (Timestamp, Nullable) - When translation was attempted/completed.
*   `raw_yt_dlp_json_snippet`: (String) - Snippet of the raw JSON from yt-dlp.
*   `ingested_at`: (Timestamp) - When this record was created.
*   `llm_promise_extraction_processed_at`: (Timestamp, Nullable) - When promise extraction was attempted/completed.
*   `promise_extraction_status`: (String, Nullable) - e.g., "success", "skipped_no_transcript", "error_llm_api", "error_llm_json_decode", "error_batch_commit".
*   `extracted_promise_count`: (Number, Nullable) - How many promises were extracted from this video.

## `mandate_letters_fulltext` Collection

Stores the full text and associated metadata scraped from ministerial mandate letters.

**Document ID:** Standardized department name slug (String, e.g., `finance-canada`).

**Fields:**

*   `minister_first_name`: (String, Nullable).
*   `minister_last_name`: (String, Nullable).
*   `minister_full_name_input`: (String, Nullable) - Name as provided in the source list.
*   `minister_title_input`: (String, Nullable) - Title/Department as provided in the source list.
*   `minister_title_scraped_pm_gc_ca`: (String, Nullable) - Title scraped directly from pm.gc.ca page.
*   `standardized_department_or_title`: (String) - The standardized department name used for linking.
*   `letter_url`: (String) - URL of the mandate letter page.
*   `full_text`: (String) - Extracted full text of the letter.
*   `date_scraped`: (Timestamp) - When the letter was scraped.
*   `minister_greeting_lastname_pm_gc_ca`: (String, Nullable) - Last name extracted from the "Dear Minister X:" greeting.

## Collection: `raw_news_releases`

**Purpose:** Stores raw data fetched from Canada News Centre RSS feeds.

**Document ID:** Unique ID (e.g., derived from a hash of the `source_url` and `publication_date`, or a UUID).

| Field Name                     | Type             | Description                                                                                                   | Example                                            | Notes                                                                                                      |
| ------------------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `raw_item_id`                  | String           | Unique ID for the raw item, same as Document ID.                                                              | `abc123xyz789`                                     |                                                                                                            |
| `source_url`                   | String           | URL of the news release.                                                                                      | `https://www.canada.ca/en/news/archive/2023/01/example.html` | Primary key for idempotency (along with publication_date).                                                 |
| `publication_date`             | Timestamp/String | Publication date of the news release.                                                                         | `2023-01-15T10:00:00Z` or Firestore Timestamp      | Store as ISO string if Timestamp is problematic from RSS.                                                  |
| `title_raw`                    | String           | Title from the RSS feed.                                                                                      | "Government Announces New Funding"                 |                                                                                                            |
| `summary_or_snippet_raw`       | String           | Summary or description from the RSS feed.                                                                     | "Details about the new funding initiative..."      |                                                                                                            |
| `full_text_scraped`            | String (nullable)| Placeholder for full text if scraped later.                                                                   | "Full text of the article..."                      | Optional.                                                                                                  |
| `rss_feed_source`              | String (nullable)| URL of the specific RSS feed it came from.                                                                    | `https://www.canada.ca/en/news/rss/national.xml`   |                                                                                                            |
| `categories_rss`               | Array of Strings (nullable) | Categories from RSS if provided.                                                                           | `["Health", "Economy"]`                            |                                                                                                            |
| `department_rss`               | String (nullable)| Department mentioned in RSS if provided.                                                                      | "Health Canada"                                    |                                                                                                            |
| `ingested_at`                  | Timestamp        | Timestamp when the item was ingested into this collection.                                                    | `firestore.SERVER_TIMESTAMP`                       |                                                                                                            |
| `evidence_processing_status`   | String           | Status of processing for this raw item.                                                                       | "pending_evidence_creation"                        | Values: "pending_evidence_creation", "evidence_created", "skipped_irrelevant_low_score", "error_processing". |
| `related_evidence_item_id`     | String (nullable)| ID of the document created in `evidence_items` if processed.                                                  | `evd_zyx987cba321`                                 |                                                                                                            |
| `parliament_session_id_assigned` | String (nullable)| The parliamentary session this news item is likely associated with, based on its publication date.           | `45-1`                                             | Determined by comparing `publication_date` with `sessions_config`.                                         |

## Collection: `raw_orders_in_council`

Stores raw data scraped/fetched for individual Orders in Council (OICs) from the Privy Council Office (PCO) database.

-   **Document ID**: Normalized OIC Number (e.g., "2025-0497")

| Field Name                        | Type      | Description                                                                                                |
| :-------------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------- |
| `raw_oic_id`                      | String    | Same as Document ID (normalized OIC Number).                                                               |
| `attach_id`                       | Integer   | The numerical ID from the `attachment.php?attach=[ATTACH_ID]` URL used to fetch this OIC.                  |
| `oic_number_full_raw`             | String    | The "PC Number" as displayed on the page (e.g., "P.C. 2025-0497").                                         |
| `oic_date`                        | Timestamp | Date the OIC was made/registered (parsed from page, stored as timezone-aware UTC).                       |
| `title_or_summary_raw`            | String    | The title or summary text from the OIC page.                                                               |
| `responsible_department_raw`    | String    | (Nullable) Department listed on the OIC page, if available.                                                |
| `responsible_minister_raw`      | String    | (Nullable) Minister listed on the OIC page, if available.                                                  |
| `act_citation_raw`                | String    | (Nullable) Any cited Act(s) mentioned on the OIC page.                                                     |
| `source_url_oic_detail_page`      | String    | Direct URL used to fetch this specific OIC (e.g., `https://orders-in-council.canada.ca/attachment.php?attach=XXXXX&lang=en`). |
| `full_text_scraped`               | String    | (Nullable) The full text of the OIC as scraped from the page.                                              |
| `ingested_at`                     | Timestamp | Firestore server timestamp when this raw record is created.                                                  |
| `evidence_processing_status`      | String    | Default: "pending_evidence_creation". Others: "evidence_created", "skipped_low_relevance_score", "error_llm_processing", "error_missing_fields", "error_processing_script". |
| `related_evidence_item_id`        | String    | (Nullable) ID of the corresponding document in `evidence_items` if successfully processed.                 |
| `parliament_session_id_assigned`  | String    | (Nullable) Determined by `get_parliament_session_id` using `oic_date`.                                     |
| `processed_at`                    | Timestamp | (Nullable) Firestore server timestamp when the item was last processed (successfully or with error).       |
| `llm_model_name_last_attempt`     | String    | (Nullable) Name of the LLM model used in the last processing attempt.                                      |
| `processing_error_message`        | String    | (Nullable) Stores the error message if `evidence_processing_status` is an error state.                     |

## Collection: `evidence_items`

**Purpose:** Stores structured evidence linked to promises.

**Document ID:** Unique `evidence_id`.

| Field Name                  | Type                | Description                                                                                                | Example                                      | Notes                                                                                                                                       |
| --------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `evidence_id`               | String              | Unique identifier for the evidence item.                                                                   | `evd_abc123xyz789`                           |                                                                                                                                             |
| `promise_ids`               | Array of Strings    | List of `promise_id`s this evidence is linked to.                                                          | `["prm_001", "prm_002"]`                     | Can be empty if not yet linked.                                                                                                             |
| `evidence_source_type`      | String              | Type of evidence source.                                                                                   | "News Release (Canada.ca)", "Legislation"    | E.g., "Campaign Document", "Mandate Letter", "News Release", "Legislation", "Order in Council", "Gazette Notice", "Ministerial Speech", "Audit Report", "Media Report", "Hansard". |
| `evidence_date`             | Timestamp           | Date the evidence occurred or was published.                                                               | `2023-01-15T00:00:00Z`                       |                                                                                                                                             |
| `title_or_summary`          | String              | Concise title or summary of the evidence.                                                                  | "Government announces $XM for infrastructure" | For news releases, this will be the LLM-generated `timeline_summary`.                                                                        |
| `description_or_details`    | String (nullable)   | More detailed description or key excerpts.                                                                 | "The funding will support projects in..."    | For news releases, this could be `summary_or_snippet_raw`.                                                                                   |
| `source_url`                | String (nullable)   | URL to the source of the evidence.                                                                         | `https://www.canada.ca/en/news/article.html` |                                                                                                                                             |
| `source_document_ref`       | String (nullable)   | Reference to a document in `source_documents` if applicable.                                               | `sd_xyz789abc123`                            |                                                                                                                                             |
| `linked_departments`        | Array of Strings (nullable) | Departments associated with this evidence.                                                               | `["Innovation, Science and Economic Development Canada"]` | Standardized department names.                                                                                                              |
| `parliament_session_id`     | String              | Parliamentary session this evidence belongs to.                                                            | `45-1`                                       |                                                                                                                                             |
| `ingested_at`               | Timestamp           | Timestamp when this item was ingested/created.                                                             | `firestore.SERVER_TIMESTAMP`                 |                                                                                                                                             |
| `last_updated_at`           | Timestamp           | Timestamp of the last update to this item.                                                                 | `firestore.SERVER_TIMESTAMP`                 |                                                                                                                                             |
| `additional_metadata`       | Map (nullable)      | Any other relevant metadata.                                                                               | `{"bill_number": "C-10", "vote_result": "passed"}` | For news releases: `{ 'raw_news_release_id': '...', 'llm_key_concepts': ['...'] }`                                                              |
| `tags_keywords`             | Array of Strings (nullable) | Keywords or tags for searching/filtering.                                                                | `["funding", "infrastructure", " غربي"]`     |                                                                                                                                             |
| `verification_status`       | String (nullable)   | Status of verification (e.g., "verified", "needs_review").                                                 | "verified"                                   |                                                                                                                                             |
| `analyst_notes`             | String (nullable)   | Notes from analysts during review or linking.                                                              | "This seems to fulfill part of X promise."   |                                                                                                                                             |
| `promise_linking_status`        | String (nullable)   | Developer status for automated linking processes.                                                          | "pending_linking", "linked", "error"       | For news releases, set to "pending" initially.                                                                                              |
| `similarity_hash`           | String (nullable)   | Hash of key fields to detect near-duplicates if needed.                                                    | `hash_value`                                 |                                                                                                                                             | 