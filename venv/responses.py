from insta import getInstaPost, getShortcode, sendMedia

async def get_response(message):
    user_input = message.content
    shortcode = getShortcode(user_input)
    getInstaPost(shortcode)
    await sendMedia(shortcode, message)
    


        