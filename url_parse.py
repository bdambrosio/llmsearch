def findnth(haystack, needle, n):
    parts= haystack.split(needle, n+1)
    if len(parts)<=n+1:
        return -1
    return len(haystack)-len(parts[-1])-len(needle)


def extract_site(url):
    site = ''
    base= findnth(url, '/',2)
    if base > 2: site = url[:base].split('.')
    if len(site) > 1: site = site[-2]
    site = site.replace('https://','')
    site = site.replace('http://','')
    return site

