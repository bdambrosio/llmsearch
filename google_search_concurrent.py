import concurrent.futures
import requests
import requests
import json
import openai
import sys
import os
import io
import time
import string
from urllib.request import urlopen
from datetime import date
from datetime import datetime
import random
import openai

# from PyPDF2 import PdfReader
import traceback
import re
import site_stats
import utilityV2 as ut
from itertools import zip_longest
import urllib3
import warnings
import copy
import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import wordfreq as wf
from unstructured.partition.html import partition_html
import nltk
import urllib.parse as en

today = " as of " + date.today().strftime("%b-%d-%Y") + "\n\n"

suffix = "\nA: "
client = "\nQ: "
QUICK_SEARCH = "quick"
NORMAL_SEARCH = "moderate"
DEEP_SEARCH = "deep"

system_prime = {
    "role": "system",
    "content": "You analyze Text with respect to Query and list any relevant information found, including direct quotes from the text, and detailed samples or examples in the text.",
}
priming_1 = {"role": "user", "content": "Query:\n"}
priming_2 = {
    "role": "user",
    "content": "List relevant information in the provided text, including direct quotes from the text. If none, respond 'no information'.\nText:\n",
}


# Define a function to make a single URL request and process the response
def process_url(query_phrase, keywords, keyword_weights, url, timeout):
    start_time = time.time()
    site = ut.extract_site(url)
    result = ""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            options = Options()
            options.page_load_strategy = "eager"
            options.add_argument("--headless")
            result = ""
            with webdriver.Chrome(options=options) as dr:
                print(f"*****setting page load timeout {timeout}")
                dr.set_page_load_timeout(timeout)
                try:
                    dr.get(url)
                    response = dr.page_source
                    result = response_text_extract(
                        query_phrase,
                        keywords,
                        keyword_weights,
                        url,
                        response,
                        int(time.time() - start_time),
                    )
                except selenium.common.exceptions.TimeoutException:
                    return "", url
    except Exception:
        traceback.print_exc()
        print(f"{site} err")
        pass
    # print(f"Processed {site}: {len(response)} / {len(result)} {int((time.time()-start_time)*1000)} ms")
    return result, url


def process_urls(query_phrase, keywords, keyword_weights, urls, search_level):
    # Create a ThreadPoolExecutor with 5 worker threads
    response = []
    print("entering process urls")
    start_time = time.time()
    full_text = ""
    used_index = 0
    urls_used = ["" for i in range(30)]
    tried_index = 0
    urls_tried = ["" for i in range(30)]
    start_time = time.time()
    in_process = []
    processed = []
    google_futures = []
    off_whitelist = False

    with concurrent.futures.ThreadPoolExecutor(max_workers=11) as executor:
        # initialize scan of google urls
        while True:
            try:
                while (
                    len(urls) > 0
                    # no sense starting if not much time left
                    and (
                        (
                            search_level == DEEP_SEARCH
                            and len(full_text) < 9600
                            and len(in_process) < 16
                            and time.time() - start_time < 14
                        )
                        or (
                            search_level == NORMAL_SEARCH
                            and len(full_text) < 6400
                            and len(in_process) < 14
                            and time.time() - start_time < 12
                        )
                        or (
                            search_level == QUICK_SEARCH
                            and len(full_text) < 4800
                            and len(in_process) < 10
                            and time.time() - start_time < 8
                        )
                    )
                ):
                    recommendation = site_stats.get_next(
                        urls, sample_unknown=off_whitelist
                    )
                    if recommendation is None or len(recommendation) == 0:
                        off_whitelist = True
                    else:
                        # set timeout so we don't wait for a slow site forever
                        timeout = 12 - int(time.time() - start_time)
                        if search_level == NORMAL_SEARCH:
                            timeout = timeout + 4
                        url = recommendation[1]
                        future = executor.submit(
                            process_url,
                            query_phrase,
                            keywords,
                            keyword_weights,
                            url,
                            timeout,
                        )
                        # remaining_time = start_time+18-time.time()
                        # future.exception(remaining_time)
                        google_futures.append(future)
                        in_process.append(future)
                        urls_tried[tried_index] = url
                        tried_index += 1
                        urls.remove(url)
                        print(f"queued {ut.extract_site(url)}, {timeout}")
                # Process the responses as they arrive
                for future in in_process:
                    if future.done():
                        result, url = future.result()
                        processed.append(future)
                        in_process.remove(future)
                        if len(result) > 0:
                            urls_used[used_index] = url
                            used_index += 1
                            result = result.replace(". .", ".")
                            print(
                                f"adding {len(result)} chars from {ut.extract_site(url)} to {len(response)} prior responses"
                            )
                            site = ut.extract_site(url)
                            domain = ut.extract_domain(url)
                            if domain.endswith("gov"):
                                credibility = "Official Source"
                            elif site in ut.sites.keys():
                                if ut.sites[site] > 0:
                                    credibility = "Whitelisted Source"
                                elif ut.sites[site] == 0:
                                    credibility = "Blacklisted Source"
                            else:
                                credibility = "Third-Party Source"

                            response.append(
                                {
                                    "source": ut.extract_domain(url),
                                    "url": url,
                                    "credibility": credibility,
                                    "text": result,
                                }
                            )

                # openai seems to timeout a plugin  at about 30 secs, and there is pbly 3-4 sec overhead
                if (
                    (len(urls) == 0 and len(in_process) == 0)
                    or (
                        search_level == DEEP_SEARCH
                        and (len(full_text) > 9600)
                        or time.time() - start_time > 42
                    )
                    or (
                        search_level == NORMAL_SEARCH
                        and (len(full_text) > 6400)
                        or time.time() - start_time > 32
                    )
                    or (
                        search_level == QUICK_SEARCH
                        and (len(full_text) > 4800)
                        or time.time() - start_time > 28
                    )
                ):
                    executor.shutdown(wait=False)
                    print(
                        f"n****** exiting process urls early {len(response)} {int(time.time()-start_time)} secs\n"
                    )
                    return response, used_index, urls_used, tried_index, urls_tried
                time.sleep(0.5)
            except:
                traceback.print_exc()
        executor.shutdown(wait=False)
    print(
        f"\n*****processed all urls {len(response)}  {int(time.time()-start_time)} secs"
    )
    return response, index, urls_used, tried_index, urls_tried


