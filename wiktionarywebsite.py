from flask import Flask, request, render_template_string
import re 
import chinese_converter 
from bs4 import BeautifulSoup
import unicodedata
import asyncio
import aiohttp
import os

def dialect_converter(dialect):
    dialect = dialect.title()
    match dialect:
        case "Mandarin":
            dialect = "Mandarin Chinese"
        case "Cantonese"|"Guangdong":
            pass
        case "Gan"|"Jiangxi":
            dialect = "Gan Chinese"
        case "Hakka"|"Khek"|"Kejia":
            dialect = "Hakka Chinese"
        case "Jin":
            dialect = "Jin Chinese"
        case "Northern Min"|"Kienow"|"Kienning"|"Minbei":
            dialect = "Northern Min"
        case "Eastern Min"|"Fuzhounese"|"Fuzhou"|"Foochow"|"Hokchew"|"Hokciu"|"Hukciu"|"Mindong":
            dialect = "Eastern Min"
        case "Hinghwa"|"Putian"|"Henghwa":
            dialect = "Puxian Min"
        case "Hokkien"|"Taiwanese"|"Minnan"|"Amoy":
            dialect = "Southern Min"
        case "Wu"|"Shanghainese":
            dialect = "Wu Chinese"
        case "Xiang"|"Hunan":
            dialect = "Xiang Chinese"
        case _:
            raise ValueError
    return dialect
def validate(characters):
    characters = re.sub(r'\s+', '', characters)
    for character in characters:
        if not (re.match(r'[\u4e00-\u9fff]', character) or unicodedata.category(character).startswith('P')):
            raise ValueError
    characters = chinese_converter.to_traditional(characters)
    return characters
async def wiktionary_async(session, character, dialect, mode):
    print(character)
    title = f"w:{dialect}"
    url = f"https://en.wiktionary.org/w/api.php?action=parse&prop=text&format=json&page={character}"
    try:
        async with session.get(url) as response:
            if response.status != 200:
                return character, " (No Info) "
            html_doc = await response.json()
            extractor = BeautifulSoup(str(html_doc['parse']['text']), "html.parser")
            if mode == "romanisation":
                try:
                    return character, extractor.find_all(class_ = "standard-box zhpron")[0].find_all(attrs = {"title": title}, limit = 1)[0].find_parent().find("span").text
                except IndexError: 
                    return character, " (No Info) "
            elif mode == "ipa":
                try:
                    return character, extractor.find_all(class_ = "standard-box zhpron")[0].find_all(attrs = {"title": title}, limit = 2)[1].find_parent().find_all("span", class_ = "IPA", limit = 1)[0].text
                except IndexError: 
                    return character, " (No Info) "
    except Exception as e:
        return character, " (No Info) "
                
async def fetch_all(characters, dialect, mode):
    async with aiohttp.ClientSession() as session:
        tasks = [
            wiktionary_async(session, character, dialect, mode)
            for character in characters if not unicodedata.category(character).startswith('P')
        ]
        return await asyncio.gather(*tasks)
    
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    if request.method == 'POST':
        dialect = request.form.get('dialect', '')
        mode = request.form.get('mode', '').lower()
        characters = request.form.get('characters', '')
        try:
            dialect = dialect_converter(dialect.strip())
            if mode not in ['romanisation', 'ipa']:
                raise ValueError("Invalid mode")
            characters = validate(characters.strip())
            altprons = []
            output = []
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(fetch_all(characters, dialect, mode))
            for orchar, rawpronounciation in results:
                if mode == "romanisation":
                    pronounciation = rawpronounciation.split("/")
                else:
                    pronounciation = rawpronounciation.split(", ")
                    pronounciation = [p[1:-1] for p in pronounciation]
                altpron = [f"{orchar}:{pronounciation[i]} " for i in range(1, len(pronounciation))]
                altprons.append(" ".join(altpron))
                output.append(pronounciation[0])
            output.append("|| Alternative Pronounciations: " + " ".join(altprons))
            result = " ".join(output)
        except Exception as e:
            result = f"Error: {e}"
    return render_template_string('''
        <form method="post">
            Dialect: <input name="dialect"><br>
            Romanisation or IPA: <input name="mode"><br>
            Characters: <input name="characters"><br>
            <input type="submit">
        </form>
        <div>{{result|safe}}</div>
    ''', result=result)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
