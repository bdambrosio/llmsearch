import json
import search_service
import quart
import quart_cors
from quart import request

app = quart_cors.cors(quart.Quart(__name__), allow_origin="https://chat.openai.com")

@app.get("/search/<string:query>")
async def get_search(query):
    search_result = search_service.run_chat(query)
    print(json.dumps(search_result, indent=2))
    return quart.Response(response=json.dumps({'response':search_result,
    "credibility_definitions": {
    "Official Source": "Source is a government agency.",
    "Whitelisted Source": "Source is approved in your curation list.",
    "Third-Party Source": "Source does not appear in your curation list and may have varying levels of reliability.",
    "Blacklisted Source": "Source has been explicitly banned in your curation list."},
                                               'input': 'Search for RTX 4070Ti reviews.'
                                               }), status=200)

@app.get("/logo.png")
async def plugin_logo():
    filename = 'logo.png'
    return await quart.send_file(filename, mimetype='image/png')

@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    host = request.headers['Host']
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")

@app.get("/openapi.yaml")
async def openapi_spec():
    host = request.headers['Host']
    with open("openapi.yaml") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/yaml")

def main():
    app.run(debug=True, host="0.0.0.0", port=5003)

if __name__ == "__main__":
    main()
