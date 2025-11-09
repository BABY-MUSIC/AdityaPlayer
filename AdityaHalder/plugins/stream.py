@bot.on_message(cdz(["play", "vplay"]) & ~filters.private)
async def start_stream_in_vc(client, message):
    try:
        await message.delete()
    except Exception:
        pass

    chat_id = message.chat.id
    mention = (
        message.from_user.mention
        if message.from_user
        else f"[Anonymous User](https://t.me/{bot.username})"
    )
    replied = message.reply_to_message
    audio_telegram = replied.audio or replied.voice if replied else None
    video_telegram = replied.video or replied.document if replied else None

    # ✅ Case 1: If replied to Telegram audio/video
    if audio_telegram or video_telegram:
        aux = await message.reply_text("**🔄 Processing ✨...**")
        if audio_telegram:
            id = audio_telegram.file_unique_id
            full_title = audio_telegram.title or audio_telegram.file_name
            ext = (
                (audio_telegram.file_name.split(".")[-1])
                if hasattr(audio_telegram, "file_name")
                else "ogg"
            )
            file_name = f"{id}.{ext}"
            duration_sec = audio_telegram.duration
            video_stream = False
        else:
            id = video_telegram.file_unique_id
            full_title = video_telegram.title or video_telegram.file_name
            ext = (video_telegram.file_name.split(".")[-1])
            file_name = f"{id}.{ext}"
            duration_sec = video_telegram.duration
            video_stream = True

        file_path = os.path.join("downloads", file_name)
        if not os.path.exists(file_path):
            await aux.edit("**⬇️ Downloading from Telegram ✨...**")
            await replied.download(file_name=file_path)

        title = full_title[:30]
        image_path = "AdityaHalder/resource/thumbnail.png"
        link = replied.link
        channel = message.chat.title
        channellink = (
            f"https://t.me/{message.chat.username}"
            if message.chat.username
            else "Telegram"
        )

    # ✅ Case 2: /play query
    else:
        if len(message.command) < 2:
            return await message.reply_text(
                "**🥀 Give me a song name to play!**\n\nExample:\n`/play believer`\n`/vplay believer`"
            )

        query = parse_query(" ".join(message.command[1:]))
        aux = await message.reply_text("**🔍 Searching...**")
        video_stream = True if message.command[0].startswith("v") else False

        search = VideosSearch(query, limit=1)
        result = (await search.next())["result"]
        if not result:
            return await aux.edit("❌ No results found.")

        video = result[0]
        full_title = video["title"]
        id = video["id"]
        duration = video["duration"]
        if not duration:
            return await aux.edit("❌ Live streams can't be played right now.")
        duration_sec = convert_to_seconds(duration)
        duration_mins = format_duration(duration_sec)
        image_path = video["thumbnails"][0]["url"].split("?")[0]
        channellink = video["channel"]["link"]
        channel = video["channel"]["name"]
        link = video["link"]
        title = full_title[:30]
        xyz = os.path.join("downloads", f"{id}.mp3")

        # 🔹 Fetch Telegram song link from API
        song_data = await fetch_song(query)
        if not song_data or "telegram_link" not in song_data:
            return await aux.edit("❌ Song not found in Telegram database.")

        song_url = song_data["telegram_link"]

        # 🎧 Step 1: Stream directly from Telegram (instant)
        await aux.edit("**🎧 Streaming instantly... please wait ✨**")

        try:
            c_username, message_id = parse_tg_link(song_url)
            msg = await client.get_messages(c_username, int(message_id))

            media_stream = (
                MediaStream(
                    media_path=msg.audio.file_id,
                    audio_parameters=AudioQuality.STUDIO,
                )
                if not video_stream
                else MediaStream(
                    media_path=msg.video.file_id,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.HD_720p,
                )
            )

            try:
                await call.start_stream(chat_id, media_stream)
                await aux.edit("**🎧 Streaming started — downloading locally...**")
            except NoActiveGroupCall:
                return await aux.edit("❌ No active VC found to stream.")
            except TelegramServerError:
                return await aux.edit("⚠️ Telegram server error, try again shortly.")
        except Exception as e:
            return await aux.edit(f"❌ Failed to start stream: `{e}`")

        # 🎵 Step 2: Sequential file download (no background / futures)
        try:
            await msg.download(file_name=xyz)
            print(f"✅ Downloaded successfully: {xyz}")
        except Exception as e:
            print(f"⚠️ Download failed: {e}")

        file_path = xyz

    # ✅ Continue with queue system & thumbnail
    media_stream = (
        MediaStream(
            media_path=file_path,
            video_flags=MediaStream.Flags.IGNORE,
            audio_parameters=AudioQuality.STUDIO,
        )
        if not video_stream
        else MediaStream(
            media_path=file_path,
            audio_parameters=AudioQuality.STUDIO,
            video_parameters=VideoQuality.HD_720p,
        )
    )

    image_file = await generate_thumbnail(image_path)
    thumbnail = await make_thumbnail(
        image_file, full_title, channel, duration_sec, f"cache/{chat_id}_{id}_{message.id}.png"
    )

    pos = await call.add_to_queue(chat_id, media_stream, title, format_duration(duration_sec), thumbnail, mention)
    status = "✅ **Started Streaming in VC.**" if pos == 0 else f"✅ **Added To Queue At: #{pos}**"
    caption = f"""
{status}

**❍ Title:** [{title}...]({link})
**❍ Duration:** {format_duration(duration_sec)}
**❍ Requested By:** {mention}"""

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="🗑️ Close", callback_data="close")]]
    )

    try:
        await aux.delete()
        await message.reply_photo(photo=thumbnail, caption=caption, has_spoiler=True, reply_markup=buttons)
    except:
        pass

    if chat_id != console.LOG_GROUP_ID:
        try:
            chat_name = message.chat.title
            if message.chat.username:
                chat_link = f"@{message.chat.username}"
            elif chat_id in console.chat_links:
                clink = console.chat_links[chat_id]
                chat_link = f"[Private Chat]({clink})"
            else:
                try:
                    new_link = await client.export_chat_invite_link(chat_id)
                    console.chat_links[chat_id] = new_link
                    chat_link = f"[Private Chat]({new_link})"
                except Exception:
                    chat_link = "N/A"
        

            if message.from_user:
                if message.from_user.username:
                    req_user = f"@{message.from_user.username}"
                else:
                    req_user = message.from_user.mention
                user_id = message.from_user.id
            elif message.sender_chat:
                if message.sender_chat.username:
                    req_user = f"@{message.sender_chat.username}"
                else:
                    req_user = message.sender_chat.title
                user_id = message.sender_chat.id
            else:
                req_user = "Anonymous User"
                user_id = "N/A"

            stream_type = "Audio" if not video_stream else "Video"

            log_message = f"""
🎉 **{mention} Just Played A Song.**

📍 **Chat:** {chat_name}
💬 **Chat Link:** {chat_link}
♂️ **Chat ID:** {chat_id}
👤 **Requested By:** {req_user}
🆔 **User ID:** `{user_id}`
🔎 **Query:** {query}
🎶 **Title:** [{title}...]({link})
⏱️ **Duration:** {duration_mins}
📡 **Stream Type:** {stream_type}"""
            await bot.send_photo(console.LOG_GROUP_ID, photo=thumbnail, caption=log_message)
        except Exception:
            pass



















