import instaloader
import re
import os
import discord
import shutil

def getInstaPost(shortcode):
    if shortcode:
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=shortcode)

def getShortcode(user_input):
    pattern = 'https?:\/\/(?:www\.)?instagram\.com\/[^\/]+(?:\/[^\/]+)?\/([^\/]{11})\/.*'
    return re.search(pattern, user_input).group(1)

async def sendMedia(shortcode, message):
    if shortcode:
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