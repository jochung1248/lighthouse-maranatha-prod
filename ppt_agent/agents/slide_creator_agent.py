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

# --- CONFIG ---
SCOPES = ['https://www.googleapis.com/auth/drive']  # or 'https://www.googleapis.com/auth/drive'
TARGET_FOLDER_ID = '1PoqUg00k3BA1HOG1Nn4HyqpUhvdUT-YX'  # optional
TEMPLATE_SUNDAY_PRESENTATION_ID = '1FCivH5ECj72APlWDdsu_3BoHZN9LWbBl'
TEMPLATE_FRIDAY_PRESENTATION_ID = '1LevZxXZWhVzD06DYpSTbddw9-t0RlU4M'


def create_slides_file(TEMPLATE_ID = '1FCivH5ECj72APlWDdsu_3BoHZN9LWbBl'):
    """Creates a new Google Slides presentation using OAuth credentials."""
    creds = None

    # Token is stored after first successful login
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials, log in through browser
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                './credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for next time
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # Build Drive and Slides clients
        drive_service = build('drive', 'v3', credentials=creds)
        

        # Generate a unique presentation name
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        title = f"{timestamp}"

        # Create via Drive API (avoids ownership edge cases)
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.presentation',
        }
        if TARGET_FOLDER_ID:
            file_metadata['parents'] = [TARGET_FOLDER_ID]

        # Copy template presentation
        file = drive_service.files().copy(
            fileId=TEMPLATE_ID,
            body=file_metadata
        ).execute()


        #file = drive_service.files().create(body=file_metadata, fields='id').execute()
        presentation_id = file.get('id')
        
        print(f"✅ Successfully created presentation: '{title}'")
        print(f"🔗 Link: https://docs.google.com/presentation/d/{presentation_id}/edit")
        return presentation_id
    except HttpError as error:
        print(f"❌ An API error occurred: {error}")


def add_lyric_slide(presentation_id, english, korean, insertion_index=5):
    """
    Create a new slide, remove default placeholders, then add two text boxes:
    - English (top) — yellow, Arial Black, 24pt, centered
    - Korean  (below) — white, Arial, 24pt, centered
    """
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        raise RuntimeError("token.json not found; run OAuth flow first")

    slides_service = build('slides', 'v1', credentials=creds)

    try:
        pres = slides_service.presentations().get(presentationId=presentation_id).execute()
        page_width_pt = pres['pageSize']['width']['magnitude'] / 12700.0
        page_height_pt = pres['pageSize']['height']['magnitude'] / 12700.0

        full_width = {"magnitude": page_width_pt, "unit": "PT"}
        eng_height = 90
        korean_height = 90
        
        eng_pt = {"magnitude": eng_height, "unit": "PT"}
        kor_pt = {"magnitude": korean_height, "unit": "PT"}

        slide_id = f"slide_{uuid.uuid4().hex[:8]}"
        
        eng_id = f"eng_{uuid.uuid4().hex[:8]}"
        kor_id = f"kor_{uuid.uuid4().hex[:8]}"

        # Y positions (translateY) measured in PT from top
        eng_translate_y = page_height_pt - 180
        kor_translate_y = page_height_pt - 90

        requests = [
            # create slide
            {
                "createSlide": {
                    "objectId": slide_id,
                    "insertionIndex": str(insertion_index),
                    #"slideLayoutReference": {"predefinedLayout": layout}
                }
            },
            # set background to black
            {
                "updatePageProperties": {
                    "objectId": slide_id,
                    "pageProperties": {
                        "pageBackgroundFill": {
                            "solidFill": {
                                "color": {
                                    "rgbColor": {"red": 0.0, "green": 0.0, "blue": 0.0}
                                }
                            }
                        }
                    },
                    "fields": "pageBackgroundFill"
                }
            },
            # create English text box (top)
            {
                "createShape": {
                    "objectId": eng_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {"height": eng_pt, "width": full_width},
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": 0,
                            "translateY": eng_translate_y,
                            "unit": "PT"
                        }
                    },
                }
            },
            {
                "updateShapeProperties": {
                    "objectId": eng_id,
                    "shapeProperties": {
                        "contentAlignment": "BOTTOM"   # options: TOP, MIDDLE, BOTTOM
                    },
                    "fields": "contentAlignment"
                }
            },
            # create Korean text box (below)
            {
                "createShape": {
                    "objectId": kor_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {"height": kor_pt, "width": full_width},
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": 0,
                            "translateY": kor_translate_y,
                            "unit": "PT"
                        }
                    }
                }
            },
            {
                "updateShapeProperties": {
                    "objectId": kor_id,
                    "shapeProperties": {
                        "contentAlignment": "TOP"   # options: TOP, MIDDLE, BOTTOM
                    },
                    "fields": "contentAlignment"
                }
            },
            # insert english text
            {"insertText": {"objectId": eng_id, "text": english}},
            # style english (Arial Black, 24pt, yellow)
            {
                "updateTextStyle": {
                    "objectId": eng_id,
                    "style": {
                        "fontFamily": "Arial Black",
                        "fontSize": {"magnitude": 26, "unit": "PT"},
                        "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 0.0}}}
                    },
                    "fields": "fontFamily,fontSize,foregroundColor"
                }
            },
            # center english paragraph
            {"updateParagraphStyle": {"objectId": eng_id, "style": {"alignment": "CENTER"}, "fields": "alignment"}},

            # insert korean text
            {"insertText": {"objectId": kor_id, "text": korean}},
            # style korean (Arial, 24pt, white)
            {
                "updateTextStyle": {
                    "objectId": kor_id,
                    "style": {
                        "fontFamily": "Calibri",
                        "fontSize": {"magnitude": 30, "unit": "PT"},
                        "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}},
                        "bold": True
                    },
                    "fields": "fontFamily,fontSize,foregroundColor, bold"
                }
            },
            # center korean paragraph
            {"updateParagraphStyle": {"objectId": kor_id, "style": {"alignment": "CENTER"}, "fields": "alignment"}}
        ]

        # remove any default pageElements after creating the slide (defensive)
        slides_service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": requests}).execute()

        # fetch pageElements for the new slide and delete any leftover placeholders
        pres_after = slides_service.presentations().get(
            presentationId=presentation_id,
            fields="slides(objectId,pageElements(objectId))"
        ).execute()

        delete_requests = []
        for s in pres_after.get("slides", []):
            if s.get("objectId") != slide_id:
                continue
            for pe in s.get("pageElements", []):
                pid = pe.get("objectId")
                # skip the two shapes we just created
                if pid and pid not in (eng_id, kor_id):
                    delete_requests.append({"deleteObject": {"objectId": pid}})

        if delete_requests:
            slides_service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": delete_requests}).execute()

        print(f"✅ Added slide {slide_id} to {presentation_id}")
        return slide_id

    except HttpError as error:
        print(f"❌ An API error occurred: {error}")
        raise

