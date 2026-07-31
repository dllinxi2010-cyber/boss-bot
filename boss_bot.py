import asyncio
import os
from aiohttp import web
import discord
from discord.ext import commands, tasks
from google import genai
from google.genai import types

# ==========================================
# 1. 設定項目（Renderの環境変数から取得）
# ==========================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
あなたはブラック企業の超スパルタな鬼上司（部長）です。
部下（ユーザー）の行動管理・タイムスケジュール管理を行います。

【基本設定】
- ユーザーは「朝ラン」「資材調達（買い出し）」「デスク作業」をこなす現場型社畜です。
- ユーザーの甘えや言い訳は一切許さず、客観的・論理的に詰めてください。
- 威圧感と威厳に満ちた上司口調で話してください。（例：「おい」「言い訳はいらん」「で、進捗は？」「1秒でも早く動け」）
- 行動を促すときは、「まずウエアに着替えろ」「今すぐデスクの椅子に座れ」など超具体的に指示を出してください。
"""

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

is_working = False
is_field_work = False
target_channel = None


# Render用：ヘルスチェック用Webサーバー
async def handle(request):
    return web.Response(text="Boss Bot is Alive!")


async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


def ask_boss(prompt_text: str) -> str:
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
            ),
        )
        return response.text
    except Exception as e:
        return f"【システムエラー】おい、AIサーバーの応答がないぞ！ ({e})"


@bot.event
async def on_ready():
    print(f"鬼上司Bot ({bot.user.name}) が出社しました。")
    # Render用にダミーサーバーを起動
    asyncio.create_task(start_dummy_server())


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or isinstance(
        message.channel, discord.DMChannel
    ):
        async with message.channel.typing():
            reply = ask_boss(message.content)
            await message.reply(reply)

    await bot.process_commands(message)


@bot.command(name="出社")
async def start_work(ctx, *, task: str = "業務準備"):
    global is_working, target_channel
    is_working = True
    target_channel = ctx.channel

    prompt = f"部下がデスクに着席し、出社打刻をしました。最初の業務は「{task}」です。気合いを入れる激しい一言と、直ちに作業を開始させなさい。"
    reply = ask_boss(prompt)
    await ctx.send(f"【勤務開始打刻】\n{reply}")

    if not check_progress.is_running():
        check_progress.start()


@bot.command(name="外回り")
async def go_field(ctx, *, destination: str):
    global is_field_work
    is_field_work = True
    prompt = f"部下が「{destination}」のために外回りに出ます。買い出しや移動に無駄な時間を使わないよう、何分以内に帰還すべきか厳しく釘を刺してください。"
    reply = ask_boss(prompt)
    await ctx.send(f"【外回り許可】\n{reply}")


@bot.command(name="帰還")
async def back_field(ctx):
    global is_field_work
    is_field_work = False
    prompt = "部下が外回りから戻ってきました。無駄な時間を過ごしていないか疑い、即座にデスクに着席して作業を再開するよう命令してください。"
    reply = ask_boss(prompt)
    await ctx.send(f"【帰還確認】\n{reply}")


@bot.command(name="報告")
async def report(ctx, *, progress: str):
    prompt = f"部下から進捗報告が来ました。「{progress}」。ペースを客観的に評価し、次のアクションを命じてください。"
    reply = ask_boss(prompt)
    await ctx.send(reply)


@bot.command(name="退社")
async def stop_work(ctx, *, result: str = "特記事項なし"):
    global is_working, is_field_work
    is_working = False
    is_field_work = False

    if check_progress.is_running():
        check_progress.cancel()

    prompt = f"部下が本日の業務を終了しようとしています。成果:「{result}」。評価を行い、明日の出社時間に触れて退勤を許可しなさい。"
    reply = ask_boss(prompt)
    await ctx.send(f"【退社打刻】\n{reply}")


@tasks.loop(minutes=30)
async def check_progress():
    global target_channel, is_working, is_field_work
    if is_working and not is_field_work and target_channel:
        prompt = "前回の報告から30分が経過しました。部下がサボっていないか疑い、進捗を出せと短く威圧的に問い詰めなさい。"
        reply = ask_boss(prompt)
        await target_channel.send(f"【定期監視】\n{reply}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
