import utilityV2 as ut
import google_search_concurrent as gs
import re
import time

ABORT = False
CONTINUE = True
history = []


class history_entry:
    def __init__(self, turn, vector=None):
        self.message = turn.message.lower()
        self.role = turn.role

    def equal(self, he2):
        return self.message == he2.message and self.role == turn.role


def add(turn):
    he = history_entry(turn)
    history.append(he)


def is_metaCyclic(turn):
    he = history_entry(turn)
    count = 0
    for prior_he in history:
        if he.equal(prior_he):
            count += 1
    return count > 1


def is_cyclic(turn):
    he = history_entry(turn)
    for prior_he in history:
        if he.equal(prior_he):
            return True
    return False


def clear():
    global history
    history = []
    return


def test_history():
    he1 = history_entry(ut.turn(role="assistant", message="who is Noriel Roubini"))
    he2 = history_entry(ut.turn(role="assistant", message="who was Noriel Roubini"))
    he3 = history_entry(ut.turn(role="assistant", message="who was Nsriel Roubini"))
    he4 = history_entry(ut.turn(role="assistant", message="where is the Pinnacles"))
    for hea in (he1, he2, he3, he4):
        for heb in (he1, he2, he3, he4):
            print(cosine(hea, heb))


def test_parse_decomp():
    test_text = """<Subquery 1>? What is the birthplace of Hugh Jackman?
<Subquery 2>? What is the Japanese name of the birthplace of Hugh Jackman?
<Keywords 1>: Hugh Jackman, birthplace
<Keywords 2>: Japanese name, birthplace, Hugh Jackman"""

    decomp = parse_decomposition(test_text)
    for subquery in decomp:
        print("Subquery\n", subquery)


def parse_decomposition(text):
    ### expecting:
    ###   <Subquery 1>
    ###   Birthplace of Hugh Jackman
    ###   <Subquery 2>
    ###   Japanese name of Birthplace of Hugh Jackman
    ###  note that 'Birthplace of Hugh Jackson' operates as both a strinq google query and a variable in subsequent occurences
    subquery_indecies = re.finditer(
        "<Subquery", text
    )  # Action: Ask {Google, User} "query"
    subqueries = []
    for index in subquery_indecies:
        hdr_end = text[index.start() :].find(">") + index.start()
        query_start = hdr_end + 1
        query_end = text[query_start:].find("<")
        if query_end < 0:
            query = text[query_start:].strip()
        else:
            query = text[query_start : query_start + query_end].lstrip("?").strip()
        print("Query:", query)
        subqueries.append(query)
    return subqueries


def query_keywords(query):
    start_wall_time = time.time()
    gpt_key_message = [
        {
            "role": "user",
            "content": "Extract keywords and named-entities from the following text.",
        },
        {"role": "user", "content": query},
    ]
    # for item in gpt_key_message:
    #    print(item)
    gpt_parse = ut.ask_gpt_with_retries(
        "gpt-3.5-turbo", gpt_key_message, tokens=25, temp=0, timeout=5, tries=2
    )
    # print(f'\n***** keywords and named-entities {gpt_parse}')
    # parse result Keywords: {comma separated list}\n\nNamed-entities: {comma-separated-list}
    keywords = []
    # do named entities first, they might be compounds of keywords
    ne_start = gpt_parse.find("Named-entities")
    print(f"***** keyword extract {int((time.time()-start_wall_time)*10)/10} sec")
    if ne_start > 0:
        nes = gpt_parse[ne_start + len("Named-entities") + 1 :].split(
            ","
        )  # assume string ends with colon or space:].split(',')
        # print(f'Named-entity candidates {nes}')
        for ne in nes:
            ne = ne.strip(" .,;:\n")
            # print(f'  appending {ne}')
            if ne != "None":
                keywords.append(ne)
    else:
        ne_start = len(gpt_parse) + 1
    kwd_start = gpt_parse.find("Keywords")
    if kwd_start > -1:
        kwds = gpt_parse[kwd_start + len("Keywords") + 1 : ne_start].split(",")
        # print(f'Keyword candidates {kwds}')
        for kwd in kwds:
            kwd = kwd.strip(" .\n,;:")
            skip = False
            for kwd2 in keywords:
                if kwd in kwd2:
                    skip = True
            if not skip:
                # print('appending', kwd)
                keywords.append(kwd)
    # else: print("Keywords index < 0")
    if len(keywords) > 0:
        print(f"***** query_keywords found keywords {keywords}")
        return keywords
    # fallback - just use query words
    candidates = query.split(" ")
    for candidate in candidates:
        candidate = candidate.strip()
        if len(candidate) > 2:
            keywords.append(candidate)
    # print(f'***** query_keywords using default keywords {keywords}')
    return keywords


