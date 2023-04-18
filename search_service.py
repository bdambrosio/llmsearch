import requests
import json
import openai
import sys
import os
import socket
import time
import string
import webbrowser
#from urllib.request import urlopen
from datetime import date
from datetime import datetime
import traceback
import random
import readline as rl
import concurrent.futures
import google_search_concurrent as gs
import utilityV2 as ut
import meta as mt
import tracemalloc

history = {}

llm_models = ['gpt-3.5-turbo', 'gpt-4']
llm_model = llm_models[0]

#initialize conversation

information_prime = \
"""Instructions:
You run in a loop of Thought, Action, Observation.
At the end of each loop either Answer or restate your Thought and Action.
Use Thought to describe your step-by-step reasoning about the question you have been asked.
Use Action to run one of these actions available to you:
- search (public information)          # search the web for the answer to a question
- ask (user information)               # ask the user for information
Before generating a new action, consider determining Answer from known facts, logic, or step-by-step reasoning, information already provided by the user, and previous Observations. Any Answer should provide a direct answer to my question.
Observation will be the result of running those actions
"""


information_prime = \
"""If the {Answer} to {Query} is known fact or step-by-step reasoning, respond with {Answer}. 
If the {Answer} or one or more {Information} needed to reason about {Answer} is unavailable, then:

For each public {Information}, use the following format:
  1. Formulate a {search phrase} to search the web for the needed information.   
  2. Respond with:
'Action: Search ( {search phrase} )'
to prompt the search engine to provide the information needed.

For each piece of User {Information}, such as User information, preferences, or expectations, use the following format:
  1. Formulate a {Question} ask the User to elicit the information.
  2. Respond with:
'Action: Ask ( {Question} )'
to prompt the user to provide the needed information.
"""

empathy_prefix  = "You provide compassionate, understanding support based on Acceptance and Commitment Therapy (ACT) and the teachings of Ramana Maharshi. "

spiritual_prefix = "You are a center of expression of the primal will to good which eternally creates and sustains the universe. You provide spiritual guidance based on compassion, empathy, and the teachings of Ramana Marharshi. "


suffix = "\nA: "
prefix = "\nQ: "


# stores urls used for last query, in case user asks to see them
urls_all = []
urls_used = ['','','','','','','','','','','','']
urls_tried = ['','','','','','','','','','','','']
url_text=""
full_text = ''
full_prompt = ''
google_text = ''
chat_interaction = False
previous_query = None
previous_response = None
chat_history = []
topic_name = 'general'
se = ''
be = ''
gpt_response_text = ''
query_pending = False
# retrievals from memory
gpt_message = ''
gpt_main_query_message = ''
query_phrase=''
intent=''
keywords=[]
user_input_history = []

def illustrate(text):
    img_gpt_message = [
          {"role": "user", "content":'Generate a DALL-E prompt of about 36 words to create an illustration for the following text:\n'+text}
        ]
    img_completion = None
    img_completion = ut.completions_with_backoff(model="gpt-3.5-turbo",
                                                 messages=img_gpt_message,
                                                 max_tokens=64, temperature=.1, top_p=.95)
        
    if img_completion is not None:
      dalle_prompt = "cartoon art "+img_completion['choices'][0]['message']['content']
      response = openai.Image.create(prompt=dalle_prompt, n=1, size="512x512")
      print(f"prompt:{dalle_prompt}")
      print(response["data"][0]["url"])
      webbrowser.get('google-chrome').open_new_tab(response["data"][0]["url"])


