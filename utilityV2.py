import openai
import requests
import re
import time
import random
import traceback
import concurrent.futures
import threading as th
import json
import tracemalloc
import os
import linecache
import nltk

# from tenacity import (retry,stop_after_attempt,stop_after_delay, wait_random_exponential)
from tenacity import *
import selenium

openai.api_key = os.getenv("OPENAI_API_KEY")
google_key = os.getenv("GOOGLE_KEY")
google_cx = os.getenv("GOOGLE_CX")
GOOGLE = "google"
USER = "user"
ASSISTANT = "assistant"

MODEL = "gpt-3.5-turbo"

sites = {}  # initialize dictionay or sites used
new_sites = {}  # initialize dictionay or sites used
try:
    with open("sites", "r") as f:
        sites = json.loads(f.read())
except:
    print("Failed to read sites.")


# for experimenting with Vicuna


def display_top(snapshot, key_type="lineno", limit=10):
    snapshot = snapshot.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        print(
            "#%s: %s:%s: %.1f KiB"
            % (index, frame.filename, frame.lineno, stat.size / 1024)
        )
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print("    %s" % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))


class turn:
    def __init__(self, role="assistant", message="", tldr="", source="", keywords=[]):
        self.role = role
        self.message = message
        self.tldr = tldr
        self.source = source
        self.keywords = keywords

    def __str__(self):
        s = ""
        if self.role is not None and len(self.role) > 0:
            s = s + "r: " + self.role
        if self.message is not None and len(self.message) > 0:
            s = s + " m: " + self.message
        if self.source is not None and len(self.source) > 0:
            s = s + " s: " + self.source
        if self.tldr is not None and len(self.tldr) > 0:
            s = s + "tldr: " + self.tldr
        return s

    def is_google_turn(self):
        return self.source is not None and self.source == GOOGLE

    def is_user_turn(self):
        return self.source is not None and self.source == USER

    def is_assistant_turn(self):
        return self.source is not None and self.source == ASSISTANT


# @retry(wait=wait_random_exponential(min=1, max=2), stop=(stop_after_delay(15) | stop_after_attempt(2)))
def chatCompletion_with_backoff(**kwargs):
    return openai.ChatCompletion.create(**kwargs)


def ask_gpt(model, gpt_message, max_tokens, temp, top_p):
    completion = None
    try:
        completion = openai.ChatCompletion.create(
            model=model,
            messages=gpt_message,
            max_tokens=max_tokens,
            temperature=temp,
            top_p=top_p,
        )
    except:
        traceback.print_exc()
    if completion is not None:
        response = completion["choices"][0]["message"]["content"].lstrip(" ,:.")
        print(response)
        return response
    else:
        print("no response")
        return None


def ask_gpt_with_retries(model, gpt_message, tokens, temp, timeout, tries):
    retryer = Retrying(stop=(stop_after_delay(timeout) | stop_after_attempt(1)))
    r = retryer(
        ask_gpt,
        model=model,
        gpt_message=gpt_message,
        max_tokens=tokens,
        temp=temp,
        top_p=1,
    )
    return r


INFORMATION_QUERY = "information query"
INTENTS = []


def find_intent(response):
    global INTENTS, INFORMATION_QUERY
    for intent in INTENTS:
        if intent in response.lower():
            return intent
    return INFORMATION_QUERY


def find_query(response):
    search_query_phrase = response
    phrase_index = response.lower().find("phrase:")
    quoted_strings = []
    if phrase_index < 0:
        phrase_index = 0
    else:
        phrase_index += len("phrase:")
    quoted_strings = re.findall(r'"([^"]*)"', search_query_phrase[phrase_index:])
    if len(quoted_strings) == 0:
        quoted_strings = re.findall(r"'([^']*)'", search_query_phrase[phrase_index:])
    if len(quoted_strings) > 0:
        # print(quoted_strings)
        phrase = quoted_strings[0]
        return phrase, response[response.find(phrase) + len(phrase) + 1 :]
    else:
        print("no quoted text, returning original query string", response)
        # print(response)
        return "", response


def find_keywords(response, query_phrase, orig_phrase):
    # keywords includes those suggested by gpt and any remaining words from query phrase len > 4
    keywords = []
    quoted_strings = re.findall(r'"([^"]*)"', query_phrase)
    quoted_strings2 = re.findall(r'"([^"]*)"', orig_phrase)
    remainder = query_phrase
    k_index = response.lower().find("keyword")
    if k_index > 0:
        keyword_string = response[k_index + len("keyword") :]
        nm_index = keyword_string.find("Named-Entities:")
        if nm_index > 0:
            keyword_string = keyword_string[:nm_index].rstrip()
            # print(keyword_string)
        c_index = keyword_string.find(":")
        keyword_string = keyword_string[c_index + 1 :]
        candidates = keyword_string.split(",")
        for keyword in candidates:
            keyword = keyword.strip(":,.\t\n").lstrip(" ")
            if len(keyword) > 3 or keyword[0:1].isupper():
                keywords.append(keyword)
        return keywords
    return ""


