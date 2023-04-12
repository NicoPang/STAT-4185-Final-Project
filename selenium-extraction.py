import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs

#from selenium import webdriver
#from selenium.webdriver.chrome.service import Service
#from selenium.webdriver.common.by import By

import time

def get_url_string(long_url):
    return long_url.split('/')[2]

def get_num_pages(works):
    return min(5000, int(works / 20))
    
# Creates an array of ranges for the driver to step through
# This is necessary to segment data grabs
def to_pagerange_array(pages):
    pageranges = []
    page_index = 0
    while page_index < pages:
        pageranges.append([page_index + 1, min(page_index + 101, pages + 1)])
        page_index += 100
    return pageranges
    
# Gets the url for the webdriver to start from
def get_url(fandom, page):
    # Filters out explicit, mature, non-consensual, orders by kudos and excludes crossovers
    processed_url = f'https://archiveofourown.org/tags/{fandom}/works?commit=Sort+and+Filter&exclude_work_search%5Barchive_warning_ids%5D%5B%5D=19&exclude_work_search%5Brating_ids%5D%5B%5D=12&exclude_work_search%5Brating_ids%5D%5B%5D=13&page={page}&work_search%5Bcomplete%5D=&work_search%5Bcrossover%5D=F&work_search%5Bdate_from%5D=&work_search%5Bdate_to%5D=&work_search%5Bexcluded_tag_names%5D=&work_search%5Blanguage_id%5D=&work_search%5Bother_tag_names%5D=&work_search%5Bquery%5D=&work_search%5Bsort_column%5D=kudos_count&work_search%5Bwords_from%5D=&work_search%5Bwords_to%5D'
    return processed_url

def get_data_page_selenium(driver):
    works = driver.find_elements(By.CSS_SELECTOR, '.blurb')
    page_works_data = []
    
    if len(works) == 0:
        raise Error
    
    for work in works:
        # Obtain title and author
        title_card = work.find_elements(By.CSS_SELECTOR, 'h4 a')
        title = title_card[0].text
        author = title_card[1].text if len(title_card) > 1 else 'Anonymous'
        #print('title: ' + title)
        #print('author: ' + author)
        
        # Get popularity statistics
        kudos = work.find_element(By.CSS_SELECTOR, '.kudos a').text
        comments = work.find_element(By.CSS_SELECTOR, '.comments a').text
        bookmarks = work.find_element(By.CSS_SELECTOR, '.bookmarks a').text
        hits = work.find_element(By.CSS_SELECTOR, 'dd.hits').text
        #print('kudos: ' + kudos)
        #print('comments: ' + comments)
        #print('bookmarks: ' + bookmarks)
        #print('hits: ' + hits)
        
        # Obtain tags
        tags = []
        tags_html = work.find_elements(By.CSS_SELECTOR, '.freeforms .tag')
        for tag in tags_html:
            tag_text = tag.text
            tag_ref = tag.get_attribute('href')
            #print('tag name: ' + tag_text)
            
            tags.append([tag_text, tag_ref])
            
        # Save to one object
        page_works_data.append([title, author, kudos, comments, bookmarks, hits, tags])
        
        #print(f'{title}: {len(tags)} tags found')
        
    return page_works_data
    
def get_page_data(fandom, page):
    request = requests.get(get_url(fandom, page))
    document = bs(request.text, 'html.parser')
    works = document.select('.blurb')
    page_works_data = []
    
    for work in works:
        # Obtain title and author
        title_card = work.select('h4 a')
        title = title_card[0].text
        author = title_card[1].text if len(title_card) > 1 else 'Anonymous'
#        print('title: ' + title)
#        print('author: ' + author)
        
        # Get popularity statistics
        kudos = work.select('.kudos a')[0].text if len(work.select('.kudos a')) >= 1 else -1
        comments = work.select('.comments a')[0].text if len(work.select('.comments a')) >= 1 else -1
        bookmarks = work.select('.bookmarks a')[0].text if len(work.select('.bookmarks a')) >= 1 else -1
        hits = work.select('dd.hits')[0].text if len(work.select('dd.hits')) >= 1 else -1
#        print('kudos: ' + kudos)
#        print('comments: ' + comments)
#        print('bookmarks: ' + bookmarks)
#        print('hits: ' + hits)
        
        # Obtain tags
        tags = []
        tags_html = work.select('.freeforms .tag')
        for tag in tags_html:
            tag_text = tag.text
            tag_ref = tag['href']
#            print('tag name: ' + tag_text)
            
            tags.append([tag_text, tag_ref])
            
        # Save to one object
        page_works_data.append([title, author, kudos, comments, bookmarks, hits, tags])
        
        #print(f'{title}: {len(tags)} tags found')
        
    return page_works_data

