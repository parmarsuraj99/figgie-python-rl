# Python implementation of Figgie 
My implementation for Jane Street's Figgie in Python 

API inspired from: [https://github.com/CornellDataScience/FiggieBot](https://github.com/CornellDataScience/FiggieBot)

## Setting up

1. Clone this repository: `git clone https://github.com/parmarsuraj99/figgie-python-rl` 
2. Move to root dir `cd figgie-python-rl`
3. Install necessary dependencies `pip install -r requirements.txt`
4. Setting up the Agents
   1. Optionally, Put your OpenAI or Anthropic API keys in the `.env-dev` file and rename it to `.env`
   2. Or you can replace the AI agents in the `clients.py` file.
5. Run the server with `python app.py`
   1. Optionally, visit `http://localhost:8000/` in the browser to view server logs
6. Run agents with `python clients.py`. This will spin up and connect four agents to the serverand start making tardes.
7. Enjoy