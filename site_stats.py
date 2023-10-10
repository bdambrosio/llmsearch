import io
import sys
import os
import json
import random
import traceback
import utilityV2 as ut


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


site_stats = {}  # initialize dictionay of sites used
stats_loaded = False
stats_dirty = False


def open_site_stats():
    global site_stats, stats_loaded, stats_dirty
    if stats_loaded:
        return
    try:
        with open("site_stats.json", "r") as f:
            site_stats = json.loads(f.read())
    except:
        print("Failed to read site_stats.json")
        traceback.print_exc()


def ckpt():
    global site_stats, stats_dirty
    if not stats_dirty:
        return
    try:
        with open("site_stats.json", "w") as ss:
            ss.write(json.dumps(site_stats))
        stats_dirty = False
    except Exception as e:
        print(f"Failed to write site_stats: {str(e)}")
        traceback.print_exc()


def update_site_stats(site, char_cnt, get_time, extract_time, openai_time):
    global site_stats, stats_dirty
    open_site_stats()
    if site not in site_stats:
        site_stats[site] = {
            "name": site,
            "hits": 0,
            "chars": 0,
            "get": 0,
            "extract": 0,
            "openai": 0,
        }
    if "hits" not in site_stats[site]:
        site_stats[site]["hits"] = 0
    site_stats[site]["hits"] = site_stats[site]["hits"] + 1
    site_stats[site]["chars"] = char_cnt + site_stats[site]["chars"]
    site_stats[site]["get"] = get_time + site_stats[site]["get"]
    site_stats[site]["extract"] = extract_time + site_stats[site]["extract"]
    site_stats[site]["openai"] = openai_time + site_stats[site]["openai"]
    stats_dirty = True
    # print("updated", site_stats[site])


def retrieve(site):
    global site_stats
    if site not in site_stats:
        site_stats[site] = {
            "name": site,
            "hits": 0,
            "chars": 0,
            "get": 0,
            "extract": 0,
            "openai": 0,
        }
    return site_stats[site]


def get_next(urls, sample_unknown=False):
    global site_stats
    # retrieve stats for sites in list
    candidates = []
    for url in urls:
        site = extract_site(url)
        candidate = retrieve(site)
        if sample_unknown or (site in ut.sites and ut.sites[site] != 0):
            candidates.append((candidate, url))
    if len(candidates) == 0:
        return []
    if len(candidates) == 1:
        return candidates[0]
    # random or ordered? if random, pick without sorting
    if random.random() > 0.85:
        pick = int(random.random() * len(candidates))
        return candidates[pick]

    # ordered, sort and compute cumulative
    candidates.sort(
        reverse=True,
        key=lambda item: (
            (item[0]["chars"] * 1000000)
            / (max(1000, item[0]["get"] + item[0]["extract"] + item[0]["openai"]))
        ),
    )

    # now pick top from sort
    p = random.random()
    p2 = p * p * p
    return candidates[int(p2 * len(candidates))]