def get_data_pagerange_selenium(fandom, pagerange):
    # Driver setup
    PATH = './chromedriver'
    service = Service(PATH)
    driver = webdriver.Chrome(service = service)
    driver.get(get_url(fandom, pagerange[0]))
    
    # Get past TOS for first open of AO3
    agree = driver.find_element(By.CSS_SELECTOR, '#tos_agree')
    agree.click()
    agree = driver.find_element(By.CSS_SELECTOR, '#accept_tos')
    agree.click()
    
    # To avoid pulling from TOS agreement section
    time.sleep(2)
      
    print(f'{0}/{pagerange[1] - pagerange[0]} pages completed.')
    
    section_data = []
    section_data += get_data_page_selenium(driver)
    print(f'1/{pagerange[1] - pagerange[0]} pages completed.', end = '\r')
    for i in range(pagerange[0] + 1, pagerange[1]):
        next_page_button = driver.find_element(By.CSS_SELECTOR, '.next a')
        next_page_button.click()
        
        section_data += get_data_page_selenium(driver)
        print(f'{i - pagerange[0]}/{pagerange[1] - pagerange[0]} pages completed.', end = '\r')
        
        # To avoid HTTP 429
        time.sleep(5)
        
    print(f'Successfully extracted {len(section_data)} works.')
    
    return section_data
    
def extract_fandom_selenium(fandom, pageranges, filename, start_index = 0):
    column_names = ['Title', 'Author', 'Kudos', 'Comments', 'Bookmarks', 'Hits', 'Tags']
    single_fandom_df = pd.DataFrame(columns = column_names)
    
    # If this is resuming a previous extraction
    if start_index > 0:
        old_df = pd.read_csv(filename)
        single_fandom_df = pd.concat([single_fandom_df, old_df], ignore_index = True)
        print(f'Resuming at section {start_index + 1}')
        
    # Iterate through remaining
    for i in range(start_index, len(pageranges)):
        try:
            section_data = get_data_pagerange_selenium(fandom, pageranges[i])
            section_df = pd.DataFrame(section_data, columns = column_names)
            single_fandom_df = pd.concat([single_fandom_df, section_df], ignore_index = True)
            print(f'{i + 1}/{len(pageranges)} sections completed.')
        except Exception as e:
            single_fandom_df.to_csv(filename)
            print(f'Failed on section {i + 1}')
            print(e)
            return
            
    single_fandom_df.to_csv(filename)
    
def extract_fandom(fandom, num_pages, filename, start_page = 1):
    column_names = ['Title', 'Author', 'Kudos', 'Comments', 'Bookmarks', 'Hits', 'Tags']
    single_fandom_df = pd.DataFrame(columns = column_names)
    
    # If this is resuming a previous extraction
    if start_page > 1:
        old_df = pd.read_csv(filename)
        single_fandom_df = pd.concat([single_fandom_df, old_df], ignore_index = True)
        print(f'Resuming at page {start_page}')
        
    # Iterate through remaining
    for i in range(start_page, num_pages + 1):
        try:
            section_data = get_page_data(fandom, i)
            section_df = pd.DataFrame(section_data, columns = column_names)
            single_fandom_df = pd.concat([single_fandom_df, section_df], ignore_index = True)
            print(f'{i}/{num_pages} page completed.', end = '\r')
            time.sleep(5)
        except Exception as e:
            print(f'{len(single_fandom_df)} rows saved. This is {len(single_fandom_df)/20} pages.')
            single_fandom_df.to_csv(filename)
            print(f'Failed on page {i}')
            print(e)
            return
            
    single_fandom_df.to_csv(filename)
    print(f'Saved to {filename}')
        

if __name__ == '__main__':
    fandoms_df = pd.read_csv('fandoms.csv')
    fandom_link_reps = fandoms_df['Link'].apply(get_url_string)
    fandom_pages = fandoms_df['Number of Works'].apply(get_num_pages)
    fandom_pageranges = fandom_pages.apply(to_pagerange_array)
    
    #print(fandom_link_reps)

    for i in range(len(fandoms_df)):
        print(fandoms_df['Name'][i])
        print(fandom_pages[i])

    print(f'total pages: {sum(fandom_pages)}')
    
    print(get_url(fandom_link_reps[9], 2335))
    
#    extract_fandom(fandom_link_reps[7], fandom_pages[7], 'pokemon.csv', start_page = 965)
#    extract_fandom(fandom_link_reps[8], fandom_pages[8], 'hetalia.csv', start_page = 85)
#    extract_fandom(fandom_link_reps[9], fandom_pages[9], 'onepiece.csv', start_page = 508)
