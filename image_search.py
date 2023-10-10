import time
import json
import requests
import os
import traceback
import utilityV2 as ut

cx = os.getenv("GOOGLE_IMAGE_CX")
gkey = os.getenv("GOOGLE_KEY")


def image_search(query):
    urls = []
    try:
        start_wall_time = time.time()
        url = (
            "https://www.googleapis.com/customsearch/v1?key="
            + gkey
            + "&source=lnms&searchType=image&cx="
            + cx
            + "&q="
            + query
        )
        response = requests.get(url)
        response_json = json.loads(response.text)
        # print(f'***** google search {int((time.time()-start_wall_time)*10)/10} sec')
        # print(json.dumps(response_json, indent=2))
        try:  # don't abort entire search just because of failure to handle one url
            for item in response_json["items"]:
                url = ""
                if "link" in item:
                    url = item["link"]
                    urls.append(url)
                    # webbrowser.get('google-chrome').open_new_tab(url)
                elif "image" in item:
                    url = item["image"]["thumbnailLink"]
                    urls.append(url)
                    # webbrowser.get('google-chrome').open_new_tab(url)
        except:
            traceback.print_exc()
    except:
        traceback.print_exc()
    return urls
