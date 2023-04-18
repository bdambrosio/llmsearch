import requests
import re
from unstructured.partition.html import partition_html

def reform(text):
    candidate_paragraphs = (paragraph.strip() for paragraph in text.split('\n'))
    paragraphs = []
    paragraph = ''
    for candidate in candidate_paragraphs:
        if len(paragraph) > 600:
            paragraphs.append(paragraph+'\n')
            paragraph = ''
        # first see if candidate is big enough to be its own paragraph
        if len(candidate) >= 600:
            if len(paragraph) > 0:
                paragraphs.append(paragraph+'\n')
                paragraphs.append(candidate+'\n')
        elif len(candidate) > 3:
            paragraph += candidate+' '
    return paragraphs


def process_actions(text):
  #look for actions in response
  action_indecies = re.finditer('Action:', text) # Action: Ask {Google, User} "query"
  actions = []
  editted_response = text
  for action_index in action_indecies:
      action = text[action_index.span()[1]:]
      agent = None; query = None
      query_start = action.find('"')
      if query_start > 0:
        agent = action[:query_start].strip()
        query_end = action[query_start+1:].find('"')
        if query_end > 0:
          query = action[query_start+1:query_start+1+query_end]
          action = text[action_index.start():action_index.start()+query_start+query_end]
      if agent is None or query is None:
        print("can't parse action, skipping", action_index)
        continue
      actions.append([agent, query])
      editted_response = editted_response.replace(action, '')
  return actions


#html = requests.get('https://www.yelp.com/biz/broadway-cafe-oakland')
#elements = partition_html(text = html.content)
#text = '.\n'.join([str(e).strip() for e in elements])
#paras = reform(text)
#for para in paras:
#    print(f'\npara:\n{para}')

text = 'Action: Ask google "tallest building"'
print(process_actions(text))
