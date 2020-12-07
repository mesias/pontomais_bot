from webbot import check_in

YAML_FILE = "./config/bot_min.yaml"

check_in.load_config(YAML_FILE)
check_in.run_checkin()
