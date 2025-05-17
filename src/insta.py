import instaloader
import re
import os
import discord
import shutil

def getShortcode(user_input):
    pattern = r'https?:\/\/(?:www\.)?instagram\.com\/[^\/]+(?:\/[^\/]+)?\/([^\/]{11})\/.*'
    match = re.search(pattern, user_input)
    if match:
        shortcode = match.group(1)
        return shortcode
    else:
        return None

def downloadShortcode(shortcode):
    L = instaloader.Instaloader()
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=shortcode)

async def sendMedia(shortcode, message):
    for filename in os.listdir(shortcode):
        if filename[-3:] == 'mp4':
            with open(f'{shortcode}/{filename}', 'rb') as f:
                file = discord.File(f)
                await message.reply(file=file)
            shutil.rmtree(shortcode)
            return
    for filename in os.listdir(shortcode):
        if filename[-3:] == 'jpg':
            with open(f'{shortcode}/{filename}', 'rb') as f:
                file = discord.File(f)
                await message.reply(file=file)
            shutil.rmtree(shortcode)
            return