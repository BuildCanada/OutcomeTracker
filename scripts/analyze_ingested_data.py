import firebase_admin
from firebase_admin import credentials, firestore
import os
import json # For pretty printing dicts
from collections import Counter
from dotenv import load_dotenv # Import load_dotenv

load_dotenv() # Load environment variables from .env file

# --- Firebase Configuration ---
if not firebase_admin._apps:
    if os.getenv('FIRESTORE_EMULATOR_HOST'):
        options = {'projectId': 'promisetrackerapp'} # Use your desired project ID for the emulator
        firebase_admin.initialize_app(options=options)
        print(f"Analysis Script: Connected to Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')} using project ID '{options['projectId']}'")
    else:
        # TODO: Add configuration for connecting to a live Firestore instance if needed
        print("ERROR: FIRESTORE_EMULATOR_HOST environment variable not set (and not found in .env).")
        print("Please set it or ensure .env file is present and configured (e.g., 'localhost:8080').")
        exit("Exiting Analysis Script: Firestore not configured.")
      
db = firestore.client()
# --- End Firebase Configuration ---

def analyze_data():
    """Fetches data from Firestore and prints summary statistics."""
    videos_ref = db.collection('youtube_video_data')
    docs = videos_ref.stream() # streams all documents

    all_videos_data = []
    for doc in docs:
        all_videos_data.append(doc.to_dict())

    if not all_videos_data:
        print("No data found in 'youtube_video_data' collection.")
        return

    total_videos = len(all_videos_data)
    print(f"\n--- Data Quality Analysis for 'youtube_video_data' ---")
    print(f"Total videos processed: {total_videos}")

    # Transcript Presence
    videos_with_transcript_text = 0
    videos_with_transcript_cues = 0
    for video in all_videos_data:
        if video.get('transcript_text_original') and video['transcript_text_original'].strip():
            videos_with_transcript_text += 1
        if video.get('transcript_cues_original') and isinstance(video['transcript_cues_original'], list) and len(video['transcript_cues_original']) > 0:
            videos_with_transcript_cues +=1
            
    print(f"Videos with non-empty 'transcript_text_original': {videos_with_transcript_text} ({videos_with_transcript_text/total_videos:.2%})")
    print(f"Videos with non-empty 'transcript_cues_original': {videos_with_transcript_cues} ({videos_with_transcript_cues/total_videos:.2%})")

    # Transcript Language
    lang_counts = Counter()
    for video in all_videos_data:
        lang = video.get('transcript_language_original', 'not_set')
        lang_counts[lang] += 1
    
    print("\nTranscript Language Distribution ('transcript_language_original'):")
    for lang, count in lang_counts.items():
        print(f"  - {lang}: {count} ({count/total_videos:.2%})")

    # Needs Translation flag
    needs_translation_count = 0
    for video in all_videos_data:
        if video.get('needs_translation') is True:
            needs_translation_count += 1
    print(f"\nVideos flagged with 'needs_translation': {needs_translation_count} ({needs_translation_count/total_videos:.2%})")

    # Metadata Presence (Title, Description)
    with_title = 0
    with_description = 0
    for video in all_videos_data:
        if video.get('title') and video['title'].strip():
            with_title += 1
        if video.get('description') and video['description'].strip():
            with_description += 1
    print("\nMetadata Presence:")
    print(f"  - Videos with non-empty title: {with_title} ({with_title/total_videos:.2%})")
    print(f"  - Videos with non-empty description: {with_description} ({with_description/total_videos:.2%})")

    # Video Duration Stats (assuming 'duration' is stored as a number in seconds)
    durations = []
    for video in all_videos_data:
        duration = video.get('duration')
        if isinstance(duration, (int, float)):
            durations.append(duration)
    
    if durations:
        print("\nVideo Duration (in seconds, where available and numeric):")
        print(f"  - Videos with numeric duration: {len(durations)}")
        print(f"  - Average duration: {sum(durations)/len(durations):.2f}s")
        print(f"  - Min duration: {min(durations):.2f}s")
        print(f"  - Max duration: {max(durations):.2f}s")
    else:
        print("\nVideo Duration: No numeric 'duration' field found in processed videos.")

    # Uploader/Channel diversity (optional, can be verbose)
    # uploader_ids = Counter()
    # channel_ids = Counter()
    # for video in all_videos_data:
    #     if video.get('uploader_id'): uploader_ids[video['uploader_id']] +=1
    #     if video.get('channel_id'): channel_ids[video['channel_id']] +=1
    # print(f"\nUnique uploader_id count: {len(uploader_ids)}")
    # print(f"Unique channel_id count: {len(channel_ids)}")
    # print("Top 5 uploader_ids:", uploader_ids.most_common(5))
    # print("Top 5 channel_ids:", channel_ids.most_common(5))

    print("\n--- End of Analysis ---")

if __name__ == "__main__":
    analyze_data() 