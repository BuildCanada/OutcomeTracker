import webvtt
from io import StringIO
import re
import os # Added for path joining

# --- Helper Functions (copied from ingest_yt_campaign_promises.py or simplified) ---

def convert_timestamp_to_seconds(timestamp_str):
    """Converts HH:MM:SS.mmm or HH:MM:SS,mmm to float seconds."""
    if not timestamp_str or not isinstance(timestamp_str, str):
        return 0.0
    timestamp_str = timestamp_str.replace(',', '.')
    parts = timestamp_str.split(':')
    seconds_str = parts[-1]
    try:
        if len(parts) == 3: # HH:MM:SS.mmm
            h, m = int(parts[0]), int(parts[1])
            s_ms = float(seconds_str)
            return h * 3600 + m * 60 + s_ms
        elif len(parts) == 2: # MM:SS.mmm
            m = int(parts[0])
            s_ms = float(seconds_str)
            return m * 60 + s_ms
        elif len(parts) == 1: # SS.mmm
            return float(seconds_str)
        else:
            print(f"WARNING: Unexpected timestamp format: {timestamp_str}")
            return 0.0
    except ValueError as e:
        print(f"ERROR: ValueError converting timestamp '{timestamp_str}': {e}")
        return 0.0

def _parse_vtt_file_direct(file_path, video_id="test_video"):
    """Parses VTT file using webvtt-py and normalize cues."""
    normalized_cues = []
    html_tag_pattern = re.compile(r'<[^>]+>')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        captions = webvtt.read_buffer(StringIO(content))
        for caption in captions:
            cleaned_text = html_tag_pattern.sub('', caption.text).strip()
            cleaned_text = " ".join(cleaned_text.split())
            
            if cleaned_text:
                normalized_cues.append({
                    'start': convert_timestamp_to_seconds(caption.start),
                    'end': convert_timestamp_to_seconds(caption.end),
                    'text': cleaned_text
                })
        
        if normalized_cues:
            print(f"Successfully parsed and normalized cues from {file_path}")
            return normalized_cues
        else:
            print(f"webvtt-py parsed file {file_path} but yielded no valid cues.")
            return None
             
    except webvtt.errors.MalformedCaptionError as e_parse:
        print(f"webvtt-py MalformedCaptionError parsing file {file_path}: {e_parse}")
    except Exception as e:
        print(f"Error parsing/normalizing file {file_path}: {e}")
    return None

def deduplicate_cues_test(raw_cues):
    """Deduplicates cues based on case-insensitive comparison of consecutive text content,
       prioritizing longer cues when one contains the other as a substring.
    """
    if not raw_cues:
        return []

    cleaned_cues = []
    # Filter out non-dict or cues without text first
    process_list = [cue for cue in raw_cues if isinstance(cue, dict) and cue.get('text', '').strip()]
    
    if not process_list: 
        return []

    # Add the first valid cue
    cleaned_cues.append(process_list[0])

    for i in range(1, len(process_list)):
        current_cue = process_list[i]
        last_added_cue = cleaned_cues[-1]

        current_text_lower = current_cue['text'].strip().lower()
        last_added_text_lower = last_added_cue['text'].strip().lower()

        # 1. Identical text? Skip current.
        if current_text_lower == last_added_text_lower:
            # print(f"Skipping identical: '{current_text_lower[:50]}...'")
            continue

        # 2. Last text is substring of current? Replace last with current.
        if last_added_text_lower in current_text_lower:
            # print(f"Replacing '{last_added_text_lower[:50]}...' with '{current_text_lower[:50]}...'")
            cleaned_cues[-1] = current_cue
            continue

        # 3. Current text is substring of last? Skip current.
        if current_text_lower in last_added_text_lower:
            # print(f"Skipping substring: '{current_text_lower[:50]}...' (already covered by '{last_added_text_lower[:50]}...')")
            continue
        
        # 4. Different enough? Add current.
        # print(f"Adding different: '{current_text_lower[:50]}...'")
        cleaned_cues.append(current_cue)
            
    return cleaned_cues

