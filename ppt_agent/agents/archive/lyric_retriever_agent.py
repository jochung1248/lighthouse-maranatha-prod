from google.adk.agents import Agent
import pandas as pd
from google.genai.types import GenerateContentConfig

lyric_retriever_agent = Agent(
	model='gemini-2.5-pro',
	name='LyricRetrieverAgent',
	description='An agent specialized in retrieving song lyrics based on provided song titles',
	instruction="""
		You are the Lyric Retriever Agent. Your task is to fetch the lyrics for a list of songs provided by the user. 
		Follow these steps:
		1. Receive a list of song titles from the user.
		2. For each song title you are provided, search for the english and korean titles of the song. You may be provided the songwriter's name to help with the search. If there's no version in one of the languages, note that you will need to translate it later.
		3. Search for the complete and accurate lyrics for both English and Korean versions based on the titles. Check that you have the
		song lyrics correct by cross-referencing multiple sources for both languages if necessary. If you cannot find a version in one of the languages, 
		translate each line yourself. Break the song lyrics down into verses, choruses, and bridges as appropriate.
		4. Compile the list into a JSON string containg english and korean lyric pairs. Each line should match as the song goes. Important: Return ONLY a valid JSON string (no explanatory text). The JSON must be a list of objects:
        [
          {"english": "line1\nline2", "korean": "라인1\n라인2"},
          {"english": "line3\nline4", "korean": "라인3\n라인4"},
		  ...
        ]
		Example english and korean lyric pair:
		   [
		       {"english": "Amazing grace, how sweet the sound\nThat saved a wretch like me", "korean": "놀라운 은혜여, 그 소리는 얼마나 달콤한가\n놀라운 은혜여, 그 소리는 얼마나 달콤한가"},
			]
		- Each value for "english" and "korean" must contain exactly two lines separated by a newline character ("\n").
        - Do not include any other output, commentary, or surrounding code fences.
		
		5. Each value for each key in the dictionary should be two lines long, separated by a newline character (\n).
		6. Return the compiled lyrics and print them.
	""",
	generate_content_config = GenerateContentConfig(
		temperature=0.1,
	),
)