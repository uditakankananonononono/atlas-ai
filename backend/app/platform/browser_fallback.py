"""Controlled legacy Selenium fallback; never adds stealth/evasion patches."""
from __future__ import annotations
import os
class LegacyBrowser:
 def __init__(self,driver=None):
  if driver is None:
   from selenium import webdriver
   options=webdriver.ChromeOptions();options.add_argument('--headless=new');options.add_argument('--no-sandbox')
   endpoint=os.getenv('ATLAS_SELENIUM_URL');driver=webdriver.Remote(command_executor=endpoint,options=options) if endpoint else webdriver.Chrome(options=options)
  self.driver=driver
 def read(self,url:str)->dict[str,str]:
  if not url.startswith(('https://','http://')):raise ValueError('http(s) URL required')
  self.driver.get(url);return {'url':self.driver.current_url,'title':self.driver.title,'html':self.driver.page_source,'engine':'selenium','external_effects':False}
 def close(self):self.driver.quit()
