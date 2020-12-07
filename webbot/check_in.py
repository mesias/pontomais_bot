from datetime import datetime, timedelta
import time
import logging

import yaml
import pathlib

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# defaults #
YAML_FILE = "bot.yaml"
BASE_URL = "https://app.pontomaisweb.com.br/#"
LOGIN_URL = f"{BASE_URL}/acessar"
PONTO_URL = f"{BASE_URL}/meu_ponto/registro_de_ponto"
BUTTON_XPATH = "//button[@class='btn btn-primary ng-binding ng-scope']"
MODAL_XPATH = "//div[@class='modal-content']"
DELAY = 60
WEBDRIVER_EXECUTABLE = "chromedriver"
# CHECKIN_ENABLED = True  # for debugging purposes
CHECKIN_ENABLED = False  # for debugging purposes


# globais #
driver = selenium_config = None
config = {}
log_name = 'log/bot_checkin-{:%Y-%m}.log'.format(datetime.now())
pathlib.Path('log').mkdir(parents=True, exist_ok=True)
pathlib.Path('screenshot').mkdir(parents=True, exist_ok=True)

logging.basicConfig(format=u'%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO,
                    handlers=[logging.FileHandler(log_name, encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger("bot_checkin")
logger.setLevel(logging.DEBUG)


def scr_file_ok():
    return 'screenshot/screenshot-{:%Y%m%d_%H%M%S}-OK.png'.format(datetime.now())


def scr_file_error():
    return 'screenshot/screenshot-{:%Y%m%d_%H%M%S}-ERROR.png'.format(datetime.now())


def get_delta(ttt):
    return timedelta(seconds=(time.time() - ttt))


def load_config(yaml_file=YAML_FILE):
    global config
    if config is None:
        with open(YAML_FILE, 'r') as stream:
            logger.debug('Carregando Yaml')
            try:
                config = yaml.safe_load(stream)
            except yaml.YAMLError:
                logger.exception('Falha ao carregar yaml')
    else:
        logger.debug('Yaml já carregado')

def resolve_urls():
    ponto_mais = config.get('pontomais')
    ponto_mais_urls = ponto_mais.get('urls')
    login_url = LOGIN_URL
    ponto_url = PONTO_URL
    if ponto_mais_urls:
        base_url = ponto_mais_urls.get('base', BASE_URL)
        if 'login' in ponto_mais_urls:
            login_url = f"{base_url}{ponto_mais_urls['login']}"
        if 'ponto' in ponto_mais_urls:
            ponto_url = f"{base_url}{ponto_mais_urls['ponto']}"
    return login_url, ponto_url

def init_driver():
    global driver, selenium_config

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=OFF")
    chrome_options.add_argument("window-size=800,600")
    # chrome_options.add_argument("--no-sandbox") # linux only
    # chrome_options.add_argument("--headless")
    driver_executable = WEBDRIVER_EXECUTABLE

    selenium_config = config.get('selenium')
    if selenium_config:
        chrome_options.binary_location = selenium_config.get('chrome_binary_path', '')
        driver_executable = selenium_config.get('driver_executable', driver_executable)
    driver = webdriver.Chrome(executable_path=driver_executable, options=chrome_options)


def do_login():
    # driver.set_window_size(900, 800)
    login_url, ponto_url = resolve_urls()
    config_login = config['pontomais']['login']
    logger.debug(f"Abrindo url de login: {login_url}")
    driver.get(login_url)
    logger.debug(f"Abrindo {login_url}")
    driver.find_element_by_name("login").send_keys(config_login['user'])
    pw = driver.find_element_by_name("password")
    pw.send_keys(config_login['pass'])
    ttdi = time.time()
    pw.send_keys(Keys.RETURN)
    logger.debug(f"Fazendo login, verificando troca de url: {ponto_url}")

    load_timeout = DELAY
    if 'selenium' in config:
        config['selenium'].get('timeout', DELAY)
    button_xpath = BUTTON_XPATH
    if 'elements' in config['pontomais']:
        button_xpath = config['pontomais']['elements'].get('register_button_xpath', BUTTON_XPATH)

    try:
        WebDriverWait(driver, load_timeout).until(EC.url_matches(ponto_url))
        logger.debug(f"Chegou na pagina {ponto_url}, tempo: {get_delta(ttdi)}")
        ttdb = time.time()
        WebDriverWait(driver, load_timeout).until(EC.presence_of_element_located((By.XPATH, button_xpath)))
        logger.info(f"Carregou o botao na pagina, tempo: {get_delta(ttdi)} - Só Botão: {get_delta(ttdb)}")
        return True
    except TimeoutException:
        scrshot_error = scr_file_error()
        driver.save_screenshot(scrshot_error)
        logger.exception(f"Loading took too much time! (timeout: {load_timeout}s), error screenshot: {scrshot_error}")
        return False


def do_checkin():
    load_timeout = DELAY
    button_xpath = BUTTON_XPATH
    modal_xpath = MODAL_XPATH

    if 'elements' in config['pontomais']:
        button_xpath = config['pontomais']['elements'].get('register_button_xpath', BUTTON_XPATH)
        modal_xpath = config['pontomais']['elements'].get('register_modal_xpath', MODAL_XPATH)

    if 'selenium' in config:
        config['selenium'].get('timeout', DELAY)

    try:
        button = driver.find_element_by_xpath(button_xpath)
        logger.debug(f"Botao encontrado: '{button.text}' (XPATH: {button_xpath})")
        # check (ElementClickInterceptedException): https://stackoverflow.com/a/56779923/926055
        time.sleep(0.5)

        ttdm = time.time()

        if CHECKIN_ENABLED:
            button.click()
            WebDriverWait(driver, load_timeout).until(EC.presence_of_element_located((By.XPATH, modal_xpath)))
            modal = driver.find_element_by_xpath(modal_xpath)
            try:
                # modelo original: \ue5cd\nPonto registrado com sucesso!\nRecibo nº 00305705964\nOK
                modal_text = modal.text.split('\n')
                logger.debug(f"Confirmou batida de ponto {repr(modal_text)} recibo: {modal_text[-2].split()[-1]}")
            except UnicodeEncodeError:
                logger.exception(f"Falha de unicode com o texto: {repr(modal.text)}")

        scrshot_ok = scr_file_ok()
        driver.save_screenshot(scrshot_ok)
        logger.info(f"Finalizou batida de ponto, tempo: {get_delta(ttdm)}, screenshot: {scrshot_ok}")
    except NoSuchElementException:
        scrshot_error = scr_file_error()
        driver.save_screenshot(scrshot_error)
        logger.exception(f'Não encontrou o botao! (error screenshot: {scrshot_error})')
    except TimeoutException:
        scrshot_error = scr_file_error()
        driver.save_screenshot(scrshot_error)
        logger.exception(f"Carregamento demorou demais! (timeout: {load_timeout}s), error screenshot: {scrshot_error}")
        return False


def finish():
    global driver
    logger.info(f"finalizando: {driver.current_url}")
    driver.close()
    driver = None


def run_checkin():
    logger.info('========================  inicio  ========================')
    load_config()
    ttt = time.time()
    init_driver()
    ttl = time.time()
    try:
        if do_login():
            logger.info(f"Tempo de login: {get_delta(ttl)}")
            ttcin = time.time()
            do_checkin()
            logger.info(f"Tempo de checkin: {get_delta(ttcin)}")
    except Exception:
        logger.exception("Falha ao fazer checkin")
    finish()
    logger.info(f"============== Tempo total: {get_delta(ttt)} ==============")

if __name__ == "__main__":
    run_checkin()
