import re
import requests

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from time import sleep

from database import DatabaseHandler


def generate_urls() -> list:
    '''Generates urls for letters A-Z and digits 0-9.'''

    url = 'https://www.legal500.com/law-firm-profiles/#'
    urls = []
    for i in range(10):
        urls.append(url + str(i))
    for i in range(97, 123):
        urls.append(url + str(chr(i)))
    return urls


def get_html_content(url: str, slow=True, delay: int=20) -> str:
    '''Reads provided webpage. Use slow=True if webpage needs delay'''

    if slow:
        chrome_options = Options()
        chrome_options.add_argument('--log-level=3') # hides console logging
        chrome_options.add_argument("--headless") # hides browser window
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        sleep(delay)
        data = driver.page_source
        driver.quit()
    else:
        data = requests.get(url).content
    return data


def html_content_to_local_file(url: str, file: str='output.html') -> None:
    '''Saves html content to local file for debug.'''

    # Specify div class you want to get
    firms_div = 'offices lawFirmWrapper'
    office_div = 'wrap'

    # Specify method of getting html content
    # html_content = get_html_content(url)    # slow loading with delay
    html_content = requests.get(url).content

    data = BeautifulSoup(html_content, 'html.parser')
    extracted_data = data.find_all('div', class_=office_div)
    with open(file, 'w', encoding='utf-8') as f:
        f.write(str(extracted_data))
    f.close()


def get_firms_from_letter_page(url: str) -> list[dict]:
    '''Scrapes all firms from "letter page".'''

    html_content = get_html_content(url)

    if html_content is None:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    firms_soup = soup.find_all('div', class_='office')

    domain = 'https://www.legal500.com'
    firms_data = []
    for firm_soup in firms_soup:
        firm = {}

        # scrape name
        firm['name'] = firm_soup.get('data-name')

        # scrape logo
        logo_img = firm_soup.find('img')
        firm['logo_url'] = logo_img.get('src') if logo_img else None
        firm['logo_url'] = firm['logo_url'] if '/no-image.png' not in firm['logo_url'] else None

        # scrape slugs
        slug_tags = firm_soup.find('div', class_='law-firm-profile-office')
        slugs = slug_tags.find_all('a') if slug_tags else None

        # create tuple (slug, city)
        firm['slugs'] = [(domain + a.get('href'), a.text) for a in slugs if a.text != firm['name']] if slugs else []

        # scrape headquater
        headquater = firm_soup.find('a', class_='office__city')
        firm['headquater'] = headquater.text.title() if headquater else None
        firm['office'] = []

        firms_data.append(firm)

    if len(firms_data) == 0:
        print('Could not load webpage, next try in 5 seconds')
        sleep(5)
        firms_data = get_firms_from_letter_page(url)

    return firms_data


def get_office_data(slug: str, city: str) -> dict:
    '''Scrapes data of single office.'''
    
    office_data = {'slug': slug, 'city': city.title(), 'practice': [], 'ranking': []}
    html_content = requests.get(slug).text
    soup = BeautifulSoup(html_content, 'html.parser')
    firms_soup = soup.find('div', id='left-col')
    if not firms_soup:
        return office_data

    # scrape address
    address_tag = firms_soup.find('div', class_='address-box')
    office_data['address'] = address_tag.text if address_tag else None

    # scrape contact info
    contact_tag = firms_soup.find('div', class_='contact-links')
    email_tag = contact_tag.find('a', class_='firm-email')
    office_data['email'] = email_tag.get('href').replace('mailto:', '').split('?')[0] if email_tag else None
    website_tag = contact_tag.find('a', class_='firm-website')
    office_data['website'] = website_tag.get('href') if website_tag else None
    office_data['phone'] = None
    for span in contact_tag('span'):
        if span.find('i', class_='fa fa-phone-square'):
            office_data['phone'] = span.text.strip().replace(' ', '')
            break
    
    # scrape practice info
    office_data['practice'] = get_practice(slug, html_content)

    # scrape ranking info
    office_data['ranking'] = get_ranking(slug, html_content)

    return office_data