def split_interaction(interaction):
    qs = interaction.find(prefix)
    rs = interaction.find(suffix)
    if qs >= 0 and rs >= 0:
        query = interaction[len(prefix) : rs].lstrip()
        response = interaction[rs + len(suffix) :].lstrip()
        return query, response
    else:
        print("can't parse", interaction)
    return "", ""


def findnth(haystack, needle, n):
    parts = haystack.split(needle, n + 1)
    if len(parts) <= n + 1:
        return -1
    return len(haystack) - len(parts[-1]) - len(needle)


def extract_site(url):
    site = ""
    base = findnth(url, "/", 2)
    if base > 2:
        site = url[:base].split(".")
    if len(site) > 1:
        site = site[-2]
    site = site.replace("https://", "")
    site = site.replace("http://", "")
    return site


def extract_domain(url):
    site = ""
    base = findnth(url, "/", 2)
    if base > 2:
        domain = url[:base].split(".")
    if len(domain) > 1:
        domain = domain[-2] + "." + domain[-1]
    domain = domain.replace("https://", "")
    domain = domain.replace("http://", "")
    return domain


def part_of_keyword(word, keywords):
    for keyword in keywords:
        if word in keyword:
            return True
    return False


keyword_prompt = 'Perform two tasks on the following text. First, rewrite the <text> as an effective google search phrase. Second, analyze text and list keywords and named-entities found. Return the result as: Phrase: "<google search phrase>"\nKeywords: <list of keywords>\nNamed-Entities: <list of Named-Entities>'


def get_search_phrase_and_keywords(query_string, chat_history):
    gpt_message = [
        {"role": "user", "content": keyword_prompt},
        {"role": "user", "content": "Text\n" + query_string},
        {"role": "assistant", "content": "Phrase:"},
    ]
    response_text = ""
    completion = None
    # for role in gpt_message:
    #    print(role)
    # print()
    response_text = ask_gpt_with_retries(
        "gpt-3.5-turbo", gpt_message, tokens=150, temp=0.3, timeout=6, tries=2
    )
    print(response_text)
    query_phrase, remainder = find_query(response_text)
    print("PHRASE:", query_phrase)
    # print(remainder)
    keywords = find_keywords(remainder, query_phrase, query_string)
    print("KEYWORDS:", keywords)
    return query_phrase, keywords


def reform(elements):
    # reformulates text extracted from a webpage by unstructured.partition_html into larger keyword-rankable chunks
    texts = (
        []
    )  # a list of text_strings, each of at most *max* chars, separated on '\n' when splitting an element is needed
    paragraphs = []
    total_elem_len = 0
    for element in elements:
        text = str(element)
        total_elem_len += len(text)
        if len(text) < 4:
            continue
        elif len(text) < 500:
            texts.append(text)
        else:
            subtexts = text.split("\n")
            for subtext in subtexts:
                if len(subtext) < 500:
                    texts.append(subtext)
                else:
                    texts.extend(nltk.sent_tokenize(subtext))

    # now reassemble shorter texts into chunks
    paragraph = ""
    total_pp_len = 0
    for text in texts:
        if len(text) + len(paragraph) < 500:
            paragraph += " " + text
        else:
            if len(paragraph) > 0:  # start a new paragraph
                paragraphs.append(paragraph)
                paragraph = ""
            paragraph += text
    if len(paragraph) > 0:
        paragraphs.append(paragraph + ".\n")
    # print(f'\n***** reform elements in {len(elements)}, paragraphs out {len(paragraphs)}')
    total_pp_len = 0
    for paragraph in paragraphs:
        total_pp_len += len(paragraph)
    if total_pp_len > 1.2 * total_elem_len:
        print(
            f"******** reform out > reform in.  out: {total_pp_len}, in: {total_elem_len}"
        )
    return paragraphs


def get_actions(text):
    # look for actions in response
    action_indecies = re.finditer("Action:", text)  # Action: [search, ask} (query)
    actions = []
    editted_response = text
    for action_index in action_indecies:
        action = text[action_index.span()[1] :]
        agent = None
        query = None
        query_start = action.find("(")
        if query_start > 0:
            agent = action[:query_start].strip()
            query_end = action[query_start + 1 :].find(")")
            if query_end > 0:
                query = action[query_start + 1 : query_start + 1 + query_end]
                action = text[
                    action_index.start() : action_index.span()[1]
                    + action_index.start()
                    + query_start
                    + query_end
                    + 2
                ]
        if agent is None or query is None:
            print(
                "can't parse action, skipping",
                text[action_index.start() : action_index.start() + 48],
            )
            continue
        actions.append([agent, query, action])
        editted_response = editted_response.replace(action, "")
    return actions


if __name__ == "__main__":
    get_search_phrase_and_keywords(
        "Would I like the video game Forspoken, given that I like Final Fantasy VII?",
        [],
    )
    # print(query_vicuna("what is 5 * 3?"))
