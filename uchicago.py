#!/usr/bin/env python3

___name__ = "checks"

"""
Basic use of lib.uchicago.edu library search function.
"""
import urllib.request
from bs4 import BeautifulSoup
import urllib.parse

from static import Static
"""
Constants for uchicago
"""


MW_API_HOST = "https://catalog.lib.uchicago.edu"
# MW_API_HOST = https://catalog.lib.uchicago.edu/vufind/Search/Results?
# sort=relevance&join=AND&bool0%5B%5D=AND&lookfor0%5B%5D=queen&type0%5B%5D=Author&lookfor0%5B%5D=&type0%5B%5D=AllFields
# &lookfor0%5B%5D=&type0%5B%5D=AllFields&filter%5B%5D=format%3A%22CD%22&daterange%5B%5D=publishDate&publishDatefrom=&publishDateto=&view=rss

# retuns rss
# https://catalog.lib.uchicago.edu/vufind/Search/Results?join=AND&bool0[]=AND&lookfor0[]=Ravi+Shankar&lookfor0[]=Raga&type0[]=Performer&type0[]=Title&view=rss
# https://catalog.lib.uchicago.edu/vufind/Search/Results?join=AND&bool0[]=AND&lookfor0[]=queen&type0[]=Author&lookfor0[]=a+night+at+the+opera&type0[]=AllFields&daterange[]=publishDate&publishDatefrom=&publishDateto=
# https://catalog.lib.uchicago.edu/vufind/Search/Results?sort=relevance&join=AND&bool0[]=AND&lookfor0[]=queen&type0[]=Author&filter[]=format:"CD"&daterange[]=publishDate&publishDatefrom=&publishDateto=&view=rss

# permission denied:
# https://catalog.lib.uchicago.edu/vufind/swagger-ui/?url=%2Fvufind%2Fapi%3Fswagger
# https://catalog.lib.uchicago.edu/vufind/api/v1/search?lookfor=sibelius&type=Author


def get_records(artist, albumtitle):
    # params = {'join': 'AND',
    #           'bool0[]': 'AND',
    #           'lookfor[]': f'{artist}',
    #           'type0[]': 'Author',
    #           'lookfor0[]': f'{albumtitle.replace(" ", "+")}',
    #           'type0[]': 'AllFields',
    #           'daterange[]': 'publishDate',
    #           'publishDatefrom': '',
    #           'publishDateto': ''}
    st = Static()
    string1 = artist.lower()
    string2 = albumtitle.lower()

    # string1 = urllib.parse.unquote(string1)
    # string2 = urllib.parse.unquote(string2)
    string1 = string1.replace(' ', '+')
    string2 = string2.replace(' ', '+')
    for character in st.characters:
        if character == ' ' or character == '+':
            continue
        string1 = string1.replace(character, '')
        string2 = string2.replace(character, '')

    string1 = urllib.parse.quote(BeautifulSoup(string1, features="lxml").text)
    string2 = urllib.parse.quote(BeautifulSoup(string2, features="lxml").text)

    # https://catalog.lib.uchicago.edu/vufind/Search/Results?sort=relevance&join=AND&bool0%5B%5D=AND&lookfor0%5B%5D=the+bends
    # &type0%5B%5D=Author&lookfor0%5B%5D=strange+days&type0%5B%5D=Title&lookfor0%5B%5D=&type0%5B%5D=AllFields&filter%5B%5D=format%3A%22CD%22
    searchstring = (f'sort=relevance&join=AND&bool0[]=AND&lookfor0[]={string1}&type0[]=Author&filter[]=format:"CD"&lookfor0[]='
                    f'{string2}&type0[]=Title&daterange[]=publishDate&publishDatefrom=&publishDateto=')

    # Use the uchicago catalog to retrieve results
    # print(f"{MW_API_HOST}/vufind/Search/Results?{searchstring}")
    response = urllib.request.urlopen(f"{MW_API_HOST}/vufind/Search/Results?{searchstring}")
    # print(response.url)
    body = response.read()

    if len(body) > 0:
        if '- did not match any resources.' in str(body):
            return None
        else:
            return response.url

    return None
