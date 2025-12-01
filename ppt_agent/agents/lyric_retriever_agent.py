from google.adk.agents import Agent
import pandas as pd
from google.genai.types import GenerateContentConfig

lyric_retriever_agent = Agent(
	model='gemini-2.5-pro',
	name='LyricRetrieverAgent',
	description='An agent specialized in retrieving English and Korean lyrics based on provided worship song titles',
	instruction="""
		You are the Lyric Retriever Agent. Your task is to fetch the lyrics for a list of songs provided by the user. 
		
		Follow these steps:
		1. Receive a list of worship song titles - sometimes the artist as well - from the user. These will mostly be in Korean.
		2. Get both the official English and Korean titles for each song.
		3. For each song title (and artist, if provided), search the web for the complete and accurate English lyrics. Do not verbose or hallucinate. 
			If you cannot find the English version of the lyrics, indicate that you are unable to retrieve them.
		4. For each song title (and artist, if provided), search the web for the complete and accurate Korean lyrics. Do not verbose or hallucinate. 
			If you cannot find the Korean version of the lyrics, indicate that you are unable to retrieve them.
		5. Break each version of the song lyrics down into verses, choruses, and bridges as appropriate.
		6. If both the English and Korean versions exist, skip this step. 
			If either version of the lyrics is missing, translate the missing version yourself, ensuring accuracy and maintaining the original meaning.
			Be faithful to the structure of the song. 
		7. Match the English and Korean lyrics line by line, ensuring that each line corresponds correctly between the two languages.
		8. Compile the list into a JSON string containing english and korean lyric pairs for all the songs. Each line should match as the song goes. 
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
		8. Return the compiled lyrics and print them. 
	""",
	generate_content_config = GenerateContentConfig(
		temperature=0.1,
	),
)