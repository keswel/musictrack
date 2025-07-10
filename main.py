from typing import Final
import os
from dotenv import load_dotenv
from io import BytesIO
from discord import Intents, Client, Message
from responses import get_response
from pathlib import Path
from pydub import AudioSegment

# load data!
DATA_FILE = Path('data.txt')


def load_user_data():
    if not DATA_FILE.exists():
        return {}
    user_data = {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=2)
            if len(parts) == 2:
                # Old format: username count
                username, count_str = parts
                user_data[username] = {'count': int(count_str), 'duration': 0.0}
            elif len(parts) == 3:
                # New format: username count duration
                username, count_str, duration_str = parts
                user_data[username] = {'count': int(count_str), 'duration': float(duration_str)}
    return user_data


def save_user_data(user_data):
    """Save the user song counts and durations dict back to the file."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        for username, data in user_data.items():
            f.write(f"{username} {data['count']} {data['duration']:.2f}\n")


def increment_user_song_count(username):
    """Increment the song count for a username, adding if new."""
    user_data = load_user_data()
    if username not in user_data:
        user_data[username] = {'count': 0, 'duration': 0.0}
    user_data[username]['count'] += 1
    save_user_data(user_data)


def increment_user_song_time(username, duration_sec):
    """Add duration to the user's total time."""
    user_data = load_user_data()
    if username not in user_data:
        user_data[username] = {'count': 0, 'duration': 0.0}
    user_data[username]['duration'] += duration_sec
    save_user_data(user_data)


def format_duration(seconds):
    """Format duration in seconds to a readable format."""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    hours = minutes // 60
    minutes = minutes % 60

    if hours > 0:
        return f"{hours}h {minutes}m {remaining_seconds}s"
    elif minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    else:
        return f"{remaining_seconds}s"


# load token!
load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN')

# bot setup
intents: Intents = Intents.default()
intents.message_content = True  # NOQA
client: Client = Client(intents=intents)


# message functionality
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        return
    if user_message == ">scan":
        await message.channel.send("Scanning `#wip-beats` for past audio uploads...")

        file_path = "data.txt"
        try:
            with open(file_path, "w"):
                pass
            print(f"File {file_path} cleared successfully.")
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

        # Find the #wip-beats channel
        wip_channel = None
        for channel in message.guild.text_channels:
            if channel.name == "wip-beats":
                wip_channel = channel
                break

        if not wip_channel:
            await message.channel.send("❌ Couldn't find `#wip-beats` channel.")
            return

        found_count = 0
        async for msg in wip_channel.history(limit=None, oldest_first=True):
            for attachment in msg.attachments:
                if attachment.filename.endswith(('.mp3', '.wav')):
                    try:
                        data = await attachment.read()
                        audio = AudioSegment.from_file(BytesIO(data))
                        duration_sec = audio.duration_seconds
                        print(f"audio length: {duration_sec}")
                        if duration_sec > 10:
                            increment_user_song_count(str(msg.author))
                            increment_user_song_time(str(msg.author), duration_sec)
                            found_count += 1
                    except Exception as e:
                        print(f"Error reading file {attachment.filename}: {e}")

        await message.channel.send(f"✅ Scan complete. Found {found_count} valid audio uploads.")
        return
    if user_message == ">help":
        await message.channel.send("**>scan** - Rescans all of #wip-beats for .mp3 and .wav (above 10 seconds long).\n"
                                   "**>leaderboard** - Shows top 3 users with most songs sent.\n"
                                   "**>stats** - Displays personal stats (song count and total duration of songs)\n"
                                   "**>server-stats** - Displays stats of everyone who has sent a song in #wip-beats\n"
                                   "**>server-duration** - Displays total time of each song in #wip-beats combined.")
        return

    if user_message == ">server-duration":
        user_data = load_user_data()
        if not user_data:
            await message.channel.send("No songs have been submitted yet!")
            return

        # Calculate total duration across all users
        total_duration = sum(data['duration'] for data in user_data.values())
        total_songs = sum(data['count'] for data in user_data.values())

        # Format the total duration
        duration_str = format_duration(total_duration)

        await message.channel.send(
            f"🎵 **Server Total:** {total_songs} song(s) with a combined duration of **{duration_str}**!"
        )
        return

    if user_message == ">leaderboard":
        user_data = load_user_data()
        if not user_data:
            await message.channel.send("No songs have been submitted yet!")
            return
        # sort users by song count
        sorted_users = sorted(user_data.items(), key=lambda item: item[1]['count'], reverse=True)

        # get top 3
        top_3 = sorted_users[:3]
        leaderboard_msg = "**Top 3 by Song Count:**\n"
        for i, (username, data) in enumerate(top_3, start=1):
            duration_str = format_duration(data['duration'])
            leaderboard_msg += f"{i}. `{username}` — {data['count']} song(s) ({duration_str})\n"

        await message.channel.send(leaderboard_msg)
        return
    if user_message == ">stats":
        user_data = load_user_data()
        data = user_data.get(str(message.author), {'count': 0, 'duration': 0.0})
        duration_str = format_duration(data['duration'])
        await message.channel.send(
            f"🎵 {message.author} has sent **{data['count']} song(s)** "
            f"with a total duration of **{duration_str}**!")
        return

    if user_message == ">server-stats":
        user_data = load_user_data()
        if not user_data:
            await message.channel.send("No songs have been submitted yet!")
            return
        # sort users by song count
        sorted_users = sorted(user_data.items(), key=lambda item: item[1]['duration'], reverse=True)

        # get top 3
        top_3 = sorted_users
        serverstats_msg = "**Server Stats:**\n"
        for i, (username, data) in enumerate(top_3, start=1):
            duration_str = format_duration(data['duration'])
            serverstats_msg += f"{i}. `{username}` — {data['count']} song(s) ({duration_str})\n"

        await message.channel.send(serverstats_msg)
        return

    if is_private := user_message[0] == '?':
        user_message = user_message[1:]

    try:
        response: str = get_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)
    except Exception as e:
        print(e)


# handle startup for bot
@client.event
async def on_ready() -> None:
    print(f'{client.user} is now running!')


# handle incoming messages
@client.event
async def on_message(message: Message) -> None:
    # if message == bot message
    if message.author == client.user:
        return
    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)

    print(f'[{channel}] {username}: "{user_message}"')

    # check for audio message
    for attachment in message.attachments:
        if attachment.filename.endswith(('.mp3', '.wav')):
            data = await attachment.read()

            audio = AudioSegment.from_file(BytesIO(data))
            duration_sec = audio.duration_seconds
            if duration_sec > 10:
                # log who sent what
                print(f'{username} sent a song: {attachment.filename} ({duration_sec:.2f}s)')
                increment_user_song_count(str(message.author))
                increment_user_song_time(str(message.author), duration_sec)
                # save file to downloads!
                downloads_dir = Path('./downloads')
                downloads_dir.mkdir(exist_ok=True)
                save_path = downloads_dir / attachment.filename
                # await attachment.save(save_path)
                # print(f'Saved to {save_path}')
                duration_str = format_duration(duration_sec)
                # mwidmi
                # await message.channel.send(f"Song {attachment.filename} has been saved! ({duration_str})")

            else:
                await message.channel.send(f'Not a song')

    await send_message(message, user_message)


# main
def main() -> None:
    client.run(token=TOKEN)


if __name__ == '__main__':
    main()
