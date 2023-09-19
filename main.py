import discord, json, os, re
from discord import Embed, Colour
from dotenv import load_dotenv

load_dotenv()
discord_token = os.getenv('DISCORD_TOKEN')
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
    content_lower = content.lower()  # convert content to lower case
    keywords_found = []
    if isinstance(user_keywords, dict):
        for user_id, user_data in user_keywords.items():
            if str(channel_id) not in user_data:  # skip if current channel isn't tracked by the user
                continue
            user_kw = user_data[str(channel_id)]
            for kw in user_kw:
                pattern = r'\b' + re.escape(kw.lower()) + r'\b'  # convert keyword to lower case
                match = re.search(pattern, content_lower)
                if match:
                    keywords_found.append(kw)
    return list(set(keywords_found))

@client.event
async def on_message(message):
    global user_keywords

    if message.author == client.user:
        return

    if not hasattr(on_message, "triggered"):
        on_message.triggered = False

    msg = message.content
    print("Received message: ", msg)
    tag_channel_id = 1091921512774246433
    link = message.jump_url
    tag_channel = client.get_channel(tag_channel_id)
    current_channel_id = message.channel.id

    member_ids = []
    for member in client.guilds[0].members:
        member_ids.append(str(member.id))

    for user_id in list(user_keywords.keys()):
        if user_id not in member_ids:
            del user_keywords[user_id]

    save_keywords(user_keywords)

    if message.embeds:
        keywords_found = set()
        for embed in message.embeds:
            embed_dict = embed.to_dict()
            
            # Extract thumbnail image and product URL
            thumbnail_url = embed_dict.get('thumbnail', {}).get('url', None)
            product_url = embed_dict.get('url', None)
            
            # Extract eBay links from the embed's fields
            ebay_links = None
            for field in embed_dict.get('fields', []):
                if field.get('name') == 'eBay Links':
                    ebay_links = field.get('value')
                    break

            for k, v in embed_dict.items():
                if k == "author":
                    continue # skip this field and its value
                print(k, v)
                
            for section in [msg, embed.description, embed.title, ' '.join([field.value for field in embed.fields if field.name != 'Offer Id'])]:
                if section:
                    if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', section):
                        continue
                    found_keywords = detected_keywords(section, user_keywords, current_channel_id)
                    if found_keywords:
                        for found_keyword in found_keywords:
                            if found_keyword not in keywords_found:
                                users_with_keyword = []
                                for user_id, channels in user_keywords.items():
                                    for channel_id, keywords in channels.items():
                                        if str(channel_id) != str(current_channel_id):
                                            continue
                                        if found_keyword in keywords:
                                            try:
                                                user = await client.fetch_user(int(user_id))
                                                users_with_keyword.append(user.mention)
                                            except discord.errors.NotFound:
                                                print(f"User {user_id} not found or not in this server.")
                                                continue

                                if users_with_keyword:
                                    chunks = [users_with_keyword[i:i+50] for i in range(0, len(users_with_keyword), 50)]
                                    for chunk in chunks:
                                        embed_notify = discord.Embed(title="Keyword found!", color=0x00ff00)
                                        embed_notify.add_field(name="Keyword", value=f"`{found_keyword}`", inline=True)
                                        embed_notify.add_field(name="Channel", value=f"<#{current_channel_id}>", inline=True)
                                        embed_notify.add_field(name="Message Link", value=f"{link}", inline=False)
                                        # Add thumbnail image
                                        if thumbnail_url:
                                            embed_notify.set_thumbnail(url=thumbnail_url)
                                        # Add eBay links as a field
                                        if ebay_links:
                                            embed_notify.add_field(name="eBay Links", value=ebay_links, inline=True)
                                        # Add product URL with title as anchor text
                                        if product_url:
                                            product_title = embed.title if embed.title else "Source Page"
                                            embed_notify.add_field(name="Source Page", value=f"[{product_title}]({product_url})", inline=False)
                                        await tag_channel.send(embed=embed_notify)
                                        await tag_channel.send(' '.join(chunk))
                                    keywords_found.add(found_keyword)

    elif msg.startswith('??add'):
        try:
            # Get the channel IDs
            channel_id_matches = re.findall(r'<#(\d+)>', msg)
            if not channel_id_matches:
                await message.channel.send("Please specify a channel.")
                return

            # Get all parts of the message after '??add', and replace the channel ids with an empty string
            msg_without_channels = msg
            for channel_id_match in channel_id_matches:
                msg_without_channels = msg_without_channels.replace(f'<#{channel_id_match}>', '').strip()

            keywords = msg_without_channels.split('??add', 1)[1].split(',')
            keywords = [kw.strip().lower() for kw in keywords if kw.strip() and kw.strip() != ',']  # Added a condition to filter out invalid keywords

            channel_keywords_added = {}
            for channel_id_match in channel_id_matches:
                channel_id = int(channel_id_match)

                # Get the channel
                channel = client.get_channel(channel_id)
                if channel is None:
                    await message.channel.send("Couldn't find the specified channel.")
                    continue

                channel_keywords_added[channel.mention] = []
                for keyword in keywords:
                    if keyword not in user_keywords.get(str(message.author.id), {}).get(str(channel.id), []):
                        channel_keywords_added[channel.mention].append(keyword)
                        user_keywords.setdefault(str(message.author.id), {}).setdefault(str(channel.id), []).append(keyword)

            if any(channel_keywords_added.values()):
                save_keywords(user_keywords)
                embed = discord.Embed(title="Keywords Added", description="", color=0x00ff00)
                for channel, added_keywords in channel_keywords_added.items():
                    if added_keywords:
                        embed.add_field(name=channel, value="Added: " + ', '.join([f'``{keyword}``' for keyword in added_keywords]), inline=False)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("All provided keywords are already in your list for the specified channels.")

        except IndexError:
            await message.channel.send(f"Please provide keyword(s) and channel to add, like this: `??add <keyword1, keyword2> <#channel1> <#channel2>`")

    elif msg.startswith('??delete'):
        try:
            # Get the channel IDs
            channel_id_matches = re.findall(r'<#(\d+)>', msg)
            if not channel_id_matches:
                await message.channel.send("Please specify a channel.")
                return

            # Get all parts of the message after '??delete', and replace the channel ids with an empty string
            msg_without_channels = msg
            for channel_id_match in channel_id_matches:
                msg_without_channels = msg_without_channels.replace(f'<#{channel_id_match}>', '').strip()

            keywords = msg_without_channels.split('??delete', 1)[1].split(',')
            keywords = [kw.strip() for kw in keywords]

            channel_keywords_removed = {}
            for channel_id_match in channel_id_matches:
                channel_id = int(channel_id_match)

                # Get the channel
                channel = client.get_channel(channel_id)
                if channel is None:
                    await message.channel.send("Couldn't find the specified channel.")
                    continue

                channel_keywords_removed[channel.mention] = []
                for keyword in keywords:
                    if keyword in user_keywords.get(str(message.author.id), {}).get(str(channel.id), []):
                        channel_keywords_removed[channel.mention].append(keyword)
                        user_keywords[str(message.author.id)][str(channel.id)].remove(keyword)

            if any(channel_keywords_removed.values()):
                save_keywords(user_keywords)
                embed = discord.Embed(title="Keywords Removed", description="", color=0x00ff00)
                for channel, removed_keywords in channel_keywords_removed.items():
                    if removed_keywords:
                        embed.add_field(name=channel, value="Removed: " + ', '.join([f'``{keyword}``' for keyword in removed_keywords]), inline=False)
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("None of the provided keywords were in your list for the specified channels.")

        except IndexError:
            await message.channel.send(f"Please provide keyword(s) and channel to delete, like this: `??delete <keyword1,keyword2> <#channel1> <#channel2>`")

    elif msg.startswith('??list'):
        user_keywords_channels = user_keywords.get(str(message.author.id), {})
        
        for channel_id, keywords in list(user_keywords_channels.items()):
            if not keywords:
                del user_keywords_channels[channel_id]
        
        if not user_keywords_channels:
            await message.channel.send("You don't have any keywords yet. Add some with `??add <keyword> <#channel>`!")
        else:
            embed = Embed(title="Your Keywords", color=Colour.blue())
            for channel_id, keywords in user_keywords_channels.items():
                channel = client.get_channel(int(channel_id))
                if channel:
                    embed.add_field(name=f"{channel.mention}", value=f"`{', '.join(keywords)}`", inline=False)
                else:
                    embed.add_field(name=f"Channel ID: {channel_id}", value=f"`{', '.join(keywords)}`", inline=False)
            
            await message.channel.send(embed=embed)

    elif msg.startswith('??clear'):
        try:
            channel_id_match = re.search(r'<#(\d+)>', msg)
            if channel_id_match is None:    # if no channel is specified, check if it's a 'list' command
                if msg.strip() == '??clear list':
                    user_keywords[str(message.author.id)] = {}
                    save_keywords(user_keywords)
                    await message.channel.send("All keywords removed from all channels.")
                else:
                    await message.channel.send("Please specify a #channel or use 'list'.")
                return

            channel_id = int(channel_id_match.group(1))

            channel = client.get_channel(channel_id)
            if channel is None:
                await message.channel.send("Couldn't find the specified channel.")
                return

            if str(channel_id) in user_keywords.get(str(message.author.id), {}):
                del user_keywords[str(message.author.id)][str(channel_id)]
                save_keywords(user_keywords)

                embed = Embed(title="Keyword Clearing", color=Colour.red())
                embed.add_field(name="Clear Successful", value=f"All keywords removed from {channel.mention}.", inline=False)
            else:
                embed = Embed(title="Keyword Clearing", color=Colour.orange())
                embed.add_field(name="No Keywords to Clear", value=f"No keywords found for {channel.mention}.", inline=False)

            await message.channel.send(embed=embed)

        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")

    elif msg.startswith('??clear list'):
        try:
            user_keywords[str(message.author.id)] = {}
            save_keywords(user_keywords)

            embed = Embed(title="Keyword Clearing", color=Colour.red())
            embed.add_field(name="Clear Successful", value="All keywords removed from all channels.", inline=False)

            await message.channel.send(embed=embed)

        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")

    elif msg.startswith('??help'):
        embed = discord.Embed(title="Keyword Pinger Commands Help", color=Colour.blue())

        embed.add_field(name="Add keywords to a channel:", value="\nYou can add one or more keywords, separated by commas.```??add word1,word2,word3 #channel1 #channel2```", inline=False)
        
        embed.add_field(name="Delete keywords from a channel:", value="\nYou can delete one or more keywords, separated by commas.```??delete word1,word2,word3 #channel1 #channel2```", inline=False)

        embed.add_field(name="List your keywords:", value="\nThis command will show all your keywords.```??list```", inline=False)

        embed.add_field(name="Clear all keywords from all channels:", value="\nThis command will remove all your keywords in __all channels!__```??clear list```", inline=False)

        embed.add_field(name="Clear all keywords from a channel:", value="\nThis command will remove all your keywords in one channel.```??clear #channel1```", inline=False)
        
        await message.channel.send(embed=embed)

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
            
            embed = Embed(title="Users with keywords", description=', '.join(users_list), color=Colour.blue())
            await message.channel.send(embed=embed)
        else:
            embed = Embed(title="Users with keywords", description="No users with keywords found.", color=Colour.red())
            await message.channel.send(embed=embed)

    elif msg.startswith('??keywords.json'):
        with open(keywords_file, 'r') as f:
            keywords_json = json.load(f)
            keywords_str = json.dumps(keywords_json)
            if len(keywords_str) > 1700:
                chunks = [keywords_str[i:i+1700] for i in range(0, len(keywords_str), 1700)]
                for chunk in chunks:
                    embed = Embed(title="Keywords.json", description=f"```{chunk}```", color=Colour.blue())
                    await message.channel.send(embed=embed)
            else:
                embed = Embed(title="Keywords.json", description=f"```{keywords_str}```", color=Colour.blue())
                await message.channel.send(embed=embed)

    elif msg.startswith('??top10'):
        if user_keywords:
            keyword_count = {}
            for user, channels in user_keywords.items():
                for channel, keywords in channels.items():
                    for keyword in keywords:
                        keyword_count[keyword] = keyword_count.get(keyword, 0) + 1
            top_keywords = sorted(keyword_count, key=keyword_count.get, reverse=True)[:10]
            top_keywords_string = '\n'.join([f"{i+1}. {keyword} ({keyword_count[keyword]})" for i, keyword in enumerate(top_keywords)])

            embed = Embed(title="Top 10 most used keywords", description=top_keywords_string, color=Colour.blue())
            await message.channel.send(embed=embed)
        else:
            embed = Embed(title="Top 10 most used keywords", description="There are no keywords to show.", color=Colour.red())
            await message.channel.send(embed=embed)
    # reset the trigger flag after the first time the message triggered the function
    if not on_message.triggered:
        on_message.triggered = True
    else:
        on_message.triggered = False
            
client.run(discord_token)