def extract_subtext(text, query_phrase, keywords, keyword_weights):
    ###  maybe we should score based on paragraphs, not lines?
    sentences = ut.reform(text)
    # print('***** sentences from reform')
    # for sentence in sentences:
    #    print(sentence)
    sentence_weights = {}
    final_text = ""
    for sentence in sentences:
        sentence_weights[sentence] = 0
        for keyword in keywords:
            if keyword in sentence or keyword.lower() in sentence:
                if keyword in keyword_weights.keys():
                    sentence_weights[sentence] += keyword_weights[keyword]

    # now pick out sentences starting with those with the most keywords
    max_sentence_weight = 0
    for keyword in keyword_weights.keys():
        max_sentence_weight += keyword_weights[keyword]
    # print(f'******* max sentence weight {max_sentence_weight}')
    for i in range(max_sentence_weight, 1, -1):
        if len(final_text) > 6000 and i < max(
            1, int(max_sentence_weight / 4)
        ):  # make sure we don't miss any super-important text
            return final_text
        for sentence in sentences:
            if len(final_text) + len(sentence) > 6001 and i < max(
                1, int(max_sentence_weight / 4)
            ):
                continue
            if sentence_weights[sentence] == i:
                final_text += sentence
    # print("relevant text", final_text)
    # print("keyword extract length:",len(final_text)) #, end='.. ')

    return final_text


def search(query_phrase):
    print(f"***** search {query_phrase}")
    sort = "&sort=date-sdate:d:w"
    if "today" in query_phrase or "latest" in query_phrase:
        sort = "&sort=date-sdate:d:s"
    # print(f"search for: {query_phrase}")
    google_query = en.quote(query_phrase)
    response = []
    try:
        start_wall_time = time.time()
        url = (
            "https://www.googleapis.com/customsearch/v1?key="
            + ut.google_key
            + "&cx="
            + ut.google_cx
            + "&num=10"
            + sort
            + "&q="
            + google_query
        )
        response = requests.get(url)
        response_json = json.loads(response.text)
        print(f"***** google search {int((time.time()-start_wall_time)*10)/10} sec")
    except:
        traceback.print_exc()
        return []

    # see if we got anything useful from google
    if "items" not in response_json.keys():
        print("no return from google ...", response, response_json.keys())
        # print(google_query)
        return []

    # first try whitelist sites
    urls = []
    for i in range(len(response_json["items"])):
        url = response_json["items"][i]["link"].lstrip().rstrip()
        site = ut.extract_site(url)
        if site not in ut.sites or ut.sites[site] == 1:
            urls.append(url)
    return urls


