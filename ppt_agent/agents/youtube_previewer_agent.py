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
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
import logging
import html

SCOPES = ["https://www.googleapis.com/youtube/v3"]


def preview_youtube_playlist(playlist_id: str, caption_chars: int = 300,):
    """
    Fetch a YouTube playlist and return:
      - video titles
      - caption snippet (first available caption)

    Args:
        playlist_id: YouTube playlist ID
        caption_chars: How many caption characters to preview
        creds_file: OAuth credentials JSON
        token_file: Stored OAuth token

    Returns:
        List of dicts: [{'video_id', 'title', 'caption_snippet'}]
    """

    logging.info("🔐 Authenticating YouTube API...")

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

        logging.info(f"📂 Fetching playlist items for playlist: {playlist_id}")

        # --- STEP 1: Fetch playlist videos ---
        while True:
            req = youtube.playlistItems().list(
                part="snippet", playlistId=playlist_id, maxResults=50, pageToken=next_page_token
            )
            res = req.execute()

            for item in res.get("items", []):
                video_id = item["snippet"]["resourceId"]["videoId"]
                title = item["snippet"]["title"]
                videos.append({"video_id": video_id, "title": title, "caption_snippet": None})

            next_page_token = res.get("nextPageToken")
            if not next_page_token:
                break

        logging.info(f"📺 Found {len(videos)} videos in playlist.")

        # --- STEP 2: Get captions ---
        for v in videos:
            try:
                cap_list = youtube.captions().list(
                    part="snippet", videoId=v["video_id"]
                ).execute()

                items = cap_list.get("items", [])
                if not items:
                    continue

                caption_id = items[0]["id"]

                # Download captions in XML
                cap_dl = youtube.captions().download(id=caption_id, tfmt="srv1")
                cap_xml = cap_dl.execute(decode=False).decode("utf-8")

                # Extract <text>...</text> entries
                text_nodes = re.findall(r"<text[^>]*>(.*?)</text>", cap_xml)
                text_nodes = [html.unescape(t) for t in text_nodes]

                full_caption = " ".join(text_nodes)
                snippet = full_caption[:caption_chars].strip()

                if snippet:
                    v["caption_snippet"] = snippet + ("..." if len(full_caption) > caption_chars else "")

            except HttpError as e:
                logging.warning(f"⚠️ Skipping captions for {v['video_id']}: {e}")
                continue

        return videos

    except HttpError as error:
        logging.error(f"❌ YouTube API error: {error}")
        return None
