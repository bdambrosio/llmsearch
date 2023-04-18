A simple web search tool with Pre and Post search filtering.
Why? LLMs need to be able to access the web efficiently.

llmsearch features:
1. Uses an LLM to rewrite the query for better search results.
2. Uses the google customized search API to collect urls.
3. Filters and prioritizes urls by local whitelist/unknown/blacklist, and also by past history of usefulness
4. Uses concurrent futures to process urls in parallel.
5. Preprocesses url returns to extract a minimal piece of candidate text to send to gpt for final refinement.
6. Stops when sufficient results are accumulated (three levels - Quick Search, Normal, Deep Search)
7. As a plugin or direct call, returns json format including result, domain, url, and credibility (see chatGPT screenshot below).

Three ways to use this:
       1. Can be used as a chatGPT plugin (if you are a plugin developer)
       2. Can be used as a standalone command line search tool python3 search_engine.py
       3. Can be called from within an application: import, then call search_service.from_gpt(query_string)

You will need google customized search api key and your google cx.

You will also need an openai api.key
llmsearch currently uses gpt-3.5-turbo internally, so its reasonably cheap for personal use, usually a few tents of a cent per top-level query.
I expect to release an update shortly that will enable use of Vicuna, maybe 7B 4bit if possible.
Screen shot of chatGPT session with plugin installed:

![plugin](https://user-images.githubusercontent.com/2271133/232800682-9864cea3-7cea-4e4c-927f-fa2f715e270a.jpg)

NOTES:
I am a 'quick sketch' research programmer. Careful methodical programmers will probably be horrified with the code in this repository.
*** If you are one such and have suggestions/edits, I'd love your contributions! ***
Having said that, I use this code base every day, all day long, as a chatGPT plugin. Pretty much the only failures I have seen are when the interall api calls to gpt-3.5-turbo timeout. There is quite a bit of recovery code around those, they are rare except when openai is swamped.

INSTALLATION:
1. clone the repository
2. pip3 install -r requirements.txt
3. add your openai.api_key either as an evironment var or directly in utilityV2.py
4. add your google credentials either as environment vars or directly in google_search_concurrent.py

to test, try:
python3 search_service.py

you should see:

Yes?

To run as a gptPlugin (assuming you are a plugin developer) run:
python3 main.py

Note that you will need to edit openapi.yaml and .well-known/ai-plugin.json, as well as setting the corresponding site info in main.py

This actually starts up a pretty std web server you can actually even call from your browser. lookup openapi.yaml for more on configuration options, I just copy-pasted.

That should do it.


<B>Site curation and prioritization</B>
1. the file contains a json formatted list of sites (next to last portion of domain name, usually).
2. At the moment there is no api to manage this list, but you can manually edit it.
       * a '1' means a site is whitelisted. a '0' means a site is blacklisted, and any urls for that site returned by google will be ignored.
       * a site not listed in sites.json is considered 'Third Party' (a chatGPT recommended term, not mine).
3. All whitelist site urls will be launched before any Third Party site urls.
4. url launch order is futher prioritized by 'site_state.json', a record of the average post-filtering bytes per second the site has delivered in previous queries.

In deciding what to whitelist or blacklist, you might want to review the site_stats.
An easy way to do this is to run python3 show_site_stats.py
show_site_stats.py accepts one optional argument: [new, all]
'new' shows only sites not listed in sites.json (so you can decide if you want to whitelist them)
