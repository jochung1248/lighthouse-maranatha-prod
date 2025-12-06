from __future__ import print_function
from google.adk.agents import Agent
import pandas as pd
from google.genai.types import GenerateContentConfig
import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import uuid
from google.adk.agents import Agent
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
import logging
import html




SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl", "https://www.googleapis.com/auth/drive"]



def preview_youtube_playlist(playlist_id: str):
    """
    Fetch a YouTube playlist and return:
      - video titles
      - caption snippet (first available caption)

    Args:
        playlist_id: YouTube playlist ID

    Returns:
        List of dicts: [{'video_id', 'title'}]
    """

    print("🔐 Authenticating YouTube API...")
    creds = None
    # Authenticate if credentials not provided
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('./credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        youtube = build("youtube", "v3", credentials=creds)

        videos = []
        next_page_token = None

        print(f"📂 Fetching playlist items for playlist: {playlist_id}")

        # --- STEP 1: Fetch playlist videos ---
        while True:
            req = youtube.playlistItems().list(
                part="snippet", playlistId=playlist_id, maxResults=50, pageToken=next_page_token
            )
            res = req.execute()

            for item in res.get("items", []):
                video_id = item["snippet"]["resourceId"]["videoId"]
                title = item["snippet"]["title"]
                videos.append({"video_id": video_id, "title": title})

            next_page_token = res.get("nextPageToken")
            if not next_page_token:
                break

        print(f"📺 Found {len(videos)} videos in playlist.")
        return videos

    except HttpError as error:
        logging.error(f"❌ YouTube API error: {error}")
        return None



def find_files_by_name(search_name: str, folder_id: str = '1hiSf6DSAO2RIv7ZCT7ltU8uBYQFvaOQu'):
    """
    Find files in a Google Drive folder that match the input name (supports Korean).
    If multiple matches found, prompts user to select one.
    
    Args:
        search_name: The name to search for (can be in Korean)
        folder_id: Google Drive folder ID to search within
        creds: Google credentials object (if None, will authenticate)
    
    Returns:
        Dictionary with file info {'id': file_id, 'name': file_name, 'content': file_content}, 
        or None if no matches found
    """
    # Authenticate if credentials not provided
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('./credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    drive_service = build('drive', 'v3', credentials=creds)
    try:
        # Build query to search for files in the folder matching the name
        query = f"name contains '{search_name}' and trashed=false"
        
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType)',
            pageSize=10
        ).execute()
        
        items = results.get('files', [])
        print(items)
        
        if not items:
            print(f"❌ No files found matching: '{search_name}'")
            return None
        
        if len(items) == 1:
            file_id = items[0]['id']
            file_name = items[0]['name']
            print(f"\n✅ Single file found matching '{search_name}': {file_name}\n")
            
            # Read file content if it's a text file
            if items[0].get('mimeType') == 'text/plain':
                content = drive_service.files().get_media(fileId=file_id).execute().decode('utf-8')
                return {'id': file_id, 'name': file_name, 'content': content}
            return {'id': file_id, 'name': file_name, 'content': None}
        
        # Multiple matches found - ask user to select
        print(f"\n⚠️ Multiple files found matching '{search_name}':\n")
        for idx, item in enumerate(items, 1):
            print(f"  {idx}. {item['name']}")
            print(f"     📍 ID: {item['id']}\n")
        
        while True:
            try:
                choice = input(f"Please select a file (1-{len(items)}): ").strip()
                choice_idx = int(choice) - 1
                
                if 0 <= choice_idx < len(items):
                    selected_item = items[choice_idx]
                    file_id = selected_item['id']
                    file_name = selected_item['name']
                    print(f"\n✅ Selected: {file_name}\n")
                    
                    # Read file content if it's a text file
                    if selected_item.get('mimeType') == 'text/plain':
                        content = drive_service.files().get_media(fileId=file_id).execute().decode('utf-8')
                        return {'id': file_id, 'name': file_name, 'content': content}
                    return {'id': file_id, 'name': file_name, 'content': None}
                else:
                    print(f"❌ Invalid selection. Please enter a number between 1 and {len(items)}.")
            except ValueError:
                print(f"❌ Invalid input. Please enter a valid number.")
    
    except HttpError as error:
        print(f"❌ An API error occurred: {error}")
        return None


