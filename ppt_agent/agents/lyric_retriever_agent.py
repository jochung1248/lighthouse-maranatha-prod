from google.adk.agents import Agent
import pandas as pd
from google.genai.types import GenerateContentConfig
from __future__ import print_function
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

SCOPES = ['https://www.googleapis.com/auth/drive.file']


def find_files_by_name(search_name: str, folder_id: str = '1hiSf6DSAO2RIv7ZCT7ltU8uBYQFvaOQu', creds = None) -> Optional[dict]:
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
    if creds is None:
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
        
        if not items:
            print(f"❌ No files found matching: '{search_name}'")
            return None
        
        if len(items) == 1:
            file_id = items[0]['id']
            file_name = items[0]['name']
            print(f"✅ Found file: {file_name}")
            
            # Read file content if it's a text file
            if items[0].get('mimeType') == 'text/plain':
                content = drive_service.files().get_media(fileId=file_id).execute().decode('utf-8')
                return {'id': file_id, 'name': file_name, 'content': content}
            return {'id': file_id, 'name': file_name, 'content': None}
        
        # Multiple matches found - ask user to select
        print(f"\n📁 Found {len(items)} file(s) matching '{search_name}':\n")
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


def search_files_with_regex(pattern: str, folder_id: str = None, creds = None) -> List[dict]:
    """
    Find files in Google Drive matching a regex pattern on filenames.
    
    Args:
        pattern: Regex pattern to match against filenames
        folder_id: Google Drive folder ID to search within
        creds: Google credentials object (if None, will authenticate)
    
    Returns:
        List of dictionaries with file info {'id': file_id, 'name': file_name}
    """
    if creds is None:
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
        regex = re.compile(pattern)
    except re.error as e:
        print(f"❌ Invalid regex pattern: {e}")
        return []
    
    try:
        # Get all files in the folder
        query = "trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=100
        ).execute()
        
        items = results.get('files', [])
        matches = []
        
        # Filter by regex pattern
        for item in items:
            if regex.search(item['name']):
                matches.append({'id': item['id'], 'name': item['name']})
        
        return matches
    
    except HttpError as error:
        print(f"❌ An API error occurred: {error}")
        return []



lyric_retriever_agent = Agent(
	model='gemini-2.5-pro',
	name='LyricRetrieverAgent',
	description='An agent specialized in retrieving English and Korean lyrics based on provided worship song titles',
	instruction="""
		You are the Lyric Retriever Agent. Your task is to fetch the lyrics for a list of songs provided by the user. 
		
		Follow these steps:
		1. Receive a list of worship song titles - sometimes the artist as well - from the user. These will mostly be in Korean.
		2. You will also receive the Google Drive folder ID where lyrics files are stored.
		
		3. For EACH song title, FIRST attempt to search for an existing lyrics file in the Google Drive lyrics folder:
			- Use the find_files_by_name() function with the provided folder_id to search for files matching the song title/artist name (Korean names fully supported)
			- If a file is found, read and use those lyrics directly
			- If multiple files match, the user will select which one to use
			- ONLY proceed to step 4 if no file is found in Google Drive
		
		4. If no file exists in Google Drive for a song, get both the official English and Korean titles for that song from the web.
		
		5. For each song title (and artist, if provided) WITHOUT a Google Drive file, search the web for the complete and accurate English lyrics. Do not verbose or hallucinate. 
			If you cannot find the English version of the lyrics, indicate that you are unable to retrieve them.
		
		6. For each song title (and artist, if provided) WITHOUT a Google Drive file, search the web for the complete and accurate Korean lyrics. Do not verbose or hallucinate. 
			If you cannot find the Korean version of the lyrics, indicate that you are unable to retrieve them.
		
		7. Break each version of the song lyrics down into verses, choruses, and bridges as appropriate.
		
		8. If both the English and Korean versions exist, skip this step. 
			If either version of the lyrics is missing, translate the missing version yourself, ensuring accuracy and maintaining the original meaning.
			Be faithful to the structure of the song. 
		
		9. Match the English and Korean lyrics line by line, ensuring that each line corresponds correctly between the two languages.
		
		10. Compile the list into a JSON string containing english and korean lyric pairs for all the songs. Each line should match as the song goes. 
			Each value for each key in the dictionary should be maximum two lines long, separated by a newline character (\n).
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
		
		11. Return the compiled lyrics and print them.
		
		PRIORITY: Always check Google Drive files first before searching the web. This saves time and ensures consistency.
	""",
	generate_content_config = GenerateContentConfig(
		temperature=0.1,
	),
        tools=[
        find_files_by_name,
    ],
)