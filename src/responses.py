from insta import downloadShortcode, getShortcode, sendMedia

async def get_response(message):
    user_input = message.content
    shortcode = getShortcode(user_input)
    if not shortcode:
        return False

    try:
        downloadShortcode(shortcode)
        result = await sendMedia(shortcode, message)
        return result
    except Exception as e:
        print(f"Error processing Instagram post: {e}")
        return False
