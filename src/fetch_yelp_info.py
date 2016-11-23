"""
- [x] Pegar somente as "companies" que foram alvo de gastos com alimentação.
- [x] Fazer a busca na api do {Yelp, Foursquare} passando como parâmetros o "trade_mark" e { latitude, longitude, zip_code }.
- [ ] Criar um dataset a partir dos resultados da busca.
"""

import json, requests, re, os.path, datetime
import configparser
import pandas as pd
import numpy as np

REIMBURSEMENTS_DATASET_PATH = os.path.join('data', '2016-11-19-reimbursements.xz')
COMPANIES_DATASET_PATH = os.path.join('data', '2016-09-03-companies.xz')
YELP_DATASET_PATH = os.path.join('data', 'yelp-companies.xz')

def companies():
  # Loading reimbursements
  docs = pd.read_csv(REIMBURSEMENTS_DATASET_PATH,
                     low_memory=False,
                     dtype={'cnpj_cpf': np.str})
  # Filtering only congressperson meals
  meal_docs = docs[docs.subquota_description == 'Congressperson meal']
  # Storing only unique CNPJs
  meal_cnpjs = meal_docs['cnpj_cpf'].unique()
  # Loading companies
  all_companies = pd.read_csv(COMPANIES_DATASET_PATH,
                              low_memory=False,
                              dtype={'trade_name': np.str})
  all_companies = all_companies[all_companies['trade_name'].notnull()]
  # Cleaning up companies CNPJs
  all_companies['clean_cnpj'] = all_companies['cnpj'].map(cleanup_cnpj)
  # Filtering only companies that are in meal reimbursements
  return all_companies[all_companies['clean_cnpj'].isin(meal_cnpjs)]

def cleanup_cnpj(cnpj):
  regex = r'\d'
  digits = re.findall(regex, '%s' % cnpj)
  return ''.join(digits)

def remaining_companies(fetched_companies, companies):
  return companies[~companies['cnpj'].isin(fetched_companies['cnpj'])]

def load_companies_dataset():
  if os.path.exists(YELP_DATASET_PATH):
      return pd.read_csv(YELP_DATASET_PATH)
  else:
      return pd.DataFrame(columns=['cnpj'])

def parse_fetch_info(response):
  if response.status_code == 200:
    json = response.json()
    results = json['businesses']
    if results:
        return results[0]

# ----------------------------
# Request to yelp API getting by term and zip code
# https://www.yelp.com/developers/documentation/v3/business_search
def fetch_yelp_info(term, location):
  url = 'https://api.yelp.com/v3/businesses/search'
  headers = {"Authorization":"Bearer {}".format(access_token)}
  params = {'term': term, 'location': location }
  response = requests.get(url, headers=headers, params=params);
  return parse_fetch_info(response)

settings = configparser.RawConfigParser()
settings.read('config.ini')
access_token = settings.get('Yelp', 'AccessToken')

companies_w_meal_expense = companies()

companies_trade_names = companies_w_meal_expense.trade_name.dropna()
companies_zip_code = companies_w_meal_expense.zip_code.dropna()

fetched_companies = load_companies_dataset()
companies_to_fetch = remaining_companies(fetched_companies, companies())[:20]

for _, company in companies_to_fetch.iterrows():
    print('Fetching %s - CNPJ: %s' % (company['trade_name'], company['zip_code']))
    fetched_company = fetch_yelp_info(company['trade_name'], company['zip_code'])
    if fetched_company:
        print('Successfuly matched %s' % fetched_company['name'])
        fetched_company['scraped_at'] = datetime.datetime.utcnow().isoformat()
        fetched_company['cnpj'] = company['cnpj']
        fetched_companies = fetched_companies.append(pd.Series(fetched_company),
                                                     ignore_index=True)
    else:
        print('Not found')

fetched_companies.to_csv(YELP_DATASET_PATH, compression='xz', index=False)
