llmsearch

V1.1 - Now with image search too! just ask chatGPT for an image or picture. Note: default return is 10. If that takes too long to display, just tell gpt how many images you want. e.g.:  
find 3 images of Stanford University  
It still actually gets 10 urls, so you can probably just ask it to display 3 more ...

Release 1.0 now here! 
Release 1.0 is designed as a single-user version of web search for LLMs, with a single global curation file, and no tools for editting it (use your favorite text editor on sites.json)

A simple web search tool / endpoint with Pre and Post search processsing.  
Why? LLMs need to be able to access the web efficiently.  
non-LLM chatbots might want text access to a curated set of websites

llmsearch features:
1. Uses an LLM to rewrite the query for better search results.
2. Uses the google customized search API to collect urls.
3. Filters and prioritizes urls by local whitelist/unknown/blacklist, and by past history of usefulness
4. Uses concurrent futures to process urls in parallel.
5. Preprocesses url returns to extract a minimal piece of candidate text to send to gpt-3.5 for final refinement.
6. Stops when sufficient results are accumulated (two levels - Quick and Full)
7. As a plugin or direct call it returns json format including result, domain, url, and credibility (see chatGPT screenshot below).

Four ways to use this:
1. as a chatGPT plugin (if you are a plugin developer)
2. as a network endpoint for your application
3. as a standalone command line search tool 'python3 search_service.py'
4. directly from within a python application: import search_service, then call search_service.from_gpt(query_string, search_level)

You will need google customized search api key and your google cx.

You will also need an openai api.key.

llmsearch currently uses gpt-3.5-turbo internally, so its reasonably cheap for personal use, usually a few tenths of a cent per top-level query.  
I expect to release an update shortly that will enable use of Vicuna, maybe 7B 4bit if possible.  
*** update - this is stacked behind the llm server I'm building, cloud resources are too hard to find and cpu inference is too slow ***  
*** update2 - even 7B is too slow with a single 3090. Will be moving up to dual 3090, maybe if I lower the number of samples.***


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
This actually starts up a pretty std web endpoint you can actually even call from your browser. lookup openapi.yaml for more on configuration options, I just copy-pasted.  
The endpoint returns json with source, url, response, and credibility keys. 

That should do it.


<B>Site curation and prioritization</B>  
1. the file *sites* contains a json formatted list of sites (next to last portion of domain name, e.g. *openai*,  usually).
2. At the moment there is no api to manage this list, but you can manually edit it. A site not listed in sites.json is considered 'Third Party' (a chatGPT recommended term, not mine).
3. All whitelist site urls will be launched before any Third-Party site urls.
4. url launch order is futher prioritized by *site_stats.json*, a record of the average post-filtering bytes per second the site has delivered in previous queries.
5. comes by default with unlisted sites ok to search.  
If you want whitelisted only, look in google_search_concurrent.py in the search def for a line like 'if site not in sites or sites[site]==1' and change it to 'if site in sites and sites[site]==1'. I'll add a config file and make that a config option someday...

In deciding what to whitelist or blacklist, you might want to review the site_stats.  
An easy way to do this is to run *python3 show_site_stats.py*  
show_site_stats.py accepts one optional argument: [new, all]  
'new' shows only stats for sites not listed in sites.json (so you can decide if you want to whitelist them)
