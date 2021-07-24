# Whitelist Bot
## Setup
- Have a 3.X version of Python installed, I'm not going to walk you through this.
- Run `pip install -r requirements.txt` in the installation folder
- Create a bot in Discord's Dev portal (if you don't know how, google it)
- Add the bot token to the environment variables or a .env file
- Run the program once, it'll generate some files in the data folder
- Go into the data folder, open `settings.json` and paste in the channel ID of the channel in which you want queued 
whitelist actions to be sent to in the empty quotes.
- Run the program again, if you did it right, it should now be working.