def drive_save_lyrics(lyrics_list: list[dict], folder_id: str = '1hiSf6DSAO2RIv7ZCT7ltU8uBYQFvaOQu'):
    """
    Save each song's lyrics as a separate Google Doc in the given Drive folder.
    Each created doc's name will be "KoreanTitle / EnglishTitle" (falling back to whichever is available).

    Args:
        lyrics_list: list of dicts with keys:
            - 'korean_title' or 'korean'
            - 'english_title' or 'english'
            - 'korean_lyrics' or 'korean'
            - 'english_lyrics' or 'english'
        folder_id: Drive folder ID to place created docs into.

    Returns:
        List of dicts: [{'id': <doc_id>, 'name': <doc_name>}, ...]
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('./credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    drive_service = build('drive', 'v3', credentials=creds)
    docs_service = build('docs', 'v1', credentials=creds)

    created_files = []
    for entry in lyrics_list:
        # normalize fields
        eng_title = entry.get('english_title') or entry.get('english') or ''
        kor_title = entry.get('korean_title') or entry.get('korean') or ''
        eng_lyrics = entry.get('english_lyrics') or entry.get('english') or ''
        kor_lyrics = entry.get('korean_lyrics') or entry.get('korean') or ''

        name_parts = []
        if kor_title:
            name_parts.append(kor_title.strip())
        if eng_title:
            name_parts.append(eng_title.strip())
        doc_name = " / ".join(name_parts) if name_parts else f"lyrics-{uuid.uuid4().hex[:8]}"

        try:
            # Create a Google Doc (blank) in the specified folder
            file_metadata = {
                'name': doc_name,
                'parents': [folder_id] if folder_id else [],
                'mimeType': 'application/vnd.google-apps.document'
            }
            new_file = drive_service.files().create(body=file_metadata, fields='id,name').execute()
            doc_id = new_file.get('id')

            # Build the content to insert
            parts = []
            if eng_title:
                parts.append(f"English Title: {eng_title}\n")
            if eng_lyrics:
                parts.append(f"{eng_lyrics}\n\n")
            if kor_title:
                parts.append(f"Korean Title: {kor_title}\n")
            if kor_lyrics:
                parts.append(f"{kor_lyrics}\n")

            content = "\n".join(parts).strip() or ""

            if content:
                # Insert text at the start of the document
                requests = [
                    {"insertText": {"location": {"index": 1}, "text": content}}
                ]
                docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

            created_files.append({"id": doc_id, "name": new_file.get('name')})
        except Exception as e:
            logging.error(f"Failed to create doc for '{doc_name}': {e}")
            # continue with other entries

    return created_files



lyric_retriever_agent = Agent(
	model='gemini-2.5-pro',
	name='LyricRetrieverAgent',
	description='An agent specialized in retrieving English and Korean lyrics based on provided worship song titles',
	instruction="""
		You are the Lyric Retriever Agent. Your task is to fetch the lyrics for a list of songs provided by the user. 
		
		Follow these steps:
        1. You will be given a URL link to a YouTube playlist containing worship songs.
        2. Use the 'preview_youtube_playlist' tool to extract video titles from the playlist. Get the playlist ID from the URL.
		
		3. Based on the youtube song titles and the song titles provided by the user, attempt to search for an existing lyrics file in the Google Drive lyrics folder in both langauges (do two separate searches for English and Korean):
			- Use the find_files_by_name() function to search for files matching the song title
            - Remove any numbers or special characters from the song title to improve matching
			- If a file is found, read and use those lyrics. You may have to clean up random letters and numbers from the text.
			- If multiple files match, list them to the user and ask which one to select
            - If you have found files, let the user know which files you have found and are using.
		
		4. If a song's lyrics can't be found in the Google Drive, then request the user to send the lyrics for both English and Korean versions.
		
		5. If the user can only send lyrics in one language, translate the missing version yourself ensuring accuracy and maintaining the original meaning.
			Be faithful to the structure of the song. 
		
		6. Match the English and Korean lyrics line by line, ensuring that each line corresponds correctly between the two languages.
            Ensure you are adhering to the song structure (verses, choruses, bridges, etc.) when matching lines. If necessary, make minor adjustments in terms of newlines to maintain alignment.
		
		7. Compile the list into a JSON string containing english and korean lyric pairs for all the songs. Each line should match as the song goes. 
			Each value for each key in the dictionary should be maximum two lines long, separated by a newline character (\n).
            It is imperative that each line in English matches the corresponding line in Korean.
			Important: Return ONLY a valid JSON string (no explanatory text). The JSON must be a list of objects:
			[
				{"english": "line1\nline2", "korean": "라인1\n라인2"},
				{"english": "line3\nline4", "korean": "라인3\n라인4"},
			...
			]
			
			Example english and korean lyric pair:
			[
				{"english": "Amazing grace, how sweet the sound\nThat saved a wretch like me", "korean": "나 같은 죄인 살리신\n주 은혜 놀라워"},
			]
		
		8. Return the compiled lyrics and print them.

        9. For any songs given by the user, save the lyrics files to Google Drive using the 'drive_save_lyrics' tool. 
            The lyrics should be saved 'slide-by-slide' meaning it should be english then korean, then next english then next korean, etc.
		
		PRIORITY: Always check Google Drive files first before asking the user for lyrics.
	""",
	generate_content_config = GenerateContentConfig(
		temperature=0.01,
	),
        tools=[
        find_files_by_name,
        preview_youtube_playlist,
        drive_save_lyrics
    ],
)