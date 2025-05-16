import instaloader
import re
def getInstaPost(shortcode):
    if shortcode:
        L = instaloader.Instaloader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=shortcode)

def getShortcode(user_input):
    insta_pattern = r"^(https://www\.)?instagram\.com(/.*)?$"
    shortcode_pattern = r"^.*/(.*)/\?.*$"
    isInsta = True if re.search(insta_pattern, user_input) else False
    if isInsta:
        return re.search(shortcode_pattern, user_input).group(1)
    return ''

shortcode = getShortcode('https://www.instagram.com/reel/DHkb-M_tK9l/?igsh=am5wNHpiaTNxMm1x')
print(shortcode)
# getInstaPost(shortcode)