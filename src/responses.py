from insta import downloadShortcode, getShortcode, sendMedia

async def get_response(message):
    user_input = message.content
    shortcode = getShortcode(user_input)
    if(shortcode):
        downloadShortcode(shortcode)
        await sendMedia(shortcode, message)
