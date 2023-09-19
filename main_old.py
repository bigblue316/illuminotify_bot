import discord, json, os, re
from dotenv import load_dotenv

load_dotenv()
discord_token = os.environ.get('DISCORD_TOKEN')
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)

keywords_file = 'keywords.json'

def save_keywords(user_keywords):
    with open(keywords_file, 'w') as f:
        json.dump(user_keywords, f)

if os.path.exists(keywords_file):
    with open(keywords_file, 'r') as f:
        user_keywords = json.load(f)
        if not isinstance(user_keywords, dict):
            user_keywords = {}
else:
    user_keywords = {}
    save_keywords(user_keywords)

@client.event
async def on_ready():
    global user_keywords

    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

def detected_keywords(content, user_keywords, channel_id):
    keywords_found = []
    if isinstance(user_keywords, dict):
        for user_id, user_kw in user_keywords.items():
            positive_keywords = [kw for kw in user_kw if not kw.startswith("-") and user_kw[kw] == channel_id]
            negative_keywords = [kw[1:] for kw in user_kw if kw.startswith("-") and user_kw[kw] == channel_id]
            has_negative_kw = any([kw in content.lower() for kw in negative_keywords])
            if not has_negative_kw:
                for kw in positive_keywords:
                    # create a regex pattern to match the keyword with optional punctuation
                    pattern = r'\b' + re.escape(kw) + r'[-/.,?\|_#]?'
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        keywords_found.append(kw)
    return list(set(keywords_found))

