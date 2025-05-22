import instaloader
import re
import os
import discord
import shutil
from discord.ext import commands
from discord import Message


class InstagramFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_shortcode(self, user_input: str) -> str | None:
        """Extracts Instagram shortcode from a URL."""
        # Pattern to find shortcode in various Instagram URL formats
        pattern = r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]{11})"
        match = re.search(pattern, user_input)
        return match.group(1) if match else None

    def _download_shortcode(self, shortcode: str) -> bool:
        """Downloads media for a given Instagram shortcode."""
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",  # Avoid .txt files
        )
        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            # Download to a directory named after the shortcode
            L.download_post(post, target=shortcode)
            return True
        except instaloader.exceptions.ProfileNotExistsException:
            print(
                f"Instagram Feature: Profile for post {shortcode} does not exist or is private."
            )
            return False
        except instaloader.exceptions.ConnectionException as e:
            if "Too Many Requests" in str(e) or "429" in str(e):
                print(
                    f"Instagram Feature: Rate limited by Instagram for {shortcode}. Try again later."
                )
            else:
                print(
                    f"Instagram Feature: Connection error downloading post {shortcode}: {e}"
                )
            return False
        except instaloader.exceptions.PrivateProfileNotFollowedException:
            print(
                f"Instagram Feature: Cannot download {shortcode}, profile is private and not followed."
            )
            return False
        except Exception as e:
            print(
                f"Instagram Feature: An unexpected error occurred while downloading post {shortcode}: {e}"
            )
            return False

    async def _send_media(self, shortcode: str, original_message: Message):
        """Sends downloaded media to Discord."""
        media_dir = shortcode
        if not os.path.exists(media_dir) or not os.path.isdir(media_dir):
            print(
                f"Instagram Feature: Media directory '{media_dir}' not found for shortcode {shortcode}."
            )
            # await original_message.reply(f"Sorry, I couldn't find the downloaded media for that Instagram post.")
            return False

        sent_media = False

        # Collect video and image files
        video_files = sorted([f for f in os.listdir(media_dir) if f.endswith(".mp4")])
        image_files = sorted(
            [f for f in os.listdir(media_dir) if f.endswith((".jpg", ".jpeg", ".png"))]
        )

        files_to_upload_paths = []

        if video_files:
            # Prioritize video, send only the first one found
            files_to_upload_paths.append(os.path.join(media_dir, video_files[0]))
        elif image_files:
            # If no video, send all images (Discord allows up to 10 attachments per message if sent as a list)
            # However, to handle >10 images and simplify, we send one by one as replies.
            for img_file in image_files:
                files_to_upload_paths.append(os.path.join(media_dir, img_file))

        if not files_to_upload_paths:
            print(
                f"Instagram Feature: No suitable media files (mp4, jpg, jpeg, png) found in '{media_dir}' for {shortcode}."
            )
            # await original_message.reply(f"I downloaded the post, but couldn't find displayable media (video/image).")
            # Fall through to cleanup

        for file_path in files_to_upload_paths:
            try:
                with open(file_path, "rb") as f:
                    discord_file = discord.File(f)
                    await original_message.reply(file=discord_file)
                sent_media = True
            except discord.errors.HTTPException as e:
                if e.status == 413:  # Payload too large
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    await original_message.reply(
                        f"Sorry, a media file from the Instagram post is too large to upload to Discord ({file_size_mb:.2f}MB). "
                        f"Discord's limit is typically 25MB (or 8MB for non-Nitro bots in some cases). "
                        f"You can view it here: `https://www.instagram.com/p/{shortcode}/`"
                    )
                else:
                    print(
                        f"Instagram Feature: Discord HTTP error sending file {file_path}: {e}"
                    )
                    await original_message.reply(
                        f"Sorry, I encountered a Discord error trying to send the media for `https://www.instagram.com/p/{shortcode}/`."
                    )
                # If one file fails, we might want to stop or continue with others.
                # For simplicity, we continue.
            except Exception as e:
                print(f"Instagram Feature: Error sending file {file_path}: {e}")
                await original_message.reply(
                    f"Sorry, I encountered an unexpected error trying to send the media for `https://www.instagram.com/p/{shortcode}/`."
                )

        # Cleanup
        if os.path.exists(media_dir):
            try:
                shutil.rmtree(media_dir)
            except Exception as e:
                print(f"Instagram Feature: Error removing directory {media_dir}: {e}")

        return sent_media

    async def on_instagram_message(self, message: Message):
        """Listener for messages, checks for Instagram links."""
        if message.author == self.bot.user:
            return  # Ignore messages from the bot itself

        # Do not process commands as Instagram links
        if message.content.startswith(self.bot.command_prefix):  # type: ignore
            return

        shortcode = self._get_shortcode(message.content)
        if not shortcode:
            return  # Not a recognized Instagram link

        print(
            f"Instagram Feature: Detected Instagram shortcode '{shortcode}' from {message.author.name}"
        )

        status_message = None
        try:
            status_message = await message.channel.send(
                f"Processing Instagram link for {message.author.mention}..."
            )

            # Run blocking download in an executor
            download_successful = await self.bot.loop.run_in_executor(
                None, self._download_shortcode, shortcode
            )

            if not download_successful:
                # Error messages are printed in _download_shortcode
                # Optionally, send a message to the user.
                # await message.reply(f"Could not download the Instagram post: `https://www.instagram.com/p/{shortcode}/`. It might be private, deleted, or I encountered an error.")
                if os.path.exists(
                    shortcode
                ):  # Cleanup if download failed but created directory
                    shutil.rmtree(shortcode)
                # if status_message: await status_message.delete()
                return

            await self._send_media(shortcode, message)
            if status_message:
                await status_message.delete()

        except Exception as e:
            print(
                f"Instagram Feature: General error processing Instagram post {shortcode}: {e}"
            )
            await message.reply(
                f"Sorry, an unexpected error occurred while processing the Instagram link: `https://www.instagram.com/p/{shortcode}/`."
            )
            if os.path.exists(shortcode):  # Ensure cleanup on error
                shutil.rmtree(shortcode)
            if status_message:
                try:
                    await status_message.delete()
                except discord.errors.NotFound:
                    pass

    async def setup(self):
        """Sets up the Instagram feature by adding message listener."""
        self.bot.add_listener(self.on_instagram_message, "on_message")
        print("Instagram feature loaded and message listener registered.")
