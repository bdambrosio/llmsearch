import json
import search_service
import image_search
import quart
import quart_cors
from quart import request
import google_search_concurrent as gs
import requests

app = quart_cors.cors(quart.Quart(__name__), allow_origin="*")

# This key can be anything, though you will likely want a randomly generated sequence.
_SERVICE_AUTH_KEY = "0123456788abcdef"

# def assert_auth_header(req):
#    assert req.headers.get(
#        "Authorization", None) == f"Bearer {_SERVICE_AUTH_KEY}"


@app.get("/search/quick")
async def get_quicksearch():
    level = "quick"
    search_result = ""
    try:
        query = request.args.get("query")
        print(f"level: {level}, query: {query}")
        search_result = search_service.run_chat(query, level)
    except:
        traceback.print_exc()
    return quart.Response(
        response=json.dumps(
            {
                "response": search_result,
                "credibility_definitions": {
                    "Official Source": "Source is a government agency.",
                    "Whitelisted Source": "Source is approved in your curation list.",
                    "Third-Party Source": "Source does not appear in your curation list and may have varying levels of reliability.",
                    "Blacklisted Source": "Source has been explicitly banned in your curation list.",
                },
            }
        ),
        status=200,
    )


@app.get("/search/full")
async def get_fullsearch():
    level = "moderate"
    search_result = ""
    try:
        query = request.args.get("query")
        print(f"level: {level}, query: {query}")
        search_result = search_service.run_chat(query, level)
    except:
        traceback.print_exc()
    return quart.Response(
        response=json.dumps(
            {
                "response": search_result,
                "credibility_definitions": {
                    "Official Source": "Source is a government agency.",
                    "Whitelisted Source": "Source is approved in your curation list.",
                    "Third-Party Source": "Source does not appear in your curation list and may have varying levels of reliability.",
                    "Blacklisted Source": "Source has been explicitly banned in your curation list.",
                },
            }
        ),
        status=200,
    )


@app.get("/search/image")
async def get_image():
    level = "moderate"
    search_result = ""
    try:
        query = request.args.get("query")
        print(f"level: {level}, query: {query}")
        search_result = image_search.image_search(query)
    except:
        traceback.print_exc()
    return quart.Response(
        response=json.dumps(
            {
                "response": search_result,
            }
        ),
        status=200,
    )


@app.get("/logo.png")
async def plugin_logo():
    filename = "logo.png"
    return await quart.send_file(filename, mimetype="image/png")


@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    # host = request.headers['Host']
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")


@app.get("/openapi.yaml")
async def openapi_spec():
    # host = request.headers['Host']
    with open("openapi.yaml") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/yaml")


# def main():
#    app.run(debug=True, host="0.0.0.0", port=443)

# if __name__ == "__main__":
#    main()