@client.event
async def on_message(message):
    global user_keywords

    if message.author == client.user:
        return

    # check if the message triggered the function for the first time
    if not hasattr(on_message, "triggered"):
        on_message.triggered = False

    msg = message.content
    print("Received message: ", msg)
    tag_channel_id = 1091921512774246433    # Specify the channel ID to ping
    link = message.jump_url
    tag_channel = client.get_channel(tag_channel_id)
    current_channel_id = message.channel.id

    # create a list of member IDs in the server
    member_ids = []
    for member in client.guilds[0].members:
        member_ids.append(str(member.id))

    # remove IDs and keywords that are no longer in the server
    for user_id in list(user_keywords.keys()):
        if user_id not in member_ids:
            del user_keywords[user_id]

    save_keywords(user_keywords)

    if message.embeds:
        keywords_found = set() # store found keywords to avoid repetition
        for embed in message.embeds:
            embed_dict = embed.to_dict()
            for k, v in embed_dict.items():
                if k == "author":
                    continue # skip this field and its value
                print(k, v)

            # iterate over all four sections to check for keywords
            for section in [msg, embed.description, embed.title, ' '.join([field.value for field in embed.fields if field.name != 'Offer Id'])]:
                if section:
                    # check if section is a URL link and exclude it from keyword search
                    if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', section):
                        continue
                    found_keywords = detected_keywords(section, user_keywords, current_channel_id)
                    if found_keywords:
                        for found_keyword in found_keywords:
                            if found_keyword not in keywords_found:
                                users_with_keyword = []
                                for user_id, keywords in user_keywords.items():
                                    if found_keyword in keywords:
                                        try:
                                            user = await client.fetch_user(int(user_id))
                                        except discord.errors.NotFound:
                                            print(f"User {user_id} not found")
                                            user_keywords.pop(user_id, None)
                                            save_keywords(user_keywords)
                                            continue
                                        users_with_keyword.append(user.mention)
                                if users_with_keyword:
                                    chunks = [users_with_keyword[i:i+50] for i in range(0, len(users_with_keyword), 50)]
                                    for chunk in chunks:
                                        await tag_channel.send(f"``{found_keyword}`` found in <#{current_channel_id}> {link} {' '.join(chunk)}")
                                    keywords_found.add(found_keyword) # add to found keywords to avoid repetition

    if msg.startswith('??add'):
        try:
            keywords = [x.strip().lower() for x in msg.split('??add ')[1].split(',') if x.strip()]
            if keywords[-1].endswith(','):
                await message.channel.send("Please do not end the list with a comma.")
                return
            for keyword in keywords:
                if keyword not in user_keywords.get(str(message.author.id), []):
                    user_keywords.setdefault(str(message.author.id), []).append(keyword)
                    save_keywords(user_keywords)
                    await message.channel.send(f"Added: ``{keyword}``")

                else:
                    await message.channel.send(f"Already in your list: ``{keyword}``")

        except IndexError:
            await message.channel.send(f"Please provide keyword(s) to add, separated by comma(s), like this: `??add <keyword1>, <keyword2>, <keyword3>`")

    elif msg.startswith('??del'):
        try:
            keywords = [k.strip().lower() for k in msg.split('??del ')[1].split(',')]
            removed_keywords = []
            for keyword in keywords:
                if keyword in user_keywords.get(str(message.author.id), []):
                    user_keywords[str(message.author.id)].remove(keyword)
                    removed_keywords.append(keyword)
            if removed_keywords:
                save_keywords(user_keywords)
                await message.channel.send(f"Removed: ``{', '.join(removed_keywords)}``")
            else:
                await message.channel.send(f"Not in your list: ``{', '.join(keywords)}``")
        except IndexError:
            await message.channel.send(f"Please provide keyword(s) to delete, separated by comma(s), like this: ??del <keyword1>, <keyword2>, <keyword3>`")

    elif msg.startswith('??list'):
        keywords_str = ', '.join(user_keywords.get(str(message.author.id), []))
        if not keywords_str:
            await message.channel.send("You don't have any keywords yet. Add some with `??add <keyword>`!")
        else:
            await message.channel.send(f"Your keywords:  ``{keywords_str}``")

    elif msg.startswith('??clear'):
        try:
            user_keywords[str(message.author.id)] = []
            save_keywords(user_keywords)
            await message.channel.send("All keywords removed.")
        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")

    elif msg.startswith('??help'):
        help_message = """
        Usage: 

        `??add` - Add a keyword or -keyword to your list
        `??del` - Remove a keyword or -keyword from your list
        `??list` - List all the keywords in your list
        `??clear` - Remove all keywords in your list
        """
        await message.channel.send(help_message)

    elif msg.startswith('??users'):
        if user_keywords:
            users_list = []
            for user_id, keywords in user_keywords.items():
                try:
                    user = await client.fetch_user(int(user_id))
                except discord.errors.NotFound:
                    print(f"User {user_id} not found")
                    continue
                users_list.append(f"{user.name}#{user.discriminator} ({len(keywords)})")
            await message.channel.send(f"**Users with keywords:**\n{', '.join(users_list)}")
        else:
            await message.channel.send("No users with keywords found.")

    elif msg.startswith('??keywords.json'):
        with open(keywords_file, 'r') as f:
            keywords_json = json.load(f)
            keywords_str = json.dumps(keywords_json)
            if len(keywords_str) > 1700:
                chunks = [keywords_str[i:i+1700] for i in range(0, len(keywords_str), 1700)]
                for chunk in chunks:
                    await message.channel.send(f"```{chunk}```")
            else:
                await message.channel.send(f"```{keywords_str}```")

    elif msg.startswith('??top10'):
        if user_keywords:
            keyword_count = {}
            for keywords in user_keywords.values():
                for keyword in keywords:
                    keyword_count[keyword] = keyword_count.get(keyword, 0) + 1
            top_keywords = sorted(keyword_count, key=keyword_count.get, reverse=True)[:10]
            top_keywords_string = '\n'.join([f"{i+1}. {keyword} ({keyword_count[keyword]})" for i, keyword in enumerate(top_keywords)])
            await message.channel.send(f"Top 10 most used keywords:\n{top_keywords_string}")
        else:
            await message.channel.send("There are no keywords to show.")

    # reset the trigger flag after the first time the message triggered the function
    if not on_message.triggered:
        on_message.triggered = True
    else:
        on_message.triggered = False
            
client.run(discord_token)