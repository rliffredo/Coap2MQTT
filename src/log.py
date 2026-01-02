import logging
from logging import config as logging_config
import os
import sys

import yaml


def ensure_directories_for_file_handlers(config_dict):
    if 'handlers' not in config_dict:
        return
    for handler in config_dict['handlers'].values():
        if 'filename' not in handler:
            continue
        log_dir = os.path.dirname(handler['filename'])
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)


def setup_logging():
    # Refresh logger cache
    root = logging.getLogger()
    root.setLevel(root.level)

    if setup_logging.configured:
        return

    # Load basic configuration
    config_file = 'Unknown'
    try:
        config_file = os.getenv('LOG_CONFIG_FILE', 'logger.conf.default.yaml')
        config_dict = yaml.load(open(config_file).read(), Loader=yaml.FullLoader)
        logging_config.dictConfig(config_dict)
        ensure_directories_for_file_handlers(config_dict)
        setup_logging.configured = True
    except (FileNotFoundError, ValueError) as ex:
        # Logging is not available, so write directly to stdout
        logging.root.setLevel(logging.INFO)
        logging.root.addHandler(logging.StreamHandler(sys.stdout))
        logger = logging.getLogger(__name__)
        logger.error(
            f'***** COULD NOT FIND/LOAD LOG CONFIGURATION FILE {config_file} (reason: {ex}): '
            f'LOGGING WILL NOT WORK CORRECTLY! *****')


setup_logging.configured = False  # type: ignore