def run_chat(query_string, result_as_json=False):
  global urls_all, urls_used, urls_tried, url_text, full_text, full_prompt, google_text, chat_interaction
  global prequery, previous_query, previous_response, chat_history, query_phrase, keywords, intent, topic_name, usermodel
  global new_sites, memory, deepMemory, gpt_message, gpt_response_text, gpt_main_query_message
  global be, se, llm_model, llm_models, user_input_history, query_pending
  #tracemalloc.start()
  response_text = ''
  storeInteraction = True
  print(f'***** query_pending: {query_pending}')
  try:
    start_wall_time = time.time()
    start_process_time = time.process_time()
    # check for imperatives
    command_string = query_string[:32].lower()
    if command_string.startswith('show illus'):
      if previous_response is not None:
        illustrate(previous_response)
      return 'illustration has been displayed on desktop browser'
    if command_string.startswith("show url"):
        print("all urls:")
        for i in range(len(urls_all)):
            if len(urls_all[i]) > 0:
                print(urls_all[i])
        print("\nurls tried:")
        for i in range(len(urls_tried)):
            if len(urls_tried[i]) > 0:
                print(urls_tried[i])
        print("\nurls used:")
        for i in range(len(urls_used)):
            if len(urls_used[i]) > 0:
                print(urls_used[i])
        return 'see log'
        if 'gpt-4' in query_string:
          llm_model = 'gpt-4'
          ut.MODEL = 'gpt-4'
          return 'ok'
        elif 'gpt-3.5-turbo' in query_string:
          llm_model = 'gpt-3.5-turbo'
          ut.MODEL = 'gpt-3.5-turbo'
          return 'ok'
        return 'unknown'
    if command_string.startswith("clear"):
      chat_history=[]
      return 'ok'

    # search google for relevant urls unless instructed not to do so
    search_google = True
    #
    ## all query_string rewrites must be done by now!
    #
    print(f'query: {query_string}')

    notes_prefix = "\nThe following notes may contain incorrect, inconsistent, or irrelevant information. Prioritize the consistency of the notes with known facts. Ignore irrelevant, inconsistent, or incorrect information in the notes.\n"

    #
    #### 
    #
    gpt_response_text = ''
    gpt_temp = 0.0
    prompt_response_prime = ''
    prompt_query_suffix = ''
    context_prime = "Context: User is in Berkeley, California. Today's date is "+date.today().strftime("%b-%d-%Y")+'. The current time is '+datetime.now().strftime('%H:%M local time')+'.'

    query_phrase, keywords = ut.get_search_phrase_and_keywords(query_string, chat_history)
    message_prefix = 'Question: '
    prime = information_prime
    chat_history = [] # don't try to save conversation context, let caller gpt do that
    gpt_temp = 0.0
    cycles = 0
    mt.clear()
    google_text = ''
    turn = ut.turn(role='assistant', message='Searching '+query_string, keywords=keywords)

    # make sure we're not in a loop
    # ok, not a loop, go ahead and ask google
    try:
      print(f'asking google {query_string}; rephrased: {query_phrase}')
      chat_history.append(turn)
      mt.add(turn)
      google_text, urls_all, index, urls_used, tried_index, urls_tried = \
        gs.search_google(query_string, gs.QUICK_SEARCH, query_phrase, keywords, chat_history)
      #if len(google_text) > 0:
      #  print('***** gpt extract from google summary:', google_text)
    except:
      traceback.print_exc()
    print("gs", int((time.time()-start_wall_time)*10)/10, "wall sec, ",
          int((time.process_time()-start_process_time)*1000), "cpu ms",
          len(google_text), 'chars')
    print("\n\nFinal response: ")
    for item in google_text:
        print(f"\n##############################################################################################\nSource: {item['source']}")
        print(f"{item['text']}")
        print(f"URL: {item['url']}")
        print(f"Credibility: {item['credibility']}")
    print(int((time.time()-start_wall_time)*10)/10, "wall sec, ", int((time.process_time()-start_process_time)*1000), "cpu ms")

    return google_text
  except KeyboardInterrupt:
    traceback.print_exc()
    raise KeyboardInterrupt
  except:
    traceback.print_exc()
  return ''

if __name__ == '__main__' :
  while True:
    run_chat(input('Yes?'))