def get_ranking(slug: str, html_content: str=None) -> list[str]:
    '''Scrapes firm ranking.'''
    
    if html_content is None:
        html_content = requests.get(slug).text
    
    ranking = []
    soup = BeautifulSoup(html_content, 'html.parser')
    ranking_soup = soup.find('div', id='right-col')
    ranking_tags = ranking_soup('li')
    for rank in ranking_tags:
        ranking.append(rank.text)

    return ranking


def get_practice(slug: str, html_content: str=None) -> list[dict]:
    '''Scrapes firm practice.'''

    if html_content is None:
        html_content = requests.get(slug).text

    # Get all starting indexes of <h3> tag
    h3_indexes = [s.start() for s in re.finditer('<h3 class="ranking-profile-header">', html_content)]
    if len(h3_indexes) < 1:
        return []

    practices = []
    practices_soup = []

    # Get all text between <h3> tags
    for i in range(len(h3_indexes) - 1):
        content_between_h3 = html_content[h3_indexes[i]:h3_indexes[i+1]-1]
        splitted_soup = BeautifulSoup(content_between_h3, 'html.parser')
        practices_soup.append(splitted_soup)
    content_after_last_h3 = html_content[h3_indexes[-1]:]
    splitted_soup = BeautifulSoup(content_after_last_h3, 'html.parser')
    practices_soup.append(splitted_soup)

    for each_practice in practices_soup:
        practice = {}
        start_index, end_index = 0, 0

        # Scrape name of practice and tier
        header = each_practice.find('h3', class_='ranking-profile-header')
        practice['name'] = header.text[:header.text.find('Tier')] if header else None
        practice['tier'] = header.text[header.text.find('Tier'):] if header else None

        # Scrape description
        each_practice_str = str(each_practice)
        start_index = each_practice_str.find(str(header)) + len(str(header))
        end_index = each_practice_str.find('<div class="ranked_lawyers">')
        # end_index = each_practice_str.find('<div>')
        description_content = each_practice_str[start_index:end_index]
        description_content_soup = BeautifulSoup(description_content, 'html.parser')
        practice['description'] = description_content_soup.get_text()

        # Scrape leading individuals
        practice['leading_individuals'] = None
        lead_ind_soup = each_practice.find('div', class_='ranked_lawyers')
        if lead_ind_soup and 'Leading individuals' in str(lead_ind_soup):
            lead_ind_soup = lead_ind_soup.find_all('div', class_='ranking-box')
            for s in lead_ind_soup:
                if 'Leading individuals' in str(s) and s.find('div'):
                    practice['leading_individuals'] = s.find('div').get_text()
                    break

        # Scrape practice head
        practice_head_soup = each_practice.find('div', class_='practice-heads-list')
        practice['practice_head'] = practice_head_soup.text if practice_head_soup else None

        # Scrape testimonials
        testimonials_soup = each_practice.find('div', class_='testimonials-list')
        practice['testimonials'] = testimonials_soup.text if testimonials_soup else None

        # Scrape key clients
        testimonials_soup = each_practice.find('div', class_='client-list')
        practice['key_clients'] = testimonials_soup.text if testimonials_soup else None

        # Scrape work highlights
        testimonials_soup = each_practice.find('ul', class_='work-highlights')
        practice['work_highlights'] = testimonials_soup.text if testimonials_soup else None
        
        practices.append(practice)

    return practices


def main() -> None:
    # Connect to database and create tables
    db_handler = DatabaseHandler()
    db_handler.connect()
    db_handler.create_tables()

    # Generate urls for every letter and digit
    urls = generate_urls()
    total = 0
    for url in urls:
        # Get data of each letter/digit webpage
        print(f'\nGathering firms from letter "{url[-1].upper()}" webpage...')
        firms = get_firms_from_letter_page(url)
        total += len(firms)
        print(f'\nFound {len(firms)} firms:', total)
        
        for firm in firms:
            # Check if firm already exists in database
            if db_handler.check_firm(firm):
                continue
            print(firm['name'])
            # Get all data of firm office
            for slug, city in firm['slugs']:
                print(slug)
                firm_office = get_office_data(slug, city)
                firm_office['name'] = firm['name']
                firm['office'].append(firm_office)
            print('******************************************************')

            # Insert firm data to database
            db_handler.insert_firm(firm)

    # Close database connection
    db_handler.close_connection()


if __name__ == '__main__':
    main()
