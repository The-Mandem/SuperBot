import instaloader
import re
import os
import discord
import shutil
import ffmpeg
from discord.ext import commands
from discord import Message
from utils import ignore_channel_in_prod


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

    def _compress_video(self, input_path: str, target_size_mb: float) -> str | None:
        """Compresses a video to a target size using two-pass ffmpeg encoding."""
        output_path = f"{os.path.splitext(input_path)[0]}_compressed.mp4"
        # Target a size slightly below the limit for a margin of error
        target_size_bytes = (target_size_mb - 0.2) * 1024 * 1024
        log_file_prefix = os.path.join(
            os.path.dirname(input_path), f"ffmpeg_log_{os.path.basename(input_path)}"
        )

        try:
            # Get video duration to calculate the required bitrate
            probe = ffmpeg.probe(input_path)
            duration = float(probe["format"]["duration"])

            # Calculate target bitrates for two-pass encoding
            audio_bitrate = 128 * 1024  # 128k
            target_total_bitrate = (target_size_bytes * 8) / duration
            # Ensure target video bitrate is a positive number
            target_video_bitrate = max(1, target_total_bitrate - audio_bitrate)

            if target_video_bitrate <= 1:
                print(
                    f"Instagram Feature: Compression failed. Target bitrate ({target_video_bitrate}) is too low for {input_path}."
                )
                return None

            print(
                f"Instagram Feature: Compressing {input_path}. Target video bitrate: {target_video_bitrate / 1024:.0f} kb/s"
            )

            # Pass 1
            ffmpeg.input(input_path).output(
                "nul" if os.name == "nt" else "/dev/null",
                vcodec="libx264",
                passlogfile=log_file_prefix,
                **{"pass": 1, "f": "mp4", "b:v": target_video_bitrate},
            ).run(cmd="ffmpeg", quiet=True, overwrite_output=True)

            # Pass 2
            ffmpeg.input(input_path).output(
                output_path,
                vcodec="libx264",
                passlogfile=log_file_prefix,
                **{
                    "pass": 2,
                    "c:a": "aac",
                    "b:a": f"{int(audio_bitrate / 1024)}k",
                    "b:v": target_video_bitrate,
                },
            ).run(cmd="ffmpeg", quiet=True, overwrite_output=True)

            final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            if final_size_mb > target_size_mb:
                print(
                    f"Instagram Feature: Compression finished, but file is still too large ({final_size_mb:.2f}MB)."
                )
                os.remove(output_path)
                return None

            print(
                f"Instagram Feature: Compression successful. New file: {output_path} ({final_size_mb:.2f}MB)"
            )
            return output_path

        except ffmpeg.Error as e:
            print(
                f"Instagram Feature: ffmpeg error during compression of {input_path}: {e.stderr.decode()}"
            )
            if os.path.exists(output_path):
                os.remove(output_path)
            return None
        except Exception as e:
            print(
                f"Instagram Feature: An unexpected error occurred during compression of {input_path}: {e}"
            )
            if os.path.exists(output_path):
                os.remove(output_path)
            return None
        finally:
            # Clean up ffmpeg log files
            for file in os.listdir(os.path.dirname(input_path)):
                if file.startswith(os.path.basename(log_file_prefix)):
                    try:
                        os.remove(os.path.join(os.path.dirname(input_path), file))
                    except OSError:
                        pass  # Ignore if file is already gone

    async def _send_media(self, shortcode: str, original_message: Message):
        """Sends downloaded media to Discord, compressing if necessary."""
        media_dir = shortcode
        if not os.path.exists(media_dir) or not os.path.isdir(media_dir):
            print(
                f"Instagram Feature: Media directory '{media_dir}' not found for shortcode {shortcode}."
            )
            return False

        sent_media = False
        video_files = sorted([f for f in os.listdir(media_dir) if f.endswith(".mp4")])
        image_files = sorted(
            [f for f in os.listdir(media_dir) if f.endswith((".jpg", ".jpeg", ".png"))]
        )
        files_to_upload_paths = []

        if video_files:
            files_to_upload_paths.append(os.path.join(media_dir, video_files[0]))
        elif image_files:
            for img_file in image_files:
                files_to_upload_paths.append(os.path.join(media_dir, img_file))

        if not files_to_upload_paths:
            print(
                f"Instagram Feature: No suitable media files found in '{media_dir}' for {shortcode}."
            )

        for file_path in files_to_upload_paths:
            try:
                with open(file_path, "rb") as f:
                    discord_file = discord.File(f)
                    await original_message.reply(file=discord_file)
                sent_media = True
            except discord.errors.HTTPException as e:
                if e.status == 413:  # Payload too large
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

                    # Only attempt to compress video files
                    if file_path.lower().endswith(".mp4"):
                        DISCORD_LIMIT_MB = 8.0
                        status_msg = await original_message.reply(
                            f"The video is too large ({file_size_mb:.2f}MB). Trying to compress it to fit under {DISCORD_LIMIT_MB}MB, please wait..."
                        )

                        # Run blocking compression in an executor
                        compressed_path = await self.bot.loop.run_in_executor(
                            None, self._compress_video, file_path, DISCORD_LIMIT_MB
                        )

                        if compressed_path:
                            try:
                                compressed_size_mb = os.path.getsize(
                                    compressed_path
                                ) / (1024 * 1024)
                                with open(compressed_path, "rb") as f:
                                    # Preserve original filename for user
                                    discord_file = discord.File(
                                        f, filename=os.path.basename(file_path)
                                    )
                                    await original_message.reply(
                                        f"Compressed to {compressed_size_mb:.2f}MB. Here's the video:",
                                        file=discord_file,
                                    )
                                sent_media = True
                            except Exception as e_comp:
                                print(
                                    f"Instagram Feature: Failed to send compressed file {compressed_path}: {e_comp}"
                                )
                                await original_message.reply(
                                    f"Sorry, I compressed the video but still couldn't upload it. "
                                    f"You can view the original here: `https://www.instagram.com/p/{shortcode}/`"
                                )
                            finally:
                                # Delete the "compressing..." message
                                await status_msg.delete()
                        else:
                            # Compression failed
                            await status_msg.delete()
                            await original_message.reply(
                                f"Sorry, I couldn't compress the video down to a sendable size. "
                                f"You can view it here: `https://www.instagram.com/p/{shortcode}/`"
                            )
                    else:
                        # Image or other non-video file is too large
                        await original_message.reply(
                            f"Sorry, a media file from the Instagram post is too large to upload to Discord ({file_size_mb:.2f}MB). "
                            f"Discord's limit for bots is 8MB. "
                            f"You can view it here: `https://www.instagram.com/p/{shortcode}/`"
                        )
                else:
                    print(
                        f"Instagram Feature: Discord HTTP error sending file {file_path}: {e}"
                    )
                    await original_message.reply(
                        f"Sorry, I encountered a Discord error trying to send the media for `https://www.instagram.com/p/{shortcode}/`."
                    )
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

    @ignore_channel_in_prod()
    async def on_instagram_message(self, message: Message):
        """Listener for messages, checks for Instagram links."""
        if message.author == self.bot.user:
            return  # Ignore messages from the bot itself

        if message.content.startswith(self.bot.command_prefix):  # type: ignore
            return

        shortcode = self._get_shortcode(message.content)
        if not shortcode:
            return

        print(
            f"Instagram Feature: Detected Instagram shortcode '{shortcode}' from {message.author.name}"
        )

        status_message = None
        try:
            status_message = await message.channel.send(
                f"Processing Instagram link for {message.author.mention}..."
            )

            download_successful = await self.bot.loop.run_in_executor(
                None, self._download_shortcode, shortcode
            )

            if not download_successful:
                if os.path.exists(shortcode):
                    shutil.rmtree(shortcode)
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
            if os.path.exists(shortcode):
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
