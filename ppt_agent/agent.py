from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
from .agents.lyric_retriever_agent import lyric_retriever_agent as LyricRetrieverAgent
from .agents.slide_creator_agent import slide_creator_agent as SlideCreatorAgent
from google.genai.types import GenerateContentConfig


root_agent = Agent(
    model='gemini-2.5-pro',
    name='root_agent',
    description='A root orchestrator agent that manages sub-agents to develop a PowerPoint presentation based on user input.',
    instruction="""
		You are the Root Agent responsible for orchestrating the creation of a PowerPoint presentation for Lighthouse Maranatha Church. 
		Your task is to manage and delegate tasks to specialized sub-agents to ensure the presentation meets the user's requirements.
		You should follow these steps:
		1. Given a list of songs provided by the user, use the LyricRetrieverAgent to fetch the korean and english lyrics. If you successfully found existing files in Google Drive, let the user know which files you found.
			If you cannot find any files in Google Drive, let the user know.
		2. Output the titles and a short snippet of both languages and ask the user if these are correct.
		3. If the user confirms the titles are correct, proceed to use the LyricRetrieverAgent to fetch the complete lyrics for each song in both languages.
		This will return a string containing the list of pairs of english and korean lyrics in JSON format.
		4. Then parse the file path to the JSON file and call the Slide Creator Agent which will accept the JSON string 
		and convert it to a list of {"english", "korean"} pairs.
		5. Output the final PowerPoint presentation file once all slides have been created.
	""",
	generate_content_config = GenerateContentConfig(
		temperature=0.01,
	),
	tools = [
		AgentTool(LyricRetrieverAgent),
		AgentTool(SlideCreatorAgent)
	],
)