def substitute(Q1, A1, Q2, debug=False):
    gpt_sub_message = [
        {
            "role": "user",
            "content": "replace '" + Q1 + "' with '" + A1 + "' in '" + Q2 + "'",
        }
    ]
    if debug:
        print("\n\n**************")
        for item in gpt_sub_message:
            print(item)
    google_tldr = ut.ask_gpt_with_retries(
        "gpt-3.5-turbo", gpt_sub_message, tokens=25, temp=0.1, timeout=5, tries=2
    )
    print("\n\n**************")
    if len(google_tldr) == 0 or "no information" in google_tldr:
        print("Returning original Q2")
        return Q2
    print("Substituted", Q2, google_tldr)
    return google_tldr


def meta(query, chat_history, debug=False):
    print("***** entering meta")
    turn = ut.turn(
        role=ut.ASSISTANT, source=ut.ASSISTANT, message='Action: search "' + query + '"'
    )
    if is_metaCyclic(turn):
        return [], ABORT

    prompt = """Decompose a compound <Query> into two smaller <Subquery>. Use the following format for output:
<Subquery 1>
<Subquery 2>"""
    gpt_message = [
        {"role": "user", "content": prompt},
        {"role": "user", "content": "<Query>\n" + query},
    ]
    response_text = ""
    completion = None
    if debug:
        for role in gpt_message:
            print(role)
    print("starting gpt decomp query")
    response_text = ut.ask_gpt_with_retries(
        "gpt-3.5-turbo", gpt_message, tokens=75, temp=0.1, timeout=5, tries=2
    )
    if debug:
        print(f"initial gpt query response:\n{response_text}")
        print("**** executing decomp ****")
    subqueries = parse_decomposition(response_text)
    meta_chat_history = []
    prev_tldr = ""
    google_tldr = ""
    for n, subquery in enumerate(subqueries):
        # do variable substituion into subquery
        # ask google
        # send google results as notes plus subquery to gpt to extract <answer i>
        # return chat history extended with each subquery and its answer
        #   (or maybe just all google notes, let next level down do the rest?)
        #   bad idea, can exceed token limit!
        if debug:
            print(f'subquery {n}, "{subquery}"')
        if n > 0:
            subquery = substitute(subqueries[n - 1], prev_tldr, subquery)
            keyword_set = query_keywords(subquery)

        keyword_set = query_keywords(subquery)
        print("*****Executing subquery", subquery, "\n  with keywords", keyword_set)
        gpt_initial_message = [
            {
                "role": "user",
                "content": subquery + " If fact is unavailable, respond: 'Unknown'",
            }
        ]

        # for turn in meta_chat_history:
        #    gpt_initial_message.append({"role":"user","content":turn.tldr})

        initial_gpt_answer = ut.ask_gpt_with_retries(
            "gpt-3.5-turbo",
            gpt_initial_message,
            tokens=25,
            temp=0.0,
            timeout=5,
            tries=2,
        )
        if debug:
            print(f"***** google extract\n {initial_gpt_answer}\n")
        if (
            "unknown" not in initial_gpt_answer.lower()
            and "cannot provide" not in initial_gpt_answer
            and "do not have access" not in initial_gpt_answer
        ):
            meta_chat_history.append(
                ut.turn(
                    role="assistant",
                    message=subquery,
                    source=ut.ASSISTANT,
                    tldr=subquery,
                    keywords=keyword_set,
                )
            )
            meta_chat_history.append(
                ut.turn(
                    role="assistant",
                    message="<note>\n" + initial_gpt_answer + "\n<note>",
                    source=ut.GOOGLE,
                    tldr=initial_gpt_answer,
                    keywords=keyword_set,
                )
            )
            prev_tldr = initial_gpt_answer
            print(f"***** Answer to {subquery}: {initial_gpt_answer}\n")
            google_tldr = initial_gpt_answer
            continue
        # ask google
        (
            google_text,
            urls_all,
            index,
            urls_used,
            tried_index,
            urls_tried,
        ) = gs.search_google(
            subquery,
            gs.QUICK_SEARCH,
            "",
            ut.INFORMATION_QUERY,
            keyword_set,
            meta_chat_history,
        )
        if len(google_text) > 0:
            # digest google response into an answer for this subquery
            if debug:
                print(f"***** search result\n{google_text}\n")
            gpt_tldr_message = [
                {
                    "role": "user",
                    "content": 'Summarize the set of <note> provided. Including only the direct answer to <Query>. Do not include any qualifiers or modifiers from the <Query> such as "where x was born".',
                },
                {"role": "user", "content": google_text},
                {"role": "user", "content": "<Query>\n" + subquery},
            ]
            # for turn in meta_chat_history:
            #   gpt_tldr_message.append({"role":"user","content":turn.tldr})

            google_tldr = ut.ask_gpt_with_retries(
                "gpt-3.5-turbo",
                gpt_tldr_message,
                tokens=150,
                temp=0.1,
                timeout=5,
                tries=2,
            )
            # print('\n\n**************')
            # for item in gpt_tldr_message:
            #    print(item)
            print(f"***** Answer to {subquery}: {google_tldr}\n")
            meta_chat_history.append(
                ut.turn(
                    role="assistant",
                    message=subquery,
                    source=ut.ASSISTANT,
                    tldr=subquery,
                    keywords=keyword_set,
                )
            )
            meta_chat_history.append(
                ut.turn(
                    role="assistant",
                    message="Observation: " + google_tldr,
                    source=ut.GOOGLE,
                    tldr=google_tldr,
                    keywords=keyword_set,
                )
            )
            prev_tldr = google_tldr
    # print(f"\n******meta return: {google_tldr} *****\n")
    return meta_chat_history, CONTINUE