def create_presentation(text_pairs: list[dict[str, str]]) -> None:
    presentation_id = create_slides_file()
    
    for pair in reversed(text_pairs):
        add_lyric_slide(presentation_id, pair['english'], pair['korean'])
    
    print("Presentation created with URL: https://docs.google.com/presentation/d/{}/edit".format(presentation_id))
    
""" 
def create_presentation_from_file(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lyrics_data = json.load(f)
        
        # Create the presentation
        presentation_id = create_presentation(lyrics_data)
        
        # Clean up temp file
        os.remove(file_path)
        
        return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    except Exception as e:
        print("❌ Detailed error:", repr(e))
        raise ValueError(f"Error creating presentation: {str(e)}") """


slide_creator_agent = Agent(
    model='gemini-2.5-flash',
    name='SlideCreatorAgent',
    description='An agent specialized in creating PowerPoint slides based on provided song lyrics',
    instruction="""
        You are the Slide Creator Agent. Your task is to create PowerPoint slides based on
        the lyrics provided by the Lyric Retriever Agent. Follow these steps:
        1. Receive a list of {"english", "korean"} objects which containing the song lyrics.
        2. Create a new PowerPoint presentation using the create_presentation(TEMPLATE_ID) function. \
            If the lyrics are for a Sunday service, use TEMPLATE_SUNDAY_PRESENTATION_ID. \
            If the lyrics are for a Friday service, use TEMPLATE_FRIDAY_PRESENTATION_ID.
            TEMPLATE_SUNDAY_PRESENTATION_ID = '1FCivH5ECj72APlWDdsu_3BoHZN9LWbBl'
            TEMPLATE_FRIDAY_PRESENTATION_ID = '1LevZxXZWhVzD06DYpSTbddw9-t0RlU4M'
        3. Each slide should contain a maximum of two lines for each language.
        4. Save and return the final PowerPoint presentation file.
    """,
    tools=[
        create_presentation,
    ],
)