def log_url_process(site, reason, raw_text, extract_text, gpt_text):
    return


"""
# to record detailed logs of url processing unquote this function
def log_url_process(site, reason, raw_text, extract_text, gpt_text):
    if len(raw_text) == 0 and len(extract_text)==0 and len(gpt_text) ==0:
        return
    try:
        with open('google_log.txt', 'a') as lg:
            lg.write('\n\n*************'+reason.upper()+'***********\n')
            lg.write('*****************'+site+'  RAW*************\n')
            lg.write(raw_text)
            lg.write('\n******************extract****************\n')
            lg.write(extract_text)
            lg.write('\n********************gpt******************\n')
            lg.write(gpt_text)
    except Exception:
        traceback.print_exc()
"""


def response_text_extract(
    query_phrase, keywords, keyword_weights, url, response, get_time
):
    curr = time.time()
    text = ""
    extract_text = ""
    site = ut.extract_site(url)

    if url.endswith("pdf"):
        pass
    else:
        elements = partition_html(text=response)
        str_elements = []
        # print('\n***** elements')
        for e in elements:
            stre = str(e).replace("  ", " ")
            str_elements.append(stre)
        extract_text = extract_subtext(
            str_elements, query_phrase, keywords, keyword_weights
        )
        # print('\n************ unstructured **********')
        print(
            f"***** unstructured found {len(elements)} elements, {sum([len(str(e)) for e in elements])} raw chars, {len(extract_text)} extract"
        )
    url_text = text  # save for final stats
    new_curr = time.time()
    extract_time = int((new_curr - curr) * 1000000)
    if len(extract_text.strip()) < 8:
        return ""

    # now ask openai to extract answer
    response_text = ""
    curr = new_curr
    extract_text = extract_text[:10000]  # make sure we don't run over token limit
    gpt_tldr_message = [
        {
            "role": "user",
            "content": "Given:\n" + extract_text + "\n\nQuery:\n" + query_phrase,
        }
    ]
    start_wall_time = time.time()
    t_out = 12 - get_time
    # print(f'****** spawning page get with timeout {t_out}')
    google_tldr = ut.ask_gpt_with_retries(
        ut.MODEL, gpt_tldr_message, tokens=300, temp=0.3, timeout=t_out, tries=1
    )
    openai_time = int((time.time() - start_wall_time) * 10) / 10
    print(f"\n***** tldr {query_phrase}, {openai_time} sec")
    # print(f'***** \n{extract_text}\n***** \n{google_tldr}\n*****\n')
    url_text = url_text.replace("\n", ". ")
    if google_tldr is None:
        google_tldr = ""
    response_text = google_tldr.lstrip()
    prefix_text = response_text[: min(len(response_text), 96)].lower()
    # openai sometimes returns a special format for 'no imformation'
    if prefix_text.startswith("query:"):
        text_index = response_text.find("Text:")
        if text_index > 0:
            response_text = response_text[text_index + 5 :]
            prefix_text = response_text[: min(len(response_text), 96)].lower()
    if (
        "no information" in prefix_text
        or "i cannot provide" in prefix_text
        or "as an ai language model" in prefix_text
        or "does not provide" in prefix_text
        or "it is not possible" in prefix_text
    ):
        # skip this summary, no info
        print(
            "{} {}/{}/{}/{}".format(
                site, len(response), len(url_text), len(extract_text), 0
            )
        )
        # print('************')
        # print(extract_text)
        # print('************')
        sys.stdout.flush()
        log_url_process(site, "no info", url_text, extract_text, "")
        site_stats.update_site_stats(site, 0, get_time, extract_time, openai_time)
        return ""

    if (
        prefix_text.startswith("i'm sorry")
        or prefix_text.startswith("there is no ")
        or (
            prefix_text.startswith("the provided text")
            or prefix_text.startswith("i cannot")
            or prefix_text.startswith("unfortunately")
            or prefix_text.startswith("sorry")
            or prefix_text.startswith("the text")
        )
        and (
            "is not relevant" in prefix_text
            or "no information" in prefix_text
            or "does not provide" in prefix_text
            or "does not contain" in prefix_text
            or "no relevant information" in prefix_text
        )
    ):
        # skip this summary, no info
        log_url_process(site, "no info 2", url_text, extract_text, "")
        print(
            "{} {}/{}/{}/{}".format(
                site, len(response), len(url_text), len(extract_text), 0
            )
        )
        ###print('************')
        ###print(extract_text)
        ###print('************')
        site_stats.update_site_stats(site, 0, get_time, extract_time, openai_time)
        return ""
    else:
        sentences = nltk.sent_tokenize(response_text)
        response_text = ""
        for sentence in sentences:
            if (
                "no inform" in sentence.lower()
                or "no specific inform" in sentence.lower()
                or "is unclear" in sentence.lower()
                or "not mention" in sentence.lower()
                or "not specifically mention" in sentence.lower()
            ):
                pass
            else:
                response_text += "\n \u2022 " + sentence + ". "
        site_stats.update_site_stats(
            site, len(response_text), get_time, extract_time, openai_time
        )
        # print('\n',response_text)
        log_url_process(site, "response", url_text, extract_text, response_text)
        print(
            "{} {}/{}/{}/{}".format(
                site,
                len(response),
                len(url_text),
                len(extract_text),
                len(response_text),
            )
        )
        # print('************')
        # print(google_tldr)
        # print('************ site response ***********')
        # print(response_text)
        # print('************')
        return response_text + "\n"
    site_stats.update_site_stats(site, 0, get_time, extract_time, openai_time)
    log_url_process(site, "no return", "", "", "")
    print(
        "{} {}/{}/{}/{}".format(
            site, len(response), len(url_text), len(extract_text), 0
        )
    )
    ###print('************')
    ###print(extract_text)
    ###print('************')
    return ""