# --- Main Test Logic ---
if __name__ == "__main__":
    # Construct the path relative to the script\'s location
    script_dir = os.path.dirname(__file__)
    test_file_path = os.path.join(script_dir, "temp_subtitles_tnFlpGzDfbI", "att2_tnFlpGzDfbI.en.en-orig.vtt") 
    output_file_path = os.path.join(script_dir, "test_output.md") # Define output file path

    print(f"Attempting to read VTT file: {test_file_path}")

    if not os.path.exists(test_file_path):
        print(f"ERROR: Test file not found at {test_file_path}")
        exit()

    raw_cues = _parse_vtt_file_direct(test_file_path)

    if raw_cues:
        print(f"\n--- Raw Cues (first 5 of {len(raw_cues)}) ---")
        for i, cue in enumerate(raw_cues[:5]):
            print(f"{i}: Start: {cue['start']:.3f}, End: {cue['end']:.3f}, Text: '{cue['text'][:100]}'")

        print(f"\n--- Deduplicating Cues ---")
        deduplicated_cues = deduplicate_cues_test(raw_cues)
        
        print(f"\n--- Deduplicated Cues (first 10 of {len(deduplicated_cues)}) ---")
        for i, cue in enumerate(deduplicated_cues[:10]):
            print(f"{i}: Start: {cue['start']:.3f}, End: {cue['end']:.3f}, Text: '{cue['text'][:100]}'")

        print(f"\n--- Statistics ---")
        print(f"Number of raw cues: {len(raw_cues)}")
        print(f"Number of deduplicated cues: {len(deduplicated_cues)}")

        transcript_text_generated = "\n".join([cue.get('text', '').strip() for cue in deduplicated_cues if cue.get('text', '').strip()])
        print(f"\n--- Generated Text (first 500 chars) ---")
        print(transcript_text_generated[:500])
        
        print(f"\n--- Full Generated Text from Deduplicated Cues ---")
        # print(transcript_text_generated) # Potentially very long
        
        # Let's look at the example you provided:
        # "Hello everyone, welcome to this"
        # "Hello everyone, welcome to this"
        # "Hello everyone, welcome to this press conference. The"
        # "press conference. The"
        # "press conference. The Premier of Quebec is accompanied by the"
        
        print("\n--- Checking specific duplications ---")
        texts_only = [cue['text'] for cue in deduplicated_cues]
        
        problematic_sequence = [
            "Hello everyone, welcome to this",
            "Hello everyone, welcome to this press conference. The",
            "press conference. The",
            "press conference. The Premier of Quebec is accompanied by the"
        ]
        
        count_exact_matches = {}
        for ps in problematic_sequence:
            count_exact_matches[ps] = texts_only.count(ps)
            
        print("Counts of specific problematic sequences in deduplicated text:")
        for text, count in count_exact_matches.items():
            print(f"'{text}': {count} occurrences")

        # --- Write Cues to Output File ---
        print(f"\nWriting raw and deduplicated cues to: {output_file_path}")
        try:
            with open(output_file_path, 'w', encoding='utf-8') as outfile:
                outfile.write(f"# WebVTT Deduplication Test Output\n\n")
                outfile.write(f"Source File: `{os.path.basename(test_file_path)}`\n\n")
                
                outfile.write(f"## Raw Cues ({len(raw_cues)})\n\n")
                for i, cue in enumerate(raw_cues):
                    outfile.write(f"{i+1}. **[{cue['start']:.3f} - {cue['end']:.3f}]**: {cue['text']}\n")
                
                outfile.write(f"\n\n## Deduplicated Cues ({len(deduplicated_cues)})\n\n")
                for i, cue in enumerate(deduplicated_cues):
                     outfile.write(f"{i+1}. **[{cue['start']:.3f} - {cue['end']:.3f}]**: {cue['text']}\n")

                outfile.write(f"\n\n## Generated Transcript Text\n\n")
                outfile.write("```text\n")
                outfile.write(transcript_text_generated)
                outfile.write("\n```\n")

            print(f"Successfully wrote cues and transcript to {output_file_path}")
        except Exception as e:
            print(f"ERROR: Failed to write output file: {e}")

    else:
        print("No raw cues were parsed.")

    print("\nTest script finished.") 