if __name__ == "__main__":
    # test_parse_decomp()
    # meta("what is the Japanese name of the birthplace of Hugh Jackman", [])
    # meta("What is the capital of the birthplace of Levy Mwanawasa?",[])
    # meta("What is the (rounded down) latitude of the birthplace of Ferenc Puskas?",[])
    # meta("What is the (rounded down) longitude of the birthplace of Juliane Koepcke?",[])
    # meta("What is the top-level domain of the birthplace of Norodom Sihamoni?",[])
    # meta("What is the 3166-1 numeric code for the birthplace of Gilgamesh?",[])
    # meta("What is the currency in the birthplace of Joel Campbell?",[])
    # meta("What is the currency abbreviation in the birthplace of Antonio Valencia?",[])
    # meta("What is the currency symbol in the birthplace of Marek Hamsˇ´ık?",[])
    # meta("What is the Japanese name of the birthplace of Hugh Jackman?",[])
    # meta("What is the Spanish name of the birthplace of Fred´ eric Chopin? ",[])
    # meta("What is the Russian name of the birthplace of Confucius?",[])
    # meta("What is the Estonian name of the birthplace of Kofi Annan?",[])
    # meta("What is the Urdu name of the birthplace of Nicki Minaj?",[])
    # meta("What is the calling code of the birthplace of Milla Jovovich?",[])
    # meta("Who was the champion of the Masters Tournament in the year that Bob Dylan was born?",[])
    # meta("Who won the Nobel Prize in Literature in the year Matt Damon was born?",[])
    # meta("Who was the President of the United States when Sting was born?",[])
    meta(
        "What are the latest reviewer opinions on Tesla Full Self Driving Beta version 11.3.4?",
        [],
        debug=True,
    )
    meta("Michael D'Ambrosio Hound Labs", [], debug=True)