def extract_items_from_numbered_list(text):
    items = ""
    elements = text.split("\n")
    for candidate in elements:
        candidate = candidate.lstrip(". \t")
        if len(candidate) > 4 and candidate[0].isdigit():
            candidate = candidate[1:].lstrip(". ")
            if (
                len(candidate) > 4 and candidate[0].isdigit()
            ):  # strip second digit if more than 10 items
                candidate = candidate[1:].lstrip(". ")
            print("E {}".format(candidate))
            items += candidate + " "
    return items


def search_google(original_query, search_level, query_phrase, keywords, chat_history):
    start_time = time.time()
    all_urls = []
    urls_used = []
    urls_tried = []
    index = 0
    tried_index = 0
    full_text = ""
    keyword_weights = {}
    for keyword in keywords:
        zipf = wf.zipf_frequency(keyword, "en")
        weight = max(0, int((8 - zipf)))
        if weight > 0:
            keyword_weights[keyword] = weight
            print(f"keyword {keyword} wf.ziff {zipf} weight {weight}")
            subwds = keyword.split(" ")
            if len(subwds) > 1:
                for subwd in subwds:
                    sub_z = wf.zipf_frequency(subwd, "en")
                    sub_wgt = max(0, int((8 - zipf) * 1 / 2))
                    if sub_wgt > 0:
                        keyword_weights[subwd] = sub_wgt
                        print(f"keyword {subwd} weight {sub_wgt}")

    try:  # query google for recent info
        sort = ""
        if "today" in original_query or "latest" in original_query:
            original_query = today.strip("\n") + " " + original_query
        extract_query = ""
        orig_phrase_urls = []
        if len(original_query) > 0:
            orig_phrase_urls = search(original_query[: min(len(original_query), 128)])
            extract_query = original_query[: min(len(original_query), 128)]
        gpt_phrase_urls = []
        if len(query_phrase) > 0:
            gpt_phrase_urls = search(query_phrase)
            extract_query = (
                query_phrase  # prefer more succint query phrase if available
            )
        if len(orig_phrase_urls) == 0 and len(gpt_phrase_urls) == 0:
            return "", [], 0, [""], 0, [""]

        for url in orig_phrase_urls:
            if url in gpt_phrase_urls:
                gpt_phrase_urls.remove(url)

        # interleave both lists now that duplicates are removed
        urls = [
            val
            for tup in zip_longest(orig_phrase_urls, gpt_phrase_urls)
            for val in tup
            if val is not None
        ]
        # urls = [val for tup in zip_longest(urls, kwd_phrase_urls) for val in tup if val is not None]
        all_urls = copy.deepcopy(urls)
        # initialize scan of google urls
        # compute keyword weights
        start_wall_time = time.time()
        full_text, index, urls_used, tried_index, urls_tried = process_urls(
            extract_query, keywords, keyword_weights, all_urls, search_level
        )
        site_stats.ckpt()
        print(f"***** urls_processed {int((time.time()-start_wall_time)*10)/10} sec")
        # print("return from url processsing")
    except:
        traceback.print_exc()
    return full_text, all_urls, index, urls_used, tried_index, urls_tried
