import logging
import sys

logger = logging.getLogger(__name__)

logging.root.setLevel(logging.INFO)
logging.root.addHandler(logging.StreamHandler(sys.stdout))
