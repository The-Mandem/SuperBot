import re
import instaloader
import os
import discord
import shutil

def getInstaPost(shortcode):
    if shortcode:
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=shortcode)

def getShortcode(user_input):
    # insta_pattern = r"(https://www\.)?instagram\.com(/.*)?"
    # shortcode_pattern = r".*/(.*)/\?.*"
    tester = 'https?:\/\/(?:www\.)?instagram\.com\/[^\/]+(?:\/[^\/]+)?\/([^\/]{11})\/.*'
    # isInsta = True if re.search(insta_pattern, user_input) else False

    return re.search(tester, user_input).group(1)

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

async def get_response(message):
    user_input = message.content
    shortcode = getShortcode(user_input)
    getInstaPost(shortcode)
    await sendMedia(shortcode, message)
    


        