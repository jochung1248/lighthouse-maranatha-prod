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
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io
from typing import List, Dict, Optional, Any




# Scopes: Drive, Docs, YouTube (as you used before)
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

TOKEN_FILE = "./ppt_agent/token.json"
CREDENTIALS_FILE = "./ppt_agent/credentials.json"


def get_credentials(scopes=SCOPES) -> Credentials:
    """
    Obtain OAuth2 credentials, refreshing or running a local flow if needed.
    Returns valid Credentials instance.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"OAuth credentials file not found: {CREDENTIALS_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, scopes)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())
    return creds


def normalize(text: str) -> str:
    """
    Normalize a search string: remove excessive punctuation while keeping Korean/English/nums and spaces.
    """
    if not text:
        return ""
    # Keep Hangul, basic Latin, digits and spaces. Replace other characters with space.
    cleaned = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", text)
    # collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def preview_youtube_playlist(playlist_id: str):
    """
    Fetch a YouTube playlist and return list of {'video_id', 'title'}.
    """
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    videos: List[Dict[str, str]] = []
    next_page_token = None

    try:
        while True:
            req = youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            res = req.execute()
            for item in res.get("items", []):
                vid = item["snippet"]["resourceId"].get("videoId")
                title = item["snippet"].get("title", "")
                videos.append({"video_id": vid, "title": title})
            next_page_token = res.get("nextPageToken")
            if not next_page_token:
                break
        return videos
    except HttpError as e:
        logging.error(f"YouTube API error: {e}")
        return None


def read_google_doc(docs_service, document_id: str):
    """
    Read a Google Doc's textual content and return plain text.
    """
    doc = docs_service.documents().get(documentId=document_id).execute()
    body = doc.get("body", {}).get("content", [])
    out = []
    for structural_element in body:
        # Paragraphs and tables can contain text runs
        paragraph = structural_element.get("paragraph")
        if paragraph:
            text_run_parts = []
            for el in paragraph.get("elements", []):
                tr = el.get("textRun")
                if tr and tr.get("content"):
                    text_run_parts.append(tr["content"])
            if text_run_parts:
                out.append("".join(text_run_parts))
        # You could expand to table cells etc. if needed
    return "\n".join(out).strip()


def read_drive_file(drive_service, file_id: str, mime_type: Optional[str]):
    """
    Read a file from Drive:
    - If Google Doc, use Docs API (caller must provide credentials or build docs_service separately).
    - If text/plain, download raw media.
    """
    if mime_type == "application/vnd.google-apps.document":
        docs_service = build("docs", "v1", credentials=get_credentials())
        return read_google_doc(docs_service, file_id)
    else:
        # Attempt to download file contents (works for .txt and other binary types; we decode as utf-8)
        try:
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            data = fh.read()
            # try decode, fallback to latin-1 if necessary
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    return data.decode("utf-8-sig")
                except Exception:
                    return data.decode("latin-1", errors="ignore")
        except HttpError as e:
            logging.error(f"Error downloading file {file_id}: {e}")
            return None


def find_files_by_name(
    search_name: str, folder_id: str = '1hiSf6DSAO2RIv7ZCT7ltU8uBYQFvaOQu', page_size: int = 20
):
    """
    Find files in Google Drive that match a search string.
    Returns list of file dicts: [{'id','name','mimeType','snippet'(optional)}...]
    Tries name contains to match content inside Google Docs.
    """
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    clean = normalize(search_name)
    # Build query safely. Use either name or fullText match
    q_parts = []
    if clean:
        # escape single quotes by replacing with \'
        clean_escaped = clean.replace("'", "\\'")
        q_parts.append(f"name contains '{clean_escaped}'")
    else:
        q_parts.append("trashed=false")

    q_parts.append("trashed=false")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")

    query = " and ".join(q_parts)

    try:
        results = drive_service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=page_size,
        ).execute()
        items = results.get("files", [])
        if not items:
            return None

        # Attach snippet/content for each item if possible (read small snippets only)
        out = []
        for item in items:
            file_id = item["id"]
            mime = item.get("mimeType")
            # Read the file content (full) if it's reasonable; caller can choose
            content = None
            try:
                content = read_drive_file(drive_service, file_id, mime)
            except Exception as e:
                logging.warning(f"Could not read content for {file_id}: {e}")
            out.append({"id": file_id, "name": item.get("name"), "mimeType": mime, "content": content})
        return out
    except HttpError as e:
        logging.error(f"Drive API error during search: {e}")
        return None


def drive_save_lyrics(lyrics_list: List[Dict[str, str]], folder_id: str = '1hiSf6DSAO2RIv7ZCT7ltU8uBYQFvaOQu'):
    """
    Save each song's lyrics as a separate Google Doc in the given Drive folder.
    Each doc will be named "KoreanTitle / EnglishTitle" (fall back to unique id).
    lyrics_list entries should include keys:
        - 'korean_title' or 'korean'
        - 'english_title' or 'english'
        - 'korean_lyrics' or 'korean'
        - 'english_lyrics' or 'english'
    Returns list of created file metadata [{'id', 'name'}]
    """
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    created_files = []

    for entry in lyrics_list:
        eng_title = entry.get("english_title") or entry.get("english") or ""
        kor_title = entry.get("korean_title") or entry.get("korean") or ""
        eng_lyrics = entry.get("english_lyrics") or entry.get("english_lyrics") or entry.get("english") or ""
        kor_lyrics = entry.get("korean_lyrics") or entry.get("korean_lyrics") or entry.get("korean") or ""

        name_parts = []
        if kor_title.strip():
            name_parts.append(kor_title.strip())
        if eng_title.strip():
            name_parts.append(eng_title.strip())

        doc_name = " / ".join(name_parts) if name_parts else f"lyrics-{uuid.uuid4().hex[:8]}"

        try:
            file_metadata = {
                "name": doc_name,
                "mimeType": "application/vnd.google-apps.document",
            }
            if folder_id:
                file_metadata["parents"] = [folder_id]

            new_file = drive_service.files().create(body=file_metadata, fields="id,name").execute()
            doc_id = new_file.get("id")

            # Prepare content: english then korean (slide-by-slide style requested)
            # We'll create a single ordered list: English Title -> English Lyrics -> Korean Title -> Korean Lyrics
            # Break into lines and ensure we insert line-by-line to preserve structure
            parts = []
            if eng_title:
                parts.append(f"English Title: {eng_title}")
            if eng_lyrics:
                parts.extend([line for line in eng_lyrics.splitlines()])
            if kor_title:
                parts.append("")  # blank line separator
                parts.append(f"Korean Title: {kor_title}")
            if kor_lyrics:
                parts.extend([line for line in kor_lyrics.splitlines()])

            # Build batchUpdate requests: insert each line at increasing index
            requests = []
            # Insert at index 1 (start of doc). We'll insert a newline after each line so spacing is preserved.
            cursor_index = 1
            for idx, line in enumerate(parts):
                # ensure each inserted chunk ends with newline (except maybe last — Docs handles final newline fine)
                text_to_insert = f"{line}\n"
                requests.append({"insertText": {"location": {"index": cursor_index}, "text": text_to_insert}})
                cursor_index += len(text_to_insert)

            if requests:
                docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

            created_files.append({"id": doc_id, "name": new_file.get("name")})
        except Exception as e:
            logging.error(f"Failed to create doc for '{doc_name}': {e}